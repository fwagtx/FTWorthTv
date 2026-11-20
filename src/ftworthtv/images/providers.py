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
    a = re.sub(r"\s*assumed\s*\(based on copyright claims\)\.?", "", a, flags=re.I)
    a = re.sub(r"^User:", "", a.strip())
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
        if any(bad in title for bad in ("map", "logo", "flag", "diagram", "seal", "icon", "chart", "plan", ".svg", ".gif", "poster")):
            continue
        out.append(PhotoCandidate(
            id=f"commons-{page.get('pageid')}", url=url,
            credit=f"Photo: {artist} via Wikimedia Commons ({lic})",
            license="wikimedia-cc", provider="wikimedia", source_url=info.get("descriptionurl", "https://commons.wikimedia.org"),
            width=int(info.get("width", 0)), height=int(info.get("height", 0)),
            alt=strip_html((meta.get("ImageDescription", {}) or {}).get("value", ""))[:200],
            title=re.sub(r"\.(jpe?g|png|webp|tiff?)$", "", str(page.get("title", "")).replace("File:", "")).replace("_", " ")[:200],
        ))
    return out


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
    payload = http.get_json(OPENVERSE_API, params={"q": query, "license_type": "commercial", "page_size": page_size, "mature": "false"}, headers=headers)
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
            title=(ph.get("title") or "")[:200],
        ))
    return out


def search_flickr(query: str, api_key: str, *, per_page: int = 20) -> list[PhotoCandidate]:
    payload = http.get_json(FLICKR_API, params={
        "method": "flickr.photos.search", "api_key": api_key, "text": query, "license": "4,5,7,9,10", "sort": "relevance",
        "content_type": 1, "safe_search": 1, "media": "photos", "extras": "url_l,url_c,owner_name,license", "per_page": per_page,
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
    return _candidates_from_pages(http.get_json(COMMONS_API, params=params))


def search_wikimedia_category(category: str, *, limit: int = 25) -> list[PhotoCandidate]:
    """Files in a Commons category, e.g. 'Dickies Arena': the building itself, not a full-text match on a description."""
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "categorymembers", "gcmtitle": f"Category:{category}", "gcmtype": "file", "gcmlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1800,
    }
    return _candidates_from_pages(http.get_json(COMMONS_API, params=params))


PERFORMANCE_WORDS = ("concert", "live", "performing", "performs", "tour", "festival", "show", "gig", "on stage", "onstage")
UNSAFE_PHOTO_WORDS = ("lingerie", "bikini", "nude", "naked", "sexy", "underwear", "playboy", "strip", "topless", "swimsuit", "lfl",
                      "porn", "erotic", "fetish", "lap dance", "hooters", "burlesque", "corpse", "dead body", "gore", "nazi", "kkk")


def unsafe_photo(cand: "PhotoCandidate") -> bool:
    blob = " ".join([cand.alt or "", cand.credit or "", cand.source_url or "", cand.url or ""]).lower()
    return any(w in blob for w in UNSAFE_PHOTO_WORDS)


def provider_order(settings) -> list[str]:
    cfg = (settings.brand.get("photos", {}) or {}).get("providers") if hasattr(settings, "brand") else None
    return list(cfg or DEFAULT_PROVIDER_ORDER)


def _search(query: str, settings) -> list[PhotoCandidate]:
    if query.lower().startswith("category:"):   # Commons category lookup (venues, landmarks)
        try:
            return search_wikimedia_category(query.split(":", 1)[1].strip())
        except Exception as exc:
            log.warning("wikimedia category failed for %r: %s", query, exc)
            return []
    if query.lower().startswith("fresh:"):      # newest Commons uploads about the subject first (events, games, ceremonies)
        try:
            return search_wikimedia(query.split(":", 1)[1].strip(), fresh=True)
        except Exception as exc:
            log.warning("wikimedia fresh search failed for %r: %s", query, exc)
            return []
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
        if not fn:
            continue
        try:
            found = fn()
        except Exception as exc:
            log.warning("%s search failed for %r: %s", name, query, exc)
            continue
        if found:
            log.info("photo: %s gave %d result(s) for %r", name, len(found), query)
            return found
    return []


def find_photo(query: "str | list[str]", settings, state: State | None = None, exclude: set[str] | None = None,
               avoid_words: tuple[str, ...] = (), fallback: bool = True) -> PhotoCandidate | None:
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
        for cand in _search(q, settings):
            if unsafe_photo(cand):
                continue
            if exclude and (cand.id in exclude or cand.family in exclude):
                continue
            name = cand.source_url.rsplit("/", 1)[-1].lower().replace("_", " ")
            titled = name + " " + (cand.title or "").lower()
            if avoid and (any(w in titled for w in avoid) or " - " in titled):   # "Artist - Venue, 2022.jpg" is a performance photo
                continue
            plain = " " + re.sub(r"[\s_\-,.:;()'’\"]+", " ", titled).strip() + " "    # "Ty_Myers_2025.jpg" -> " ty myers 2025 jpg "
            if avoid_words:
                blob = " ".join([name, cand.alt or "", cand.credit or "", cand.url or ""]).lower()
                if any(w in blob for w in avoid_words):
                    continue
            if require and not all(f" {w} " in plain for w in require):   # the subject, whole and in order, in the file name or its title
                continue
            if state and state.photo_recently_used(cand.id):
                continue
            return cand
    return None
