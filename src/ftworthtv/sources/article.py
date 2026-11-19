"""Fetch an official release/article page and pull out what the feed did not give us: the photo, a summary, the date.

Used for government sources (police releases, city news) whose photos we are allowed to post. Reads Open Graph /
Twitter meta tags first, then the first real image inside the article body.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from dateutil import parser as dtparse

from .. import http
from ..models import Story
from ..textutil import strip_html, truncate

log = logging.getLogger(__name__)

_META_RE = re.compile(r"<meta\s+[^>]*>", re.I)
_ATTR_RE = re.compile(r'([a-zA-Z:_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", re.I)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.S)
_SKIP_IMG = ("logo", "icon", "sprite", "badge", "seal", ".svg", "pixel", "spacer", "avatar", "facebook", "twitter", "instagram", "youtube")


def parse_article(html: str, base_url: str) -> dict:
    meta: dict[str, str] = {}
    for tag in _META_RE.findall(html):
        attrs = {k.lower(): (v1 if v1 is not None else v2) for k, v1, v2 in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key and attrs.get("content"):
            meta.setdefault(key, attrs["content"])
    image = meta.get("og:image") or meta.get("twitter:image") or meta.get("twitter:image:src")
    body = html
    # news pages carry several <article> blocks (teasers, "trending", the story itself): take the one that contains the
    # page's own description, else the longest; never the first one found
    blocks = [m.group(1) for m in re.finditer(r"<article[^>]*>(.*?)</article>", html, re.I | re.S)]
    if not blocks:
        m = re.search(r"<main[^>]*>(.*?)</main>", html, re.I | re.S)
        blocks = [m.group(1)] if m else []
    if blocks:
        desc = strip_html(meta.get("og:description") or meta.get("description") or "")[:60].lower()
        with_desc = [b for b in blocks if desc and desc in strip_html(b).lower()]
        body = max(with_desc or blocks, key=lambda b: len(strip_html(b)))
    if not image:
        for src in _IMG_RE.findall(body):
            low = src.lower()
            if any(s in low for s in _SKIP_IMG) or low.startswith("data:"):
                continue
            image = src
            break
    if image:
        image = urljoin(base_url, image)
    paragraphs = [strip_html(p) for p in _P_RE.findall(body)]
    paragraphs = [p for p in paragraphs if len(p) > 40]
    published = None
    for key in ("article:published_time", "og:updated_time", "date", "dc.date", "pubdate"):
        if meta.get(key):
            try:
                published = dtparse.parse(meta[key])
                break
            except (ValueError, OverflowError):
                continue
    return {
        "title": strip_html(meta.get("og:title") or ""),
        "description": strip_html(meta.get("og:description") or meta.get("description") or ""),
        "summary": truncate(" ".join(paragraphs), 900),
        "image": image,
        "published": published,
    }


def fetch_article(url: str) -> dict:
    resp = http.get(url, headers={"Accept": "text/html,application/xhtml+xml"})
    return parse_article(resp.text, str(resp.url))


def enrich(story: Story) -> Story:
    """For official sources: fill in the release photo and a fuller summary from the page itself."""
    try:
        info = fetch_article(story.url)
    except Exception as exc:
        log.info("article fetch failed for %s: %s", story.url, exc)
        return story
    if not story.image_url and info.get("image"):
        story.image_url = info["image"]
    if len(story.summary) < 120 and (info.get("summary") or info.get("description")):
        story.summary = info.get("summary") or info["description"]
    if story.published is None and info.get("published"):
        story.published = info["published"]
    story.extra["article_fetched"] = True
    return story


def enrich_summary(story: Story, min_len: int = 160) -> Story:
    """For any outlet: when the feed gave only a teaser, read the article's description and lead paragraphs so the caption
    can be a real two-paragraph summary. Text only: a non-official outlet's photo is never taken."""
    if len(story.summary or "") >= min_len or not story.url:
        return story
    try:
        info = fetch_article(story.url)
    except Exception as exc:
        log.info("article fetch failed for %s: %s", story.url, exc)
        return story
    if not same_subject(story.title, info.get("title", ""), info.get("description", ""), info.get("summary", "")):
        log.info("article text does not match the story (%s); keeping the feed summary", story.title[:50])
        return story
    lead = " ".join(part for part in (info.get("description", ""), info.get("summary", "")) if part)
    if len(lead) > len(story.summary or ""):
        story.summary = truncate(lead, 900)
    return story


_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "after", "as", "by", "is", "are", "was", "from",
         "its", "it", "this", "that", "new", "says", "say", "said", "will", "over", "into", "up", "fort", "worth", "texas", "how", "why",
         "what", "who", "when", "where", "about", "than", "more", "most", "their", "his", "her", "they", "our", "your", "has", "have"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", (text or "").lower()) if w not in _STOP}


def same_subject(story_title: str, page_title: str, description: str, body: str) -> bool:
    """Is the fetched page the story we were sent to? A news page can hand back a teaser for a different article."""
    t = _words(story_title)
    if not t:
        return False
    pt = _words(page_title)
    if pt and len(t & pt) / max(1, min(len(t), len(pt))) >= 0.5:
        return True
    lead = _words(description) | _words(body[:600])
    return len(t & lead) >= max(2, len(t) // 3)
