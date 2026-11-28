"""Licensed, real photos we are allowed to post natively: Pexels (free commercial license) and Wikimedia Commons (CC)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .. import http
from ..state import State
from ..textutil import strip_html

log = logging.getLogger(__name__)

PEXELS_API = "https://api.pexels.com/v1/search"
UNSPLASH_API = "https://api.unsplash.com/search/photos"
PIXABAY_API = "https://pixabay.com/api/"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
OPENVERSE_TOKEN_API = "https://api.openverse.org/v1/auth_tokens/token/"
FLICKR_API = "https://www.flickr.com/services/rest/"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FLICKR_LICENSES = {"4": "CC BY 2.0", "5": "CC BY-SA 2.0", "7": "No known copyright restrictions", "9": "CC0", "10": "Public Domain Mark"}
OPENVERSE_OK = ("cc0", "pdm", "by", "by-sa")
DEFAULT_PROVIDER_ORDER = ["pexels", "unsplash", "flickr", "pixabay", "openverse", "wikimedia"]
OK_LICENSES = ("cc by", "cc0", "public domain", "pd", "cc-by", "no restrictions")


@dataclass
class PhotoCandidate:
    id: str
    url: str            # direct image URL to download
    credit: str         # human credit line
    license: str
    provider: str
    source_url: str     # page to link in the credit
    width: int = 0
    height: int = 0
    alt: str = ""
    title: str = ""     # the file's own title (what the uploader called it); descriptions are never trusted for the subject
    taken: str = ""     # when the picture was taken, if the file says (Commons DateTimeOriginal), "YYYY-MM-DD..."
    download_hook: str | None = None   # Unsplash: URL to ping when the photo is used

    @property
    def family(self) -> str:
        """Same photo in another crop/size ("Foo.jpg" vs "Foo (cropped).jpg") should count as the same photo."""
        name = self.source_url.rsplit("/", 1)[-1].lower()
        name = re.sub(r"\.(jpe?g|png|webp|tiff?)$", "", name)
        name = re.sub(r"[_(\s-]*(cropped|crop|edit(ed)?|retouched|\d+px)[_)\s-]*", "", name)
        return re.sub(r"[^a-z0-9]", "", name) or self.id


def search_pexels(query: str, api_key: str, *, per_page: int = 15, orientation: str = "portrait") -> list[PhotoCandidate]:
    payload = http.get_json(PEXELS_API, params={"query": query, "per_page": per_page, "orientation": orientation},
                            headers={"Authorization": api_key})
    out: list[PhotoCandidate] = []
    for p in payload.get("photos", []) or []:
        src = p.get("src", {}) or {}
        url = src.get("large2x") or src.get("original")
        if not url:
            continue
        out.append(PhotoCandidate(
            id=f"pexels-{p.get('id')}", url=url,
            credit=f"Photo: {p.get('photographer', 'Pexels photographer')} via Pexels",
            license="pexels", provider="pexels", source_url=p.get("url", "https://www.pexels.com"),
            width=int(p.get("width", 0)), height=int(p.get("height", 0)), alt=p.get("alt", "") or "", title=p.get("alt", "") or "",
        ))
    return out


def _clean_artist(raw: str) -> str:
    a = strip_html(raw or "")
    a = re.sub(r"No machine-readable author provided\.?", "", a, flags=re.I)
    a = re.sub(r"\s*assumed\s*\(based on copyright(?: claims\)\.?| ?\w*)", "", a, flags=re.I)      # also the form a 60-char cut leaves behind
    a = re.sub(r"^User:", "", a.strip())
    a = re.sub(r"^(?:photos?|photograph(?:ed)?|foto|image|picture)\s*(?:by|:)\s*", "", a, flags=re.I)   # "Photo: Andreas Praefcke" (Nov 23)
    a = re.sub(r"^original uploader was\s+", "", a, flags=re.I)                    # "Original uploader was Hequalstohenry of
    a = re.sub(r"\s+(?:of|at)\s+[a-z]{2,3}\.wikipedia\b.*$", "", a, flags=re.I)  #  en.wikipedia" (Nov 23)
    a = re.sub(r"\s*\(talk\)", "", a)
    a = re.sub(r"\S+@\S+\.\w+", "", a)                       # e-mail addresses some uploaders put in the author field
    a = re.sub(r"\s+from\s+[A-Z][\w.]*(?:[ ,]+[A-Z][\w.]*)*\s*$", "", a)   # "Jane Doe from Austin, Texas. USA"
    a = re.sub(r"\s+from\s+[A-Z][\w.]*(?:[ ,]+[A-Z][\w.]*)*(?=\s|$)", "", a)
    a = re.sub(r"\s{2,}", " ", a).strip(" .,-")
    return a[:60] or "Wikimedia Commons contributor"


def _candidates_from_pages(payload: dict) -> list[PhotoCandidate]:
    out: list[PhotoCandidate] = []
    for page in (payload.get("query", {}) or {}).get("pages", []) or []:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {}) or {}
        lic = strip_html((meta.get("LicenseShortName", {}) or {}).get("value", "")).strip()
        if not lic or not lic.lower().startswith(OK_LICENSES) or "nc" in lic.lower() or "nd" in lic.lower():
            continue
        artist = _clean_artist((meta.get("Artist", {}) or {}).get("value", ""))
        url = info.get("thumburl") or info.get("url")
        title = str(page.get("title", "")).lower()
        if not url or int(info.get("width", 0)) < 1000:
            continue
        if any(bad in title for bad in ("map", "logo", "flag", "diagram", "seal", "icon", "chart", "plan", ".svg", ".gif", ".png", "poster", "graphic",
                                        "infographic", "flyer", "banner", "awareness")):
            continue
        if re.search(r"\b(graphic|illustration|infographic|poster)\b", artist, re.I):     # "U.S. Navy graphic by ...": a poster, not a picture
            continue
        out.append(PhotoCandidate(
            id=f"commons-{page.get('pageid')}", url=url,
            credit=f"Photo: {artist} via Wikimedia Commons ({lic})",
            license="wikimedia-cc", provider="wikimedia", source_url=info.get("descriptionurl", "https://commons.wikimedia.org"),
            width=int(info.get("width", 0)), height=int(info.get("height", 0)),
            alt=strip_html((meta.get("ImageDescription", {}) or {}).get("value", ""))[:200],
            title=re.sub(r"\.(jpe?g|png|webp|tiff?)$", "", str(page.get("title", "")).replace("File:", "")).replace("_", " ")[:200],
            taken=iso_date(strip_html((meta.get("DateTimeOriginal", {}) or {}).get("value", ""))),
        ))
    return out


_ISO_DATE_RE = re.compile(r"\b((?:19|20)\d{2})[-:/.](\d{1,2})[-:/.](\d{1,2})\b")
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def iso_date(raw: str) -> str:
    """Commons writes DateTimeOriginal as '2016-07-11 14:22', '2016:07:11', 'July 11, 2016' or 'circa 2016'. Only an ISO
    date compares with a date bar: Nov 22, 'July 11, 2016' sorted after '2026-11-08' (letters sort after digits) and a
    2016 photo of Sonny Dykes in a Cal polo passed as a picture from the week TCU fired him. Returns 'YYYY-MM-DD' or ''."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = _ISO_DATE_RE.search(raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    if not _YEAR_RE.search(raw):
        return ""
    from datetime import datetime as _dt
    from dateutil import parser as _p
    try:
        when = _p.parse(raw, fuzzy=True, default=_dt(1900, 1, 1))
    except (ValueError, OverflowError):
        years = _YEAR_RE.findall(raw)
        return f"{years[-1]}-01-01" if years else ""
    return when.date().isoformat() if when.year >= 1900 else ""


# ---- Unsplash (free key: unsplash.com/developers; license: free commercial use, credit requested) ----
def parse_unsplash(payload: dict) -> list[PhotoCandidate]:
    out = []
    for r in payload.get("results", []) or []:
        urls = r.get("urls", {}) or {}
        url = urls.get("regular") or urls.get("full")
        if not url:
            continue
        user = r.get("user", {}) or {}
        out.append(PhotoCandidate(
            id=f"unsplash-{r.get('id')}", url=url, credit=f"Photo: {user.get('name', 'Unsplash photographer')} on Unsplash",
            license="unsplash", provider="unsplash", source_url=(r.get("links", {}) or {}).get("html", "https://unsplash.com"),
            width=int(r.get("width", 0)), height=int(r.get("height", 0)), alt=(r.get("alt_description") or "")[:200],
            title=(r.get("description") or r.get("alt_description") or "")[:200],
        ))
        out[-1].download_hook = (r.get("links", {}) or {}).get("download_location")  # Unsplash asks apps to ping this on use
    return out


def search_unsplash(query: str, access_key: str, *, per_page: int = 15, orientation: str = "portrait") -> list[PhotoCandidate]:
    payload = http.get_json(UNSPLASH_API, params={"query": query, "per_page": per_page, "orientation": orientation, "content_filter": "high"},
                            headers={"Authorization": f"Client-ID {access_key}", "Accept-Version": "v1"})
    return parse_unsplash(payload)


# ---- Pixabay (free key: pixabay.com/api/docs; Pixabay Content License: free commercial use) ----
def parse_pixabay(payload: dict) -> list[PhotoCandidate]:
    out = []
    for h in payload.get("hits", []) or []:
        url = h.get("largeImageURL") or h.get("webformatURL")
        if not url:
            continue
        out.append(PhotoCandidate(
            id=f"pixabay-{h.get('id')}", url=url, credit=f"Photo: {h.get('user', 'Pixabay contributor')} via Pixabay",
            license="pixabay", provider="pixabay", source_url=h.get("pageURL", "https://pixabay.com"),
            width=int(h.get("imageWidth", 0)), height=int(h.get("imageHeight", 0)), alt=(h.get("tags") or "")[:200],
        ))
    return out


def search_pixabay(query: str, api_key: str, *, per_page: int = 20, orientation: str = "vertical") -> list[PhotoCandidate]:
    payload = http.get_json(PIXABAY_API, params={"key": api_key, "q": query, "image_type": "photo", "orientation": orientation,
                                                 "per_page": per_page, "safesearch": "true"})
    return parse_pixabay(payload)


# ---- Openverse (no key needed; aggregates Flickr/Wikimedia/etc. Creative Commons photos) ----
_openverse_token: dict = {}


def _openverse_headers(settings) -> dict:
    cid, secret = getattr(settings, "openverse_client_id", None), getattr(settings, "openverse_client_secret", None)
    if not (cid and secret):
        return {}
    import time
    if _openverse_token.get("exp", 0) > time.time() + 60:
        return {"Authorization": f"Bearer {_openverse_token['token']}"}
    try:
        resp = http.session().post(OPENVERSE_TOKEN_API, data={"client_id": cid, "client_secret": secret, "grant_type": "client_credentials"}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        _openverse_token.update(token=data["access_token"], exp=time.time() + int(data.get("expires_in", 3600)))
        return {"Authorization": f"Bearer {data['access_token']}"}
    except Exception as exc:
        log.info("openverse token failed (continuing anonymously): %s", exc)
        return {}


def parse_openverse(payload: dict) -> list[PhotoCandidate]:
    out = []
    for r in payload.get("results", []) or []:
        lic = str(r.get("license", "")).lower()
        if lic not in OPENVERSE_OK or not r.get("url"):
            continue
        if int(r.get("width") or 0) and int(r.get("width") or 0) < 900:
            continue
        lic_label = {"cc0": "CC0", "pdm": "Public Domain", "by": "CC BY", "by-sa": "CC BY-SA"}[lic] + (f" {r.get('license_version')}" if r.get("license_version") and lic in ("by", "by-sa") else "")
        src = (r.get("source") or "openverse").replace("_", " ").title()
        out.append(PhotoCandidate(
            id=f"openverse-{r.get('id')}", url=r["url"], credit=f"Photo: {r.get('creator') or 'unknown'} ({lic_label}) via {src}",
            license="openverse-cc", provider="openverse", source_url=r.get("foreign_landing_url") or "https://openverse.org",
            width=int(r.get("width") or 0), height=int(r.get("height") or 0), alt=(r.get("title") or "")[:200],
            title=(r.get("title") or "")[:200],
        ))
    return out


def search_openverse(query: str, settings=None, *, page_size: int = 20) -> list[PhotoCandidate]:
    headers = _openverse_headers(settings) if settings is not None else {}
    payload = http.get_json(OPENVERSE_API, params={"q": query, "license_type": "commercial", "page_size": page_size, "mature": "false"}, headers=headers,
                            timeout=PROVIDER_TIMEOUT, quick=True)
    return parse_openverse(payload)


# ---- Flickr (free key: flickr.com/services/apps/create; CC-licensed photos only) ----
def parse_flickr(payload: dict) -> list[PhotoCandidate]:
    out = []
    for ph in (payload.get("photos", {}) or {}).get("photo", []) or []:
        url = ph.get("url_l") or ph.get("url_c")
        lic = FLICKR_LICENSES.get(str(ph.get("license")))
        if not url or not lic:
            continue
        out.append(PhotoCandidate(
            id=f"flickr-{ph.get('id')}", url=url, credit=f"Photo: {ph.get('ownername', 'Flickr user')} ({lic}) via Flickr",
            license="flickr-cc", provider="flickr", source_url=f"https://www.flickr.com/photos/{ph.get('owner')}/{ph.get('id')}",
            width=int(ph.get("width_l") or ph.get("width_c") or 0), height=int(ph.get("height_l") or ph.get("height_c") or 0), alt=(ph.get("title") or "")[:200],
            title=(ph.get("title") or "")[:200], taken=str(ph.get("datetaken") or ""),
        ))
    return out


def search_flickr(query: str, api_key: str, *, per_page: int = 20) -> list[PhotoCandidate]:
    payload = http.get_json(FLICKR_API, params={
        "method": "flickr.photos.search", "api_key": api_key, "text": query, "license": "4,5,7,9,10", "sort": "relevance",
        "content_type": 1, "safe_search": 1, "media": "photos", "extras": "url_l,url_c,owner_name,license,date_taken", "per_page": per_page,
        "format": "json", "nojsoncallback": 1})
    return parse_flickr(payload)


def search_wikimedia(query: str, *, limit: int = 15, fresh: bool = False) -> list[PhotoCandidate]:
    """Full-text search of Commons files; `fresh` asks for the newest uploads first, which is how a photo taken at
    yesterday's game or this morning's ceremony beats a ten-year-old file of the same building."""
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1800,
    }
    if fresh:
        params["gsrsort"] = "create_timestamp_desc"
    return _candidates_from_pages(http.get_json(COMMONS_API, params=params, timeout=PROVIDER_TIMEOUT, quick=True))


def search_wikimedia_category(category: str, *, limit: int = 25) -> list[PhotoCandidate]:
    """Files in a Commons category, e.g. 'Dickies Arena': the building itself, not a full-text match on a description."""
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "categorymembers", "gcmtitle": f"Category:{category}", "gcmtype": "file", "gcmlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1800,
    }
    return _candidates_from_pages(http.get_json(COMMONS_API, params=params, timeout=PROVIDER_TIMEOUT, quick=True))


PERFORMANCE_WORDS = ("concert", "live", "performing", "performs", "tour", "festival", "show", "gig", "on stage", "onstage")
UNSAFE_PHOTO_WORDS = ("lingerie", "bikini", "nude", "naked", "sexy", "underwear", "playboy", "strip", "topless", "swimsuit", "lfl",
                      "porn", "erotic", "fetish", "lap dance", "hooters", "burlesque", "corpse", "dead body", "gore", "nazi", "kkk")


_NOT_A_PHOTO_RE = re.compile(r"\b(screenshot|screen shot|screencap|screen capture|wallpaper|desktop background|desktop|schedule|launchpad|"
                             r"os x|mac ?os|windows \d+|ios \d+|user interface|gui|app icon|icons?|logo|wordmark|clip ?art|clipart|vector|"
                             r"mock-?up|meme|collage|poster|flyer|graphic|infographic|illustration|rendering|render|banner|jersey number|"
                             r"caricature|cartoon|satire|satirical|parody|political art|editorial cartoon|donkeyhotey|"
                             r"photoshop|photoshopped|manipulated|digital art|painting|drawing|"
                             # Nov 23: "Marvel" found a Scarlet Witch cosplayer at a fair in Bari for an Avengers: Doomsday story
                             r"cosplay|cosplayer|cosplayers|cosplaying|fan art|fanart|"
                             # Nov 24: "Toys R Us Backrooms Level.jpg", a liminal-space image, for a store opening in Fort Worth
                             r"backrooms|liminal|ai[- ]generated|generated by ai|midjourney|stable diffusion|dall-?e|creepypasta|"
                             # Nov 25: "Hispanic ancestry in Florida.jpg" was a county map for a story about Mesquite entrepreneurs
                             r"maps?|ancestry|demographics?|census|population density|by county|by state|choropleth|"
                             # Nov 27, render 319: "Average daily wind speed reagan national.png" (a NOAA plot) for two jets
                             # that clipped wings at Reagan National
                             r"average (?:daily|monthly|annual|yearly)|wind speeds?|precipitation|rainfall|climatolog\w*|"
                             r"climate data|histogram|plot|time series|trend line|data set|dataset|"
                             r"chart|graph|diagram|statistics|ambigram|calligraphy|typography|lettering|wordart|word art)\b", re.I)
# Nov 22, render 128: "Medicare" found DonkeyHotey's "Dr. Oz Is In Charge of Your Medicare and Medicaid. You Better Watch
# Out!", a caricature captioned "Medicare for All Sucks, Go Trumpcare!", for a Medicare counseling story
_OPINION_TITLE_RE = re.compile(r"[!?]|\byou better\b|\byour\b.{0,40}\b(?:watch out|beware)\b", re.I)


def not_a_photo(cand: "PhotoCandidate") -> bool:
    """A screenshot, a wallpaper or a schedule graphic is not a photograph of anything: Nov 21, "Mavericks" found an OS X
    Mavericks Launchpad screenshot, and "Dallas Cowboys" a 2010 schedule wallpaper stamped "photo property of the NFL"."""
    name = (cand.source_url or "").rsplit("/", 1)[-1].replace("_", " ").replace("%27", "'")
    blob = " ".join([name, cand.title or "", cand.alt or ""])
    title = cand.title or name
    if re.search(r"\bdonkeyhotey\b", cand.credit or "", re.I):
        return True                                           # a caricaturist's work, whatever its file is called
    return bool(_NOT_A_PHOTO_RE.search(blob)) or "property of" in blob.lower() or bool(_OPINION_TITLE_RE.search(title))


# an archive's account holds history, not today: Nov 24, "gasoline pump nozzle fueling car" found Orange County Archives'
# 1970s pump priced at 51.8 cents a gallon for FOX 4's "DFW gas prices drop below $3 ahead of Thanksgiving travel rush"
_ARCHIVE_RE = re.compile(r"\b(?:archives?|historical society|history center|history museum|heritage (?:society|center|collection)|"
                         r"library of congress|state library|digital collections?|special collections|vintage|retro|circa|"
                         r"(?:18|19)\d0s)\b", re.I)


STALE_PHOTO_YEARS = 10


def stale_photo(cand: "PhotoCandidate", year: int | None = None) -> bool:
    """A search photo more than ten years old is not today's picture: Nov 24, the gas-prices story drew a Flickr pump with
    "09/06/2010" burned into the frame. The taken date when the file has one, else a year in its title or file name."""
    from datetime import datetime
    bar = (year or datetime.now().year) - STALE_PHOTO_YEARS
    taken = iso_date(cand.taken)
    if taken:
        return int(taken[:4]) < bar
    name = (cand.source_url or "").rsplit("/", 1)[-1].replace("_", " ")
    years = [int(y) for y in re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", f"{cand.title or ''} {name}")]
    return bool(years) and max(years) < bar


_OTHER_PRODUCTION_RE = re.compile(r"\b(?:production of|school production|high school (?:musical|production|theat(?:re|er))|"
                                  r"community theat(?:re|er)|dinner theat(?:re|er)|summer stock|student production)\b", re.I)


def other_production(cand: "PhotoCandidate") -> bool:
    """A staging by another company (a school, a community theater) is not the tour coming to town."""
    name = (cand.source_url or "").rsplit("/", 1)[-1].replace("_", " ")
    return bool(_OTHER_PRODUCTION_RE.search(" ".join([cand.title or "", cand.alt or "", name])))


def archive_photo(cand: "PhotoCandidate") -> bool:
    name = (cand.source_url or "").rsplit("/", 1)[-1].replace("_", " ")
    return bool(_ARCHIVE_RE.search(" ".join([cand.credit or "", cand.title or "", cand.alt or "", name])))


def unsafe_photo(cand: "PhotoCandidate") -> bool:
    blob = " ".join([cand.alt or "", cand.credit or "", cand.source_url or "", cand.url or ""]).lower()
    return any(w in blob for w in UNSAFE_PHOTO_WORDS)


def provider_order(settings) -> list[str]:
    cfg = (settings.brand.get("photos", {}) or {}).get("providers") if hasattr(settings, "brand") else None
    return list(cfg or DEFAULT_PROVIDER_ORDER)


PROVIDER_TIMEOUT = (8, 15)           # connect, read: a photo search waits at most ~25 s, once
_PROVIDERS_DOWN: set[str] = set()    # providers that timed out this run (a render is one process)


SEARCH_BUDGET_S = 420                 # all photo searches of one render together: the workflow stops the job at 15 minutes
_search_started: list[float] = []


def _over_budget() -> bool:
    import time
    if not _search_started:
        _search_started.append(time.monotonic())
        return False
    if time.monotonic() - _search_started[0] > SEARCH_BUDGET_S:
        if "budget" not in _PROVIDERS_DOWN:
            _PROVIDERS_DOWN.add("budget")
            log.warning("photo searches used their %d s budget: the rest of this run uses the library or a text card", SEARCH_BUDGET_S)
        return True
    return False


def _is_timeout(exc: Exception) -> bool:
    import requests
    return isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)) or "timed out" in str(exc).lower()


def _search(query: str, settings) -> list[PhotoCandidate]:
    """The first provider's results for the query."""
    return next(_search_each(query, settings), [])


def _search_each(query: str, settings):
    """Each provider's results in turn, so find_photo can move on when none of one provider's files will do: Nov 24,
    Openverse's 15 results for "U2" were Dublin graffiti walls, a spy plane and 2005-2009 concerts, while Commons had
    U2 on tour in 2018 and at the Sphere in 2023."""
    if query.lower().startswith(("category:", "fresh:", "commons:")) and "wikimedia" in _PROVIDERS_DOWN:
        return
    if _over_budget():
        return
    if query.lower().startswith("commons:"):    # Commons only: "commons:U2 2024" (a subject's recent files, see plan_image)
        try:
            found = search_wikimedia(query.split(":", 1)[1].strip())
        except Exception as exc:
            log.warning("wikimedia search failed for %r: %s", query, exc)
            if _is_timeout(exc):
                _PROVIDERS_DOWN.add("wikimedia")
            return
        if found:
            log.info("photo: wikimedia gave %d result(s) for %r", len(found), query)
            yield found
        return
    if query.lower().startswith("category:"):   # Commons category lookup (venues, landmarks)
        try:
            found = search_wikimedia_category(query.split(":", 1)[1].strip())
        except Exception as exc:
            log.warning("wikimedia category failed for %r: %s", query, exc)
            if _is_timeout(exc):
                _PROVIDERS_DOWN.add("wikimedia")
            return
        if found:
            yield found
        return
    if query.lower().startswith("fresh:"):      # newest Commons uploads about the subject first (events, games, ceremonies)
        try:
            found = search_wikimedia(query.split(":", 1)[1].strip(), fresh=True)
        except Exception as exc:
            log.warning("wikimedia fresh search failed for %r: %s", query, exc)
            if _is_timeout(exc):
                _PROVIDERS_DOWN.add("wikimedia")
            return
        if found:
            yield found
        return
    keyed = {
        "pexels": lambda: search_pexels(query, settings.pexels_api_key) if settings.pexels_api_key else [],
        "unsplash": lambda: search_unsplash(query, settings.unsplash_access_key) if getattr(settings, "unsplash_access_key", None) else [],
        "flickr": lambda: search_flickr(query, settings.flickr_api_key) if getattr(settings, "flickr_api_key", None) else [],
        "pixabay": lambda: search_pixabay(query, settings.pixabay_api_key) if getattr(settings, "pixabay_api_key", None) else [],
        "openverse": lambda: search_openverse(query, settings),
        "wikimedia": lambda: search_wikimedia(query),
    }
    for name in provider_order(settings):
        fn = keyed.get(name)
        if not fn or name in _PROVIDERS_DOWN or _over_budget():
            continue
        try:
            found = fn()
        except Exception as exc:
            log.warning("%s search failed for %r: %s", name, query, exc)
            if _is_timeout(exc):
                _PROVIDERS_DOWN.add(name)     # Nov 22: Openverse answering in minutes ran a render past its 15-minute limit
                log.warning("%s is not answering: no more %s searches this run", name, name)
            continue
        if found:
            log.info("photo: %s gave %d result(s) for %r", name, len(found), query)
            yield found


# iNaturalist imports on Commons are named "Genus species 123456789.jpg": a species record, never a person or a character
_SPECIES_FILE_RE = re.compile(r"^(?:file:)?[a-z]+ [a-z]+(?: [a-z]+)? \(?\d{5,}\)?\.(?:jpe?g|png|webp)$")


# a picture of one event is that event: Nov 24, "NEX Atsugi Toys R Us Grand Opening" (Navy officers at a Navy Exchange shop in
# Japan) for a Toys "R" Us opening at Tanger Outlets Fort Worth
_EVENT_PHOTO_RE = re.compile(r"\b(?:grand opening|ribbon[- ]cutting|groundbreaking|ground breaking|ceremony|dedication|opening day|"
                             r"unveiling|parade|festival)\b", re.I)
_PLACE_STOP = {"the", "a", "an", "of", "at", "in", "on", "and", "for", "with", "by", "to", "from", "jpg", "jpeg", "png", "file",
               "photo", "grand", "opening", "ribbon", "cutting", "groundbreaking", "ground", "breaking", "ceremony", "dedication",
               "day", "unveiling", "parade", "festival", "new", "store", "shop", "celebrates", "celebration", "held", "hosts",
               # what a picture of a store shows, not where it is: "Toys R Us storefront" names no other place
               "storefront", "exterior", "interior", "entrance", "front", "facade", "sign", "signage", "building", "inside",
               "outside", "aisle", "aisles", "display", "displays", "shelves", "department", "location", "outlet"}


# a file that opens with a person's name is a portrait of that person: Nov 25, "Annie E. Andrews, Esquire American Lawyer and
# Juvenile Justice Advocate" (a South Carolina lawyer) came back for "Juvenile Justice" on a story about Texas's former juvenile
# justice director, a different woman. A venue named for a person ("Amon G. Carter Stadium") is not a portrait.
# Nov 27, render 302: 'John "Doomsday" Howard in 2025' (a fighter) went out for IGN's Avengers: Doomsday teaser: a nickname in
# quotes between the names is still a person's portrait
_PERSON_START_RE = re.compile(r"^(?:File:)?\s*([A-Z][a-z]+)(?: ([A-Z])\.?)?(?: [\"“'‘][^\"”'’]{1,24}[\"”'’])? "
                              r"([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b(?!['’]s)"
                              r"(?!\s+(?:Stadium|Center|Centre|Hall|Park|Building|Museum|School|University|College|Field|Arena|"
                              r"Library|Bridge|Street|Avenue|Boulevard|Road|Tower|House|Church|Plaza|Theater|Theatre|Airport|Lake|"
                              r"River|County|Elementary|High|Middle|Memorial|Hospital|Courthouse|Gardens?|Zoo|Station|Square)\b)")
_NOT_A_FIRST_NAME = {"fort", "san", "new", "las", "los", "el", "north", "south", "east", "west", "lake", "mount", "saint", "st",
                     "downtown", "texas", "dallas", "houston", "austin", "the", "big", "old", "grand", "royal", "white", "red"}
_NOT_A_SURNAME = {"skyline", "downtown", "street", "night", "sunset", "sunrise", "aerial", "view", "panorama", "exterior",
                  "interior", "building", "stadium", "entrance", "sign", "logo", "map", "flag", "seal", "store", "shop", "mall"}


def unnamed_person_photo(title: str, query: str, story_text: str) -> bool:
    """The file is a portrait of a person whom neither the story nor the search names."""
    m = _PERSON_START_RE.match((title or "").strip())
    if not m or not story_text:
        return False
    first, last = m.group(1), m.group(3)
    if first.lower() in _NOT_A_FIRST_NAME or last.lower() in _NOT_A_SURNAME:
        return False
    low = f"{story_text} {query or ''}".lower()
    return last.lower() not in low


# an opening is one place: Nov 24, "Toys R Us department in Macy's Center City Philadelphia" went out for the Toys "R" Us pop-up
# that opened at Tanger Outlets Fort Worth. For a story about a store, restaurant or branch opening, a file titled with somewhere
# the story never names is another location of the brand.
_OPENING_STORY_RE = re.compile(r"\b(?:opens?|opened|opening|debuts?|debuted|reopens?|reopened|unveils?|unveiled|launch(?:es|ed)?)\b"
                               r"[^.]{0,60}?\b(?:store|shop|pop-?up|location|restaurant|branch|outlet|bar|cafe|café|eatery|taproom|"
                               r"brewery|gym|clinic|dealership|showroom|market|grocery|supermarket|boutique|bakery|diner|salon|"
                               r"headquarters|hq|office|campus|warehouse|plant|factory|center)\b|\bpop-?up (?:store|shop)\b|"
                               r"\bnew location\b|\bnow open\b", re.I)


# a company's building is not its news: Nov 25, "SpaceX hangar at LC39A, Kennedy Space Center" (Florida) for CBS News Texas's
# "SpaceX gets FCC approval for 1 million satellites to build data centers in space" (and on Nov 24 for SpaceX debris in Mexico)
_FACILITY_RE = re.compile(r"\b(?:hangar|hangars|headquarters|hq|office building|offices|facility|facilities|plant|warehouse|factory|"
                          r"campus|distribution center|fulfillment center|corporate office)\b", re.I)


def facility_for_other_news(title: str, story_text: str) -> bool:
    """The file is a company's building, and the story's headline is not about a building."""
    if not story_text or not _FACILITY_RE.search(title or ""):
        return False
    head = story_text[:200]
    return not _FACILITY_RE.search(head) and not re.search(r"\b(?:building|site|location|opens?|opening|expan\w+|construction|"
                                                           r"moves?|relocat\w+|closes?|closing)\b", head, re.I)


# a file titled "X v. Y" shows that match: Nov 26, render 268, "Levi's Stadium 2026 FIFA World Cup Australia v. Paraguay" for
# ESPN's USWNT qualifier story (the USWNT plays El Salvador in Mansfield)
_MATCH_TITLE_RE = re.compile(r"\b([A-Za-z][\w.'’-]+) (?:v|vs)\.? ([A-Z][\w.'’-]+)")


def other_event_photo(titled: str, query: str, story_text: str) -> bool:
    """The file shows a named event ("grand opening") somewhere the story never mentions, or, for a story about something
    opening, another location of the same brand, or a match between two teams the story never names."""
    m = _MATCH_TITLE_RE.search(titled or "")
    if m and story_text:
        low = story_text.lower()
        if not any(team.lower().strip(".") in low for team in (m.group(1), m.group(2))):
            return True
    if not story_text or not (_EVENT_PHOTO_RE.search(titled) or _OPENING_STORY_RE.search(story_text[:300])):
        return False
    subject = set(re.findall(r"[a-z0-9]+", (query or "").lower()))
    words = {w for w in re.findall(r"[a-z]{3,}", titled.lower()) if w not in _PLACE_STOP and w not in subject}
    story = set(re.findall(r"[a-z]{3,}", story_text.lower()))
    return bool(words) and not (words & story)


# Nov 26, render 286: KXAN's "Texas football grateful ahead of Texas A&M game" drew "Texas A&M Women's Volleyball at White House
# 2026": another sport, the opponent, and a visit to the White House the story never mentions
_SPORT_NAMES = ("football", "basketball", "baseball", "softball", "volleyball", "soccer", "hockey", "golf", "tennis", "swimming",
                "wrestling", "gymnastics", "lacrosse", "rowing", "rodeo", "track and field", "cross country")


def other_sport_photo(titled: str, story_text: str) -> bool:
    """The file shows a sport the story is not about (volleyball for a football story), or a team's White House visit that the
    story never mentions."""
    t, s = (titled or "").lower(), (story_text or "").lower()
    if not s:
        return False
    in_file = {x for x in _SPORT_NAMES if re.search(r"\b" + re.escape(x) + r"\b", t)}
    in_story = {x for x in _SPORT_NAMES if re.search(r"\b" + re.escape(x) + r"\b", s)}
    if in_file and in_story and not (in_file & in_story):
        return True
    return bool(re.search(r"\bwhite house\b", t)) and "white house" not in s


def find_photo(query: "str | list[str]", settings, state: State | None = None, exclude: set[str] | None = None,
               avoid_words: tuple[str, ...] = (), fallback: bool = True, taken_after: str = "",
               story_text: str = "") -> PhotoCandidate | None:
    """Pexels first (best quality, simplest license), Wikimedia Commons as the fallback.

    Tries the given query/queries in order, then generic city queries, and skips photos used earlier in this run or recently
    posted. `avoid_words` are place names the photo must not be labelled with (a "Texas skyline" hit that is really Houston).
    """
    city = settings.brand.get("city", "Fort Worth")
    base = [query] if isinstance(query, str) else list(query or [])
    queries = [q or "" for q in base] + ([f"{city} skyline", f"{city} Texas downtown"] if fallback else [])
    tried: set[str] = set()
    for item in queries:
        avoid: tuple[str, ...] = ()
        require: tuple[str, ...] = ()
        if isinstance(item, tuple):  # (query, words that disqualify a file name[, words the file name must contain])
            require = tuple(item[2]) if len(item) > 2 else ()
            item, avoid = item[0], tuple(item[1])
        q = re.sub(r"\s+", " ", item or "").strip()
        if not q or q.lower() in tried:
            continue
        tried.add(q.lower())
        for cand in (c for found in _search_each(q, settings) for c in found):
            if unsafe_photo(cand) or not_a_photo(cand) or archive_photo(cand) or stale_photo(cand) or other_production(cand):
                continue
            if exclude and (cand.id in exclude or cand.family in exclude):
                continue
            name = cand.source_url.rsplit("/", 1)[-1].lower().replace("_", " ")
            titled = name + " " + (cand.title or "").lower()
            if "inaturalist" in avoid and _SPECIES_FILE_RE.match(name):
                continue                  # Nov 24: "Acacia cyclops 452574694.jpg" (seed pods) for the X-Men's Cyclops
            if other_event_photo(name + " " + (cand.title or ""), q, story_text):
                continue                  # another place's grand opening is not this one
            if other_sport_photo(name + " " + (cand.title or ""), story_text):
                continue                  # a volleyball team at the White House is not a football story
            if unnamed_person_photo(cand.title or cand.source_url.rsplit("/", 1)[-1].replace("_", " "), q, story_text):
                continue                  # a stranger's portrait: the worst mistake a page can make
            if facility_for_other_news(cand.title or cand.source_url.rsplit("/", 1)[-1].replace("_", " "), story_text):
                continue                  # a company's hangar is not its satellite approval
            if avoid and (any(w in titled for w in avoid) or " - " in titled):   # "Artist - Venue, 2022.jpg" is a performance photo
                continue
            plain = " " + re.sub(r"[\s_\-,.:;()'’\"]+", " ", titled).strip() + " "    # "Ty_Myers_2025.jpg" -> " ty myers 2025 jpg "
            if avoid_words:
                blob = " ".join([name, cand.alt or "", cand.credit or "", cand.url or ""]).lower()
                if any(w in blob for w in avoid_words):
                    continue
            if require and not all(any(f" {alt} " in plain for alt in w.split("|")) for w in require):
                continue                                      # the subject, whole and in order, in the file name or its title ("hippo|hippopotamus")
            if taken_after:                                   # an event wants a picture from the event, not from years ago
                taken = iso_date(cand.taken)
                if not taken or taken < taken_after:
                    continue
                if any(int(y) < int(taken_after[:4]) for y in _YEAR_RE.findall(titled)):
                    continue                                  # "Sonny Dykes at 2016 Bay Area College Football Media Day.jpg"
            if state and state.photo_recently_used(cand.id):
                continue
            return cand
    return None
