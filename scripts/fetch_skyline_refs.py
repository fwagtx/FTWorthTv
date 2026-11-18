"""Download openly licensed reference photos of the Fort Worth skyline (and a few landmarks) from Wikimedia Commons,
with their license metadata, so the logo silhouette can be traced from the real thing on a machine without internet.

Only public-domain, CC0, CC BY and CC BY-SA files are kept; the credit line for each is written to refs.json.

Usage: python scripts/fetch_skyline_refs.py out/refs ["query" ...]
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = "FTWorthTv-brand-refs/0.1 (open-licence skyline references for a logo; contact via the project's GitHub issues)"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/refs")
QUERIES = sys.argv[2:] or [
    "Fort Worth skyline", "Downtown Fort Worth skyline Trinity River", "Fort Worth Texas skyline panorama",
    "Fort Worth skyline filemime:image/svg+xml", "Tarrant County Courthouse Fort Worth", "Fort Worth Stockyards sign",
]
OK_LICENSES = ("public domain", "cc0", "cc by", "cc-by", "pd")
SKIP_WORDS = ("map", "logo", "flag", "seal", "diagram", "chart", "poster", "screenshot", "night", "nacht")
MAX_PER_QUERY = 14

OUT.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers["User-Agent"] = UA
refs: list[dict] = []
seen: set[str] = set()


def search(query: str) -> list[dict]:
    params = {"action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 40,
              "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1800, "format": "json"}
    r = session.get(API, params=params, timeout=40)
    r.raise_for_status()
    return list((r.json().get("query", {}) or {}).get("pages", {}).values())


for q in QUERIES:
    kept = 0
    try:
        pages = search(q)
    except Exception as exc:
        print("search failed", q, exc)
        continue
    pages.sort(key=lambda p: -((p.get("imageinfo") or [{}])[0].get("width", 0) or 0))
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        title = page.get("title", "")
        meta = info.get("extmetadata", {}) or {}
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        mime = info.get("mime", "")
        if title in seen or not info.get("url"):
            continue
        low = title.lower()
        if any(w in low for w in SKIP_WORDS) or not lic or not any(k in lic.lower() for k in OK_LICENSES):
            continue
        if mime not in ("image/jpeg", "image/png", "image/svg+xml") or (info.get("width", 0) or 0) < 900:
            continue
        url = info["url"] if mime == "image/svg+xml" else (info.get("thumburl") or info["url"])
        try:
            r = session.get(url, timeout=60)
            if not r.ok:
                continue
        except Exception as exc:
            print("download failed", title, exc)
            continue
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/svg+xml": ".svg"}[mime]
        name = re.sub(r"[^a-zA-Z0-9]+", "_", title.replace("File:", "")).strip("_")[:90] + ext
        (OUT / name).write_bytes(r.content)
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", "")).strip()
        refs.append({"file": name, "title": title, "query": q, "license": lic, "artist": artist,
                     "description_url": info.get("descriptionurl"), "width": info.get("width"), "height": info.get("height"), "mime": mime})
        seen.add(title)
        kept += 1
        print(f"kept  {lic:14} {name}")
        time.sleep(0.6)
        if kept >= MAX_PER_QUERY:
            break
    print(f"{q!r}: kept {kept}")

(OUT / "refs.json").write_text(json.dumps(refs, indent=1), encoding="utf-8")
print("saved", len(refs), "files to", OUT)
