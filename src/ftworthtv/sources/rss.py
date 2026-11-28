"""RSS / Atom ingestion for local outlets, city hall and the police department."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import feedparser

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import collapse_ws, stable_id, strip_html, truncate

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


_FEED_NOISE = re.compile(r"\s*(The post .{0,200}? appeared first on .{0,80}?(\.|$)|Continue reading\b.*$|Read more\b.*$|The article .{0,200}? appeared first on .{0,80}?(\.|$))", re.I)


def clean_feed_text(text: str) -> str:
    """WordPress feeds append 'The post X appeared first on Y.' and truncate with '[…]'; neither belongs in a caption."""
    text = _FEED_NOISE.sub("", text or "")
    text = re.sub(r"\s*\[(…|\.\.\.|&hellip;)\]\s*", " … ", text)
    return collapse_ws(text)


# a headline's abbreviations, spelled out the way a description says them
_TITLE_ALIASES = {"uswnt": "united states women's national soccer team", "usmnt": "united states men's national soccer team",
                  "dfw": "dallas fort worth", "fwpd": "fort worth police", "dps": "department public safety troopers",
                  "isd": "school district", "tcu": "horned frogs", "uta": "arlington mavericks", "unt": "north mean green"}


def about_headline(title: str, text: str) -> bool:
    """Does a feed's description talk about its own headline? NBC 5's feed (Nov 23) carried one Sunday Night Football article
    under every item, so "Christmas in the Garden returns to Fort Worth Botanic Garden" was filed as sports news.
    Nov 27, render 312: WFAA's "USWNT plays El Salvador in Texas Health Mansfield Stadium" lost its description ("The United
    States women's soccer team takes on El Salvador in North Texas on Friday night.") for sharing one word with a six-word
    headline: abbreviations are spelled out, and a short headline needs one shared word (a description repeated under several
    headlines, the broken feed's mark, is caught separately)."""
    from .article import _words
    t = _words(title)
    if not text or not t:
        return True
    spelled = t | _words(" ".join(_TITLE_ALIASES[w] for w in t if w in _TITLE_ALIASES))
    # Nov 27, render 317: WFAA's "Fort Worth police tighten pursuit policy ..." lost "Nearly 1,000 police pursuits over five
    # years resulted in hundreds of crashes and 10 deaths." for "pursuit" against "pursuits": words are compared by their stems
    shared = len({_stem(w) for w in spelled} & {_stem(w) for w in _words(text[:700])})
    return shared >= (1 if len(t) <= 6 else 2)


def _stem(word: str) -> str:
    """'pursuits' -> 'pursuit', 'policies' -> 'policy', 'crashes' -> 'crash', 'closing' -> 'clos', 'closed' -> 'clos'."""
    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def parse_feed(cfg: dict, content: bytes | str, now: datetime) -> list[Story]:
    """Parse one feed's body into Stories. Pure function so it is testable without network."""
    parsed = feedparser.parse(content)
    name = cfg["name"]
    stories: list[Story] = []
    seen: dict[str, set[str]] = {}               # the same description under different headlines is a broken feed
    for entry in parsed.entries:
        text = clean_feed_text(strip_html(entry.get("summary") or ""))[:300]
        if text:
            seen.setdefault(text, set()).add(strip_html(entry.get("title") or ""))
    for entry in parsed.entries:
        link = (entry.get("link") or "").strip()
        title = strip_html(entry.get("title") or "")
        if not link or not title:
            continue
        # a weekly's reviews, listings and advertorials are not news: Nov 25, Fort Worth Weekly's "Hexed: 'Cause It's Witchcraft"
        # (Film Reviews), "Film Shorts // ..." (Film Shorts), "Ate Days of Thanksgiving Leftovers" and a sweepstakes-casino
        # pitch (Living Local); the feed names each item's section first
        section = str(((entry.get("tags") or [{}])[0] or {}).get("term") or "").strip().lower()
        if section and section in {str(x).lower() for x in (cfg.get("skip_sections") or [])}:
            continue
        summary = clean_feed_text(strip_html(entry.get("summary") or ""))
        if not summary and entry.get("content"):
            summary = clean_feed_text(strip_html(entry["content"][0].get("value", "")))
        if summary and (len(seen.get(summary[:300], ())) > 1 or not about_headline(title, summary)):
            excerpt = clean_feed_text(strip_html(entry.get("excerpt") or ""))
            summary = excerpt if excerpt and about_headline(title, excerpt) else ""   # the article is read later (enrich_summary)
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
            image_license=cfg.get("image_license") or ("official" if cfg.get("official") else "source-owned"),
            image_policy=cfg.get("image_policy", "none"),
            official=bool(cfg.get("official", False)),
            always_relevant=bool(cfg.get("always_relevant", False)),
            weight=float(cfg.get("weight", 1.0)),
            extra={"feed_title": strip_html(parsed.feed.get("title", "")) if parsed.feed else "", "national": bool(cfg.get("national", False)),
                   **({"social_tag": cfg["social_tag"]} if cfg.get("social_tag") else {})},
        ))
    return stories


_CHALLENGE_MARKERS = (b"awsWafCookieDomainList", b"AwsWafIntegration", b"challenge-platform", b"_cf_chl_opt", b"Just a moment...")


def feed_problem(status: int, content: bytes) -> str | None:
    """Why a 2xx answer is not a feed: ESPN's WAF answers 202 with a JavaScript challenge page, a Sidearm site answers 200
    with nothing. Both used to log as "0 items", which reads like a quiet news day instead of a broken source."""
    head = (content or b"")[:4000]
    if status == 202 or any(m in head for m in _CHALLENGE_MARKERS):
        return f"blocked by a bot challenge (HTTP {status})"
    if not head.strip():
        return f"empty body (HTTP {status})"
    return None


def fetch_one(cfg: dict, now: datetime) -> list[Story]:
    resp = http.get(cfg["url"], headers={"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"},
                    timeout=(10, 30), quick=True)
    problem = feed_problem(resp.status_code, resp.content)
    if problem:
        raise ValueError(problem)
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
            if cfg.get("fetch_article") or cfg.get("image_policy") == "source_image":
                fresh = [s for s in found if (not s.image_url or cfg.get("image_policy") == "source_image") and (s.published is None or s.age_hours(now) <= max_age)]
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
