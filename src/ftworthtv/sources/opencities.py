"""News listings on OpenCities-CMS government sites (police.fortworthtexas.gov, fortworthtexas.gov, arlingtontx.gov).

They publish no RSS, but every list item has the same shape:
  <article><a href=URL><h2 class="list-item-title">TITLE</h2> ... <img src=THUMB> ...
  <p class="published-on small-text">Published on Month D, YYYY</p> <p> SUMMARY </p></a></article>
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from dateutil import parser as dtparse

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import stable_id, strip_html, truncate

log = logging.getLogger(__name__)

ITEM_RE = re.compile(r'<article>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</article>', re.S | re.I)
TITLE_RE = re.compile(r'<h2 class="list-item-title">\s*(.*?)\s*</h2>', re.S | re.I)
IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
DATE_RE = re.compile(r'Published on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', re.I)
SUMMARY_RE = re.compile(r'<p>\s*([^<].*?)</p>', re.S)
# the City's stock notice graphics are not pictures of the story: Nov 25, "City seeks input on 2025-26 federal housing funds" came
# with city-news-request-for-public-comment.jpg (a megaphone and "Notice of Request for Public Comment")
GENERIC_IMAGE_WORDS = ("news-release", "sized-for-x", "placeholder", "default", "logo", "city-news-", "public-comment",
                       "public-hearing", "public-notice", "request-for", "notice-of")


def full_size(url: str) -> str:
    """Listing thumbnails carry ?dimension=smallthumbnail&w=..&h=..; the same path without the query is the original."""
    return url.split("?", 1)[0]


def parse_listing(html: str, base_url: str, cfg: dict, now: datetime, tz: ZoneInfo | None = None) -> list[Story]:
    name = cfg["name"]
    stories: list[Story] = []
    for href, block in ITEM_RE.findall(html):
        title_m = TITLE_RE.search(block)
        if not title_m:
            continue
        title = strip_html(title_m.group(1))
        url = urljoin(base_url, href)
        date_m = DATE_RE.search(block)
        published = None
        if date_m:
            try:
                published = dtparse.parse(date_m.group(1)).replace(hour=12, tzinfo=tz or timezone.utc)
            except (ValueError, OverflowError):
                published = None
        img_m = IMG_RE.search(block)
        image = urljoin(base_url, full_size(img_m.group(1))) if img_m else None
        generic = bool(image and any(w in image.lower() for w in GENERIC_IMAGE_WORDS))
        summary = ""
        for para in SUMMARY_RE.findall(block):
            text = strip_html(para)
            if text and not text.lower().startswith("published on"):
                summary = text
                break
        stories.append(Story(
            id=stable_id("oc", url),
            source=name,
            source_kind="rss",
            title=truncate(title, 200),
            summary=truncate(summary, 700),
            url=url,
            published=published,
            category_hint=cfg.get("category_hint"),
            image_url=None if generic else image,   # a generic "news release" graphic is not a photo of the story
            image_credit=f"Photo: {name}",
            image_license="official" if cfg.get("official", True) else "source-owned",
            image_policy=cfg.get("image_policy", "source_image"),
            official=bool(cfg.get("official", True)),
            always_relevant=bool(cfg.get("always_relevant", True)),
            weight=float(cfg.get("weight", 0.9)),
            extra={"listing_image": image, "generic_image": generic},
        ))
    return stories


def fetch(settings: Settings, now: datetime) -> list[Story]:
    if settings.offline:
        return []
    from .article import enrich
    stories: list[Story] = []
    max_age = float(settings.since_hours or 36)
    for cfg in settings.sources.get("opencities", []) or []:
        if not cfg.get("enabled", True):
            continue
        try:
            resp = http.get(cfg["url"], headers={"Accept": "text/html"})
            found = parse_listing(resp.text, str(resp.url), cfg, now, settings.tz)
            log.info("opencities %-28s %3d items", cfg["name"], len(found))
            fresh = [s for s in found if s.published is None or s.age_hours(now) <= max_age]
            for story in fresh[: int(cfg.get("max_article_fetches", 6))]:
                enrich(story)   # the release page carries the real photo (booking photo, scene photo) and the full text
            stories.extend(found)
        except Exception as exc:
            log.warning("opencities %s failed (%s): %s", cfg["name"], cfg.get("url"), exc)
    return stories
