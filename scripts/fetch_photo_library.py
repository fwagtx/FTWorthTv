"""Pull candidate photos for a curated, verified photo library from Wikimedia Commons: landmarks, venues, institutions
and generic beats, by Commons category (exact subject) with a full-text search as the fallback.

Only public-domain, CC0, CC BY and CC BY-SA files are kept, with the credit line of each in candidates.json. A person
then looks at the contact sheets and keeps the ones that really show the subject (scripts/build_photo_library.py).

    python scripts/fetch_photo_library.py out/library            # all topics
    python scripts/fetch_photo_library.py out/library skyline tcu # some topics
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = "FTWorthTv-photo-library/0.1 (open-licence local photos for a community news page; github.com/fwagtx/FTWorthTv)"
OK_LICENSES = ("public domain", "cc0", "cc by", "cc-by", "pd")
SKIP_WORDS = ("map", "logo", "flag", "seal", "diagram", "chart", "poster", "screenshot", "plan", "scan", "postcard",
              "drawing", "painting", "sketch", "1900", "1910", "1920", "1930", "1940", "1950", "1960", "1970", "1980")
PER_TOPIC = 6
MIN_WIDTH = 1100

# topic -> (Commons categories to try, search queries to try)
TOPICS: dict[str, tuple[list[str], list[str]]] = {
    "skyline": (["Skylines of Fort Worth, Texas"], ["Fort Worth skyline"]),
    "skyline-night": ([], ["Fort Worth skyline night"]),
    "downtown": (["Downtown Fort Worth"], ["Downtown Fort Worth street"]),
    "sundance-square": (["Sundance Square"], ["Sundance Square Fort Worth"]),
    "courthouse": (["Tarrant County Courthouse"], ["Tarrant County Courthouse"]),
    "city-hall": (["Fort Worth City Hall"], ["Fort Worth City Hall Texas"]),
    "transit": (["Trinity Metro", "Fort Worth Central Station", "Fort Worth Intermodal Transportation Center"], ["Trinity Metro bus Fort Worth", "TEXRail train"]),
    "stockyards": (["Fort Worth Stockyards"], ["Fort Worth Stockyards cattle drive"]),
    "tcu": (["Texas Christian University", "Amon G. Carter Stadium"], ["TCU campus Fort Worth", "Amon G. Carter Stadium"]),
    "uta": (["University of Texas at Arlington"], ["University of Texas at Arlington campus"]),
    "dickies-arena": (["Dickies Arena"], ["Dickies Arena Fort Worth"]),
    "will-rogers": (["Will Rogers Memorial Center"], ["Will Rogers Memorial Center Fort Worth"]),
    "att-stadium": (["AT&T Stadium"], ["AT&T Stadium Arlington"]),
    "globe-life-field": (["Globe Life Field"], ["Globe Life Field Arlington"]),
    "aac": (["American Airlines Center"], ["American Airlines Center Dallas"]),
    "toyota-stadium": (["Toyota Stadium (Texas)"], ["Toyota Stadium Frisco"]),
    "water-gardens": (["Fort Worth Water Gardens"], ["Fort Worth Water Gardens"]),
    "kimbell": (["Kimbell Art Museum"], ["Kimbell Art Museum"]),
    "modern": (["Modern Art Museum of Fort Worth"], ["Modern Art Museum of Fort Worth"]),
    "bass-hall": (["Bass Performance Hall"], ["Bass Performance Hall Fort Worth"]),
    "zoo": (["Fort Worth Zoo"], ["Fort Worth Zoo"]),
    "botanic-garden": (["Fort Worth Botanic Garden"], ["Fort Worth Botanic Garden"]),
    "trinity-river": (["Trinity River in Fort Worth, Texas", "Trinity Park (Fort Worth, Texas)"], ["Trinity River Fort Worth trail"]),
    "highway": (["Interstate 35W (Texas)", "Interstate 30 in Texas"], ["Fort Worth freeway", "Interstate 35W Fort Worth"]),
    "police": (["Fort Worth Police Department"], ["Fort Worth police car", "Fort Worth Police Department"]),
    "fire": (["Fort Worth Fire Department"], ["Fort Worth Fire Department truck"]),
    "schools": (["Fort Worth Independent School District", "High schools in Fort Worth, Texas"], ["Fort Worth high school building", "Fort Worth ISD school"]),
    "hospital": (["Hospitals in Fort Worth, Texas"], ["Fort Worth hospital", "JPS Health Network"]),
    "arlington": (["Arlington, Texas", "Downtown Arlington, Texas"], ["Arlington Texas downtown", "Arlington Texas city hall"]),
    "dfw-airport": (["Dallas/Fort Worth International Airport"], ["DFW Airport terminal"]),
    "alliance": (["Fort Worth Alliance Airport"], ["Alliance Airport Fort Worth"]),
    "convention-center": (["Fort Worth Convention Center"], ["Fort Worth Convention Center"]),
    "texas-motor-speedway": (["Texas Motor Speedway"], ["Texas Motor Speedway"]),
    "dallas-skyline": (["Skylines of Dallas"], ["Dallas skyline"]),
    "houston-skyline": (["Skylines of Houston"], ["Houston skyline"]),
    "austin-skyline": (["Skylines of Austin, Texas"], ["Austin Texas skyline"]),
    "san-antonio-skyline": (["Skylines of San Antonio"], ["San Antonio skyline"]),
    "capitol": (["Texas State Capitol"], ["Texas State Capitol building"]),
    "heb": (["H-E-B"], ["H-E-B store Texas"]),
    "bucees": (["Buc-ee's"], ["Buc-ee's store"]),
    "whataburger": (["Whataburger"], ["Whataburger restaurant"]),
    "ut-austin": (["Darrell K Royal–Texas Memorial Stadium", "University of Texas at Austin"], ["Texas Longhorns stadium"]),
    "texas-am": (["Kyle Field"], ["Kyle Field Texas A&M"]),
    "texas-tech": (["Jones AT&T Stadium"], ["Texas Tech Jones Stadium"]),
    "baylor": (["McLane Stadium"], ["McLane Stadium Baylor"]),
    "smu": (["Gerald J. Ford Stadium", "Southern Methodist University"], ["SMU campus Dallas Hall"]),
    "unt": (["University of North Texas"], ["University of North Texas campus"]),
    "nrg-stadium": (["NRG Stadium"], ["NRG Stadium Houston"]),
    "daikin-park": (["Minute Maid Park", "Daikin Park"], ["Astros ballpark Houston"]),
    "toyota-center": (["Toyota Center"], ["Toyota Center Houston"]),
    "frost-bank-center": (["Frost Bank Center", "AT&T Center"], ["Spurs arena San Antonio"]),
    "storm": ([], ["Texas thunderstorm clouds", "supercell Texas"]),
    "ice": ([], ["ice storm Texas road", "snow Dallas Fort Worth"]),
    "heat": ([], ["Texas summer sun heat"]),
    "bbq": (["Barbecue in Texas"], ["Texas barbecue brisket plate"]),
    "tacos": ([], ["tacos plate Texas"]),
    "power": ([], ["transmission lines Texas", "ERCOT"]),
    "gas": ([], ["gas station pump Texas"]),
    "courtroom": ([], ["courtroom gavel"]),
    "voting": ([], ["polling place Texas vote here sign"]),
    "money": ([], ["US dollars cash"]),
    "classroom": ([], ["empty classroom desks"]),
    "grocery": ([], ["grocery store aisle"]),
    "apartments": ([], ["apartment construction Texas"]),
    "housing": ([], ["suburban houses Texas"]),
    "jail": (["Tarrant County Jail"], ["jail cell bars"]),
}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/library")
    wanted = sys.argv[2:] or list(TOPICS)
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    cands: list[dict] = []
    seen: set[str] = set()

    def pages_for(params: dict) -> list[dict]:
        base = {"action": "query", "format": "json", "formatversion": 2, "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600}
        r = s.get(API, params={**base, **params}, timeout=40)
        r.raise_for_status()
        return list((r.json().get("query", {}) or {}).get("pages", []) or [])

    def keep(topic: str, page: dict, how: str) -> bool:
        info = (page.get("imageinfo") or [{}])[0]
        title = page.get("title", "")
        meta = info.get("extmetadata", {}) or {}
        lic = re.sub(r"<[^>]+>", "", (meta.get("LicenseShortName", {}) or {}).get("value", "")).strip()
        mime, w, h = info.get("mime", ""), int(info.get("width") or 0), int(info.get("height") or 0)
        low = title.lower()
        if title in seen or not info.get("url") or mime not in ("image/jpeg", "image/png"):
            return False
        if any(x in low for x in SKIP_WORDS) or not lic or not any(k in lic.lower() for k in OK_LICENSES) or "nc" in lic.lower() or "nd" in lic.lower():
            return False
        if w < MIN_WIDTH or h < 600 or w / max(h, 1) > 3.2 or h / max(w, 1) > 1.6:
            return False
        url = info.get("thumburl") or info["url"]
        try:
            r = s.get(url, timeout=60)
            if not r.ok or len(r.content) < 30_000:
                return False
        except Exception as exc:
            print("download failed", title, exc)
            return False
        name = f"{topic}--" + re.sub(r"[^a-zA-Z0-9]+", "_", title.replace("File:", "")).strip("_")[:70] + (".png" if mime == "image/png" else ".jpg")
        (out / name).write_bytes(r.content)
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", "")).strip()
        artist = re.sub(r"\s{2,}", " ", artist)[:80] or "Wikimedia Commons contributor"
        desc = re.sub(r"<[^>]+>", "", (meta.get("ImageDescription", {}) or {}).get("value", "")).strip()[:240]
        cands.append({"file": name, "topic": topic, "title": title, "how": how, "license": lic, "artist": artist,
                      "credit": f"Photo: {artist} via Wikimedia Commons ({lic})", "description": desc,
                      "source_url": info.get("descriptionurl"), "width": w, "height": h})
        seen.add(title)
        return True

    for topic in wanted:
        cats, queries = TOPICS[topic]
        kept = 0
        for cat in cats:
            if kept >= PER_TOPIC:
                break
            try:
                pages = pages_for({"generator": "categorymembers", "gcmtitle": f"Category:{cat}", "gcmtype": "file", "gcmlimit": 60})
            except Exception as exc:
                print("category failed", cat, exc)
                continue
            pages.sort(key=lambda p: -int(((p.get("imageinfo") or [{}])[0].get("width") or 0)))
            for page in pages:
                if kept >= PER_TOPIC:
                    break
                if keep(topic, page, f"category:{cat}"):
                    kept += 1
            time.sleep(0.3)
        for q in queries:
            if kept >= PER_TOPIC:
                break
            try:
                pages = pages_for({"generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 40})
            except Exception as exc:
                print("search failed", q, exc)
                continue
            pages.sort(key=lambda p: -int(((p.get("imageinfo") or [{}])[0].get("width") or 0)))
            for page in pages:
                if kept >= PER_TOPIC:
                    break
                if keep(topic, page, f"search:{q}"):
                    kept += 1
            time.sleep(0.3)
        print(f"{topic}: {kept} file(s)")
    (out / "candidates.json").write_text(json.dumps(cands, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(cands)} candidates in {out}")


if __name__ == "__main__":
    main()
