"""RSS / Atom ingestion for local outlets, city hall and the police department."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import feedparser

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import stable_id, strip_html, truncate

log = logging.getLogger(__name__)
_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        tm = entry.get(key)
        if tm:
            try:
                return datetime(*tm[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _entry_image(entry) -> str | None:
    for media in entry.get("media_content", []) or []:
        url = media.get("url")
        if url and (media.get("medium", "image") == "image" or str(media.get("type", "")).startswith("image")):
            return url
    for thumb in entry.get("media_thumbnail", []) or []:
        if thumb.get("url"):
            return thumb["url"]
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image") and link.get("href"):
            return link["href"]
    for content in entry.get("content", []) or []:
        m = _IMG_RE.search(content.get("value", "") or "")
        if m:
            return m.group(1)
    m = _IMG_RE.search(entry.get("summary", "") or "")
    return m.group(1) if m else None


def parse_feed(cfg: dict, content: bytes | str, now: datetime) -> list[Story]:
    """Parse one feed's body into Stories. Pure function so it is testable without network."""
    parsed = feedparser.parse(content)
    name = cfg["name"]
    stories: list[Story] = []
    for entry in parsed.entries:
        link = (entry.get("link") or "").strip()
        title = strip_html(entry.get("title") or "")
        if not link or not title:
            continue
        summary = strip_html(entry.get("summary") or "")
        if not summary and entry.get("content"):
            summary = strip_html(entry["content"][0].get("value", ""))
        stories.append(Story(
            id=stable_id("rss", entry.get("id") or link),
            source=name,
            source_kind="rss",
            title=truncate(title, 200),
            summary=truncate(summary, 700),
            url=link,
            published=_entry_time(entry),
            category_hint=cfg.get("category_hint"),
            image_url=_entry_image(entry),
            image_credit=f"Photo: {name}",
            image_license="official" if cfg.get("official") else "source-owned",
            image_policy=cfg.get("image_policy", "none"),
            official=bool(cfg.get("official", False)),
            always_relevant=bool(cfg.get("always_relevant", False)),
            weight=float(cfg.get("weight", 1.0)),
            extra={"feed_title": strip_html(parsed.feed.get("title", "")) if parsed.feed else ""},
        ))
    return stories


def fetch_one(cfg: dict, now: datetime) -> list[Story]:
    resp = http.get(cfg["url"], headers={"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"})
    return parse_feed(cfg, resp.content, now)


def fetch(settings: Settings, now: datetime) -> list[Story]:
    if settings.offline:
        return []
    from .article import enrich
    stories: list[Story] = []
    max_age = float(settings.since_hours or 36)
    for cfg in settings.sources.get("rss", []) or []:
        if not cfg.get("enabled", True):
            continue
        try:
            found = fetch_one(cfg, now)
            log.info("rss %-32s %3d items", cfg["name"], len(found))
            if cfg.get("fetch_article") or (cfg.get("official") and cfg.get("image_policy") == "source_image"):
                fresh = [s for s in found if not s.image_url and (s.published is None or s.age_hours(now) <= max_age)]
                for story in fresh[: int(cfg.get("max_article_fetches", 6))]:
                    enrich(story)
            stories.extend(found)
        except Exception as exc:
            log.warning("rss %s failed (%s): %s", cfg["name"], cfg.get("url"), exc)
    return stories


def check(settings: Settings) -> list[dict]:
    """For `ftworthtv sources check`: hit every feed and report what came back."""
    report = []
    now = datetime.now(timezone.utc)
    for cfg in settings.sources.get("rss", []) or []:
        row = {"name": cfg["name"], "url": cfg["url"], "ok": False, "items": 0, "with_image": 0, "newest": None, "error": ""}
        try:
            found = fetch_one(cfg, now)
            row.update(ok=True, items=len(found), with_image=sum(1 for s in found if s.image_url))
            times = [s.published for s in found if s.published]
            row["newest"] = max(times).isoformat() if times else None
        except Exception as exc:
            row["error"] = str(exc)[:200]
        report.append(row)
    return report
