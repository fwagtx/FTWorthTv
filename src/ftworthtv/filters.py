"""Is this story about Fort Worth, fresh, brand-safe, and what kind of story is it?"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from .config import Settings
from .models import CATEGORIES, Story
from .state import State

log = logging.getLogger(__name__)

# keyword heuristics used before Claude refines the category (and as the only signal in template mode)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "weather": ["storm", "tornado", "thunder", "hail", "flood", "freeze", "ice ", "snow", "heat advisory", "weather",
                "forecast", "rain", "wind advisory", "cold front", "warning for"],
    "traffic": ["crash", "wreck", "i-35w", "35w", "i-30", "i-20", "loop 820", "highway", "lanes closed", "road closure",
                "traffic", "pileup", "18-wheeler", "trinity metro", "texrail", "dfw airport delays"],
    "crime": ["police", "shooting", "shot", "arrested", "arrest", "stabbing", "robbery", "homicide", "murder", "suspect",
              "fwpd", "deputies", "sheriff", "charged with", "manhunt", "burglary", "carjack"],
    "sports": ["tcu", "horned frogs", "frogs", "cowboys", "rangers", "mavericks", "stars", "fc dallas", "texas motor speedway",
               "nascar", "indycar", "rodeo", "stock show", "panther city", "pga", "colonial", "golf", "football", "basketball", "baseball"],
    "food": ["restaurant", "barbecue", "bbq", "brisket", "taco", "brewery", "bar ", "cafe", "coffee", "bakery", "food hall",
             "menu", "chef", "opens its", "grand opening", "margarita", "tex-mex", "burger", "pizza"],
    "events": ["concert", "festival", "tour", "live at", "dickies arena", "billy bob", "bass hall", "will rogers", "fair",
               "parade", "fireworks", "mayfest", "oktoberfest", "arts festival", "tickets", "show at", "comedy"],
    "culture": ["museum", "kimbell", "amon carter", "modern art", "stockyards", "cattle drive", "sundance square", "cultural district",
                "zoo", "botanic", "theater", "theatre", "gallery", "mural", "history", "historic"],
    "business": ["headquarters", "development", "jobs", "layoffs", "opening", "expansion", "investment", "real estate",
                 "apartments", "retail", "store", "company", "startup", "acquisition"],
    "politics": ["city council", "council vote", "mayor", "election", "ballot", "campaign", "legislature", "governor", "senate",
                 "congress", "republican", "democrat", "isd board", "school board", "trustees", "bond election", "ordinance"],
    "community": ["volunteer", "nonprofit", "fundraiser", "community", "neighborhood", "school", "students", "library", "park",
                  "church", "celebration", "holiday", "christmas", "thanksgiving"],
    "breaking": ["breaking", "developing", "evacuat", "explosion", "massive fire", "amber alert", "active shooter"],
}


def relevance_score(story: Story, keywords: list[str]) -> int:
    title = story.title.lower()
    summary = story.summary.lower()
    score = 0
    for kw in keywords:
        kw = kw.lower()
        if _has_word(kw, title):
            score += 2
        elif _has_word(kw, summary):
            score += 1
    return score


OBIT_TITLE_RE = re.compile(r"\b(19|20)\d{2}\b.*[–\-—].*\b(19|20)\d{2}\b")   # "Jane Doe – June 29, 1932 – Nov. 8, 2026"


def blocked(story: Story, blocklist: list[str]) -> str | None:
    text = story.text()
    for term in blocklist or []:
        if term.lower() in text:
            return term
    if OBIT_TITLE_RE.search(story.title) and len(story.title) < 90:
        return "obituary (name + life dates)"
    if re.search(r"/obit", story.url or "", re.I) or re.search(r"\b(passed away|in loving memory|funeral services?)\b", text):
        return "obituary"
    return None


_WORD_RE: dict[str, "re.Pattern[str]"] = {}


def _has_word(word: str, text: str) -> bool:
    """Whole-word match so 'rain' does not fire on 'drainage' or 'art' on 'party'."""
    pat = _WORD_RE.get(word)
    if pat is None:
        pat = _WORD_RE[word] = re.compile(r"(?<![a-z0-9])" + re.escape(word.strip()) + r"(?![a-z0-9])", re.I)
    return bool(pat.search(text))


def infer_category(story: Story) -> str:
    text = story.text()
    title = story.title.lower()
    best, best_hits = None, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        hits = sum(1 for w in words if _has_word(w, text))
        # title hits count double
        hits += sum(1 for w in words if _has_word(w, title))
        if hits > best_hits:
            best, best_hits = cat, hits
    if story.category_hint and (best_hits == 0 or story.category_hint in ("weather", "events", "sports", "crime")):
        return story.category_hint if story.category_hint in CATEGORIES else (best or "other")
    return best or story.category_hint or "other"


def is_fresh(story: Story, now: datetime, max_age_hours: float) -> bool:
    if story.source_kind in ("nws_alert", "nws_forecast", "event", "event_roundup", "wanted", "arrest_log", "culture"):
        return True
    if story.published is None:
        return True  # feeds without dates: trust the feed order / dedupe state
    return story.age_hours(now) <= max_age_hours


def filter_stories(stories: list[Story], settings: Settings, state: State, now: datetime) -> tuple[list[Story], list[tuple[Story, str]]]:
    """Returns (kept, [(story, reason)]) and annotates kept stories with category + relevance."""
    rel = settings.relevance
    keywords = rel.get("keywords", ["fort worth"])
    blocklist = rel.get("blocklist", [])
    excluded = set(rel.get("exclude_categories", []) or [])
    min_rel = int(rel.get("min_relevance", 2))
    max_age = float(settings.since_hours or rel.get("max_age_hours", 36))

    kept: list[Story] = []
    dropped: list[tuple[Story, str]] = []
    for story in stories:
        if state.has(story.id):
            dropped.append((story, "already posted"))
            continue
        if not is_fresh(story, now, max_age):
            dropped.append((story, f"older than {max_age:.0f}h"))
            continue
        term = blocked(story, blocklist)
        if term:
            dropped.append((story, f"blocklist: {term}"))
            continue
        story.relevance = relevance_score(story, keywords)
        story.extra.setdefault("scope", "local")
        if not story.always_relevant and story.relevance < min_rel:
            # the Dallas page is Dallas-first but posts DFW and Texas-wide stories every day (new Texas bills, H-E-B,
            # gas prices, outages). Keep those at a lower weight and a lower share; drop the rest.
            tier = None
            for name, mult in (("dfw", 0.85), ("texas", 0.7)):
                tier_keys = rel.get(f"{name}_keywords", []) or []
                if tier_keys and relevance_score(story, tier_keys) >= 2:
                    tier = (name, mult)
                    break
            if tier is None:
                dropped.append((story, f"not local enough (relevance {story.relevance} < {min_rel})"))
                continue
            story.extra["scope"] = tier[0]
            story.weight *= tier[1]
            story.relevance = min_rel
        story.category = infer_category(story)
        if story.category in excluded:
            dropped.append((story, f"excluded category: {story.category}"))
            continue
        kept.append(story)
    return kept, dropped
