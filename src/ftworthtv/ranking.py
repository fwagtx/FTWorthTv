"""Which of the many candidates deserve a post right now?"""
from __future__ import annotations

import math
from datetime import datetime

from .models import Story

CATEGORY_BOOST = {
    "breaking": 1.6, "weather": 1.2, "traffic": 1.15, "events": 1.1, "food": 1.05, "sports": 1.05,
    "crime": 1.0, "culture": 1.0, "community": 0.9, "business": 0.8, "other": 0.75, "politics": 1.1,   # "New Texas bill filed would..." is their best topic
}
KIND_BOOST = {"nws_alert": 2.0, "nws_forecast": 1.3, "event_roundup": 1.25, "event": 0.95, "rss": 1.0, "wanted": 0.9, "arrest_log": 0.9, "culture": 1.45, "reddit": 0.7,
              "video": 1.15, "submission": 1.3}
# one-liner news the Dallas page loves: rankings, openings, "coming to", consumer alerts
BUZZ_WORDS = ("ranked", "named", "best", "worst", "top 10", "opening", "opens", "coming to", "closing", "closes", "free", "outage",
              "recall", "first look", "new", "record", "biggest", "largest", "only in", "viral", "last night", "tonight", "this weekend",
              # sports: results and moves, not previews and filler
              "beat", "beats", "wins", "win", "loses", "loss", "upset", "fired", "hired", "trade", "traded", "signs", "signed", "injur",
              "suspended", "playoff", "bowl", "championship", "no. 1", "ranked no", "commit", "transfer", "heisman", "draft")
HALF_LIFE_HOURS = 6.0      # a story loses half its pull every six hours: the feed favours what just happened


def score(story: Story, now: datetime) -> float:
    rel = 1.0 + min(story.relevance, 8) / 8.0          # 1.0 .. 2.0
    fresh = 0.5 ** (story.age_hours(now) / HALF_LIFE_HOURS)
    if story.source_kind in ("nws_alert", "nws_forecast", "event", "event_roundup", "wanted", "arrest_log", "culture"):
        fresh = 1.0
    sev = {"extreme": 2.0, "severe": 1.6, "moderate": 1.2}.get(story.severity, 1.0) if story.source_kind == "nws_alert" else 1.0
    img = 1.08 if (story.image_url and story.image_policy == "source_image") else 1.0
    title = story.title.lower()
    buzz = 1.0 + 0.15 * min(2, sum(1 for w in BUZZ_WORDS if w in title))
    return rel * story.weight * fresh * CATEGORY_BOOST.get(story.category or "other", 0.8) * KIND_BOOST.get(story.source_kind, 1.0) * sev * img * buzz


def rank(stories: list[Story], now: datetime) -> list[Story]:
    for s in stories:
        s.score = round(score(s, now), 4)
    return sorted(stories, key=lambda s: s.score, reverse=True)


def pick(ranked: list[Story], k: int) -> list[Story]:
    """Top-k with diversity: at most one story per source per run, and no two of the same category unless urgent."""
    picked: list[Story] = []
    used_sources: set[str] = set()
    used_categories: set[str] = set()
    for s in ranked:
        if len(picked) >= k:
            break
        if s.is_urgent:
            picked.append(s)
            continue
        if s.source in used_sources and s.source_kind == "rss":
            continue
        if (s.category or "other") in used_categories and s.source_kind not in ("nws_alert",):
            continue
        picked.append(s)
        used_sources.add(s.source)
        used_categories.add(s.category or "other")
    if len(picked) < k:  # relax the diversity rule if we are short
        for s in ranked:
            if len(picked) >= k:
                break
            if s not in picked:
                picked.append(s)
    return picked
