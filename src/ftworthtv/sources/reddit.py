"""r/FortWorth hot posts as a trend signal (link posts only; we never download redditors' media). Off by default."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import stable_id, truncate

log = logging.getLogger(__name__)


def parse_listing(payload: dict, sub: str, min_score: int, now: datetime) -> list[Story]:
    stories: list[Story] = []
    for child in (payload.get("data", {}) or {}).get("children", []) or []:
        d = child.get("data", {}) or {}
        if d.get("over_18") or d.get("stickied") or int(d.get("score", 0)) < min_score:
            continue
        permalink = "https://www.reddit.com" + d.get("permalink", "")
        stories.append(Story(
            id=stable_id("reddit", d.get("id", permalink)),
            source=f"r/{sub}",
            source_kind="reddit",
            title=truncate(d.get("title", ""), 200),
            summary=truncate(d.get("selftext", "") or f"Trending on r/{sub} with {d.get('score')} upvotes.", 500),
            url=permalink,
            published=datetime.fromtimestamp(float(d.get("created_utc", 0)), tz=timezone.utc) if d.get("created_utc") else now,
            category_hint="community",
            image_policy="none",
            always_relevant=True,
            weight=0.6,
            extra={"score": d.get("score"), "author": d.get("author"), "external_url": d.get("url")},
        ))
    return stories


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("reddit", {}) or {}
    if settings.offline or not cfg.get("enabled", False):
        return []
    stories: list[Story] = []
    for sub in cfg.get("subreddits", ["FortWorth"]):
        payload = http.get_json(f"https://www.reddit.com/r/{sub}/hot.json", params={"limit": 30, "raw_json": 1})
        stories.extend(parse_listing(payload, sub, int(cfg.get("min_score", 150)), now))
    return stories
