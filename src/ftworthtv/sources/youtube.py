"""New videos from public YouTube channels (the city, the police, the stations, the teams), read from each channel's
public Atom feed. Nothing is downloaded: the post carries the YouTube link, which Facebook renders as a playable embed
credited to the channel. Instagram gets no link posts, so these go to Facebook only.

config/sources.yaml:
    youtube:
      enabled: true
      max_per_day: 4
      channels:
        - {name: City of Fort Worth, id: UC..., always_relevant: true, category_hint: community, weight: 0.9}
        - {name: FOX 4 Dallas-Fort Worth, id: UC..., weight: 0.7}      # kept only when the title names Fort Worth / the tiers match
"""
from __future__ import annotations

import re

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

from dateutil import parser as dtparse

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import collapse_ws, stable_id, truncate

log = logging.getLogger(__name__)

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={id}"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
SKIP_TITLE = ("live stream", "livestream", "#live", "live:", "watch live", "full game", "full episode", "full show")


PLACE_WORDS = ("fort worth", "ft. worth", "ft worth", "tarrant", "tcu", "arlington", "keller", "southlake", "mansfield", "grand prairie",
               "burleson", "haslet", "north richland hills", "hurst", "euless", "bedford", "grapevine", "weatherford", "benbrook",
               "white settlement", "saginaw", "crowley", "azle", "colleyville", "watauga", "forest hill", "river oaks", "lake worth",
               "aledo", "roanoke", "trophy club", "westlake", "dfw", "dallas-fort worth", "dallas/fort worth", "north texas",
               "metroplex", "cowtown", "panther island", "stockyards", "alliance airport", "dickies arena", "globe life", "at&t stadium")
# a station's video must name our side of the Metroplex or the region as a whole: "Dallas", "Denton" or "Texas" alone is
# not enough (a crash into a Dallas home or a Dallas ISD vote is not Fort Worth news, however good the video)
_CHANNEL_SUFFIX = re.compile(r"\s*[|–-]\s*(?:[^|–-]*\b(?:nbc|fox|wfaa|cbs|kera|news|dfw|weather update)\b[^|–-]*)$", re.I)


def place_text(title: str) -> str:
    """The title without a trailing station tag: 'Car crashes into Dallas home | NBC DFW' must not pass on 'DFW'."""
    return _CHANNEL_SUFFIX.sub("", title or "").strip()


REGIONAL_WORDS = ("dfw", "dallas-fort worth", "dallas/fort worth", "north texas", "metroplex")


def names_our_place(title: str) -> bool:
    """A Tarrant-side place, or the region as a whole; but a title whose subject is Dallas ("The Dallas Foundation awards
    ... to North Texas nonprofits") does not become ours because it also says North Texas."""
    text = place_text(title).lower()
    if any(p in text for p in PLACE_WORDS if p not in REGIONAL_WORDS):
        return True
    if not any(p in text for p in REGIONAL_WORDS):
        return False
    stripped = text
    for p in REGIONAL_WORDS:
        stripped = stripped.replace(p, " ")
    return re.search(r"\bdallas\b", stripped) is None


def wanted_title(cfg: dict, title: str, global_cfg: dict | None = None) -> bool:
    """The per-channel caution: a station's video must name the place in its own title; a team's video must be a result,
    highlights or a move; hours-long recordings and filler never qualify."""
    low = title.lower()
    skip = list((global_cfg or {}).get("skip_in_title", []) or []) + list(cfg.get("skip_in_title", []) or [])
    if any(s in low for s in SKIP_TITLE) or any(str(s).lower() in low for s in skip):
        return False
    if cfg.get("title_must_name_place") and not names_our_place(low):
        return False
    need = cfg.get("require_any_in_title")
    if need and not any(str(w).lower() in low for w in need):
        return False
    if cfg.get("require_watchlist_in_title"):      # wires and exchanges: only a video about a subject on the video watchlist
        terms = [str(t).lower() for t in (global_cfg or {}).get("video_watchlist", [])]
        if not any(t in low for t in terms):
            return False
    return True


def parse_feed(cfg: dict, content: bytes | str, now: datetime, global_cfg: dict | None = None) -> list[Story]:
    root = ET.fromstring(content)
    name = cfg["name"]
    max_age = float((global_cfg or {}).get("max_age_hours", 12))
    stories: list[Story] = []
    for entry in root.findall("a:entry", NS):
        vid = (entry.findtext("yt:videoId", default="", namespaces=NS) or "").strip()
        title = collapse_ws(entry.findtext("a:title", default="", namespaces=NS) or "")
        if not vid or not title or not wanted_title(cfg, title, global_cfg):
            continue
        group = entry.find("media:group", NS)
        desc = collapse_ws(group.findtext("media:description", default="", namespaces=NS) or "") if group is not None else ""
        thumb = None
        if group is not None:
            t = group.find("media:thumbnail", NS)
            thumb = t.get("url") if t is not None else None
        views = None
        if group is not None:
            st = group.find("media:community/media:statistics", NS)
            views = int(st.get("views")) if st is not None and st.get("views", "").isdigit() else None
        published = None
        raw = entry.findtext("a:published", default="", namespaces=NS)
        if raw:
            try:
                published = dtparse.isoparse(raw)
            except ValueError:
                published = None
        if published is None or (now - published).total_seconds() > max_age * 3600:
            continue                                   # undated or older than the window: not today's video
        stories.append(Story(
            id=stable_id("youtube", vid),
            source=name,
            source_kind="video",
            title=truncate(title, 200),
            summary=truncate(desc.split("\n")[0] if desc else "", 600),
            url=f"https://www.youtube.com/watch?v={vid}",
            published=published,
            category_hint=cfg.get("category_hint"),
            image_url=thumb,
            image_credit=f"Video: {name}",
            image_license="source-owned",
            image_policy="none",                 # their thumbnail is theirs; Facebook fetches its own preview for the link
            official=bool(cfg.get("official", False)),
            always_relevant=bool(cfg.get("always_relevant", False)),
            weight=float(cfg.get("weight", 0.8)),
            extra={"video_id": vid, "channel": name, "handle": cfg.get("handle", ""), "views": views, "feed_title": name,
                   **({"national": True} if cfg.get("national") else {})},
        ))
    return stories


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("youtube", {}) or {}
    if settings.offline or not cfg.get("enabled", False):
        return []
    stories: list[Story] = []
    for ch in cfg.get("channels", []) or []:
        if not ch.get("id") or not ch.get("enabled", True):
            continue
        try:
            resp = http.get(FEED.format(id=ch["id"]), headers={"Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.8"})
            found = parse_feed(ch, resp.content, now, cfg)
            log.info("youtube %-28s %3d videos", ch["name"], len(found))
            stories.extend(found)
        except Exception as exc:
            log.warning("youtube %s failed: %s", ch.get("name"), exc)
    return stories
