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
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
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
            width=int(p.get("width", 0)), height=int(p.get("height", 0)), alt=p.get("alt", "") or "",
        ))
    return out


def search_wikimedia(query: str, *, limit: int = 15) -> list[PhotoCandidate]:
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1800,
    }
    payload = http.get_json(COMMONS_API, params=params)
    out: list[PhotoCandidate] = []
    for page in (payload.get("query", {}) or {}).get("pages", []) or []:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {}) or {}
        lic = strip_html((meta.get("LicenseShortName", {}) or {}).get("value", "")).strip()
        if not lic or not lic.lower().startswith(OK_LICENSES) or "nc" in lic.lower() or "nd" in lic.lower():
            continue
        artist = strip_html((meta.get("Artist", {}) or {}).get("value", "")) or "Wikimedia Commons contributor"
        url = info.get("thumburl") or info.get("url")
        title = str(page.get("title", "")).lower()
        if not url or int(info.get("width", 0)) < 1000:
            continue
        if any(bad in title for bad in ("map", "logo", "flag", "diagram", "seal", "icon", "chart", "plan", ".svg", ".gif", "poster")):
            continue
        out.append(PhotoCandidate(
            id=f"commons-{page.get('pageid')}", url=url,
            credit=f"Photo: {artist[:60]} via Wikimedia Commons ({lic})",
            license="wikimedia-cc", provider="wikimedia", source_url=info.get("descriptionurl", "https://commons.wikimedia.org"),
            width=int(info.get("width", 0)), height=int(info.get("height", 0)),
            alt=strip_html((meta.get("ImageDescription", {}) or {}).get("value", ""))[:200],
        ))
    return out


def _search(query: str, settings) -> list[PhotoCandidate]:
    candidates: list[PhotoCandidate] = []
    if settings.pexels_api_key:
        try:
            candidates = search_pexels(query, settings.pexels_api_key)
        except Exception as exc:
            log.warning("pexels search failed for %r: %s", query, exc)
    if not candidates:
        try:
            candidates = search_wikimedia(query)
        except Exception as exc:
            log.warning("wikimedia search failed for %r: %s", query, exc)
    return candidates


def find_photo(query: str, settings, state: State | None = None, exclude: set[str] | None = None) -> PhotoCandidate | None:
    """Pexels first (best quality, simplest license), Wikimedia Commons as the fallback.

    Tries the writer's query, then generic city queries, and skips photos used earlier in this run or recently posted.
    """
    city = settings.brand.get("city", "Fort Worth")
    queries = [query or "", f"{city} skyline", f"{city} Texas downtown"]
    tried: set[str] = set()
    for q in queries:
        q = re.sub(r"\s+", " ", q).strip()
        if not q or q.lower() in tried:
            continue
        tried.add(q.lower())
        for cand in _search(q, settings):
            if exclude and cand.id in exclude:
                continue
            if state and state.photo_recently_used(cand.id):
                continue
            return cand
    return None
