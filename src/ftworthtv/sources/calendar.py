"""Recurring Fort Worth cultural moments (config/culture.yaml) -> evergreen posts with a licensed photo.

Mirrors the seasonal beats the Dallas page posts (State Fair, Halloween, holiday lights, game days, summer heat memes).
"""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from ..config import Settings
from ..models import Story

log = logging.getLogger(__name__)


def _parse_window(window: str, year: int) -> tuple[date, date]:
    start_s, end_s = [w.strip() for w in window.split("..")]
    sm, sd = (int(x) for x in start_s.split("-"))
    em, ed = (int(x) for x in end_s.split("-"))
    start = date(year, sm, sd)
    end = date(year, em, ed)
    if end < start:  # window wraps the new year, e.g. 12-15..02-15
        end = date(year + 1, em, ed)
    return start, end


def active_moments(moments: list[dict], today: date) -> list[tuple[dict, date, int]]:
    """(moment, window_start, occurrence_index) for every moment whose window contains today."""
    out = []
    for m in moments:
        for year in (today.year - 1, today.year):
            start, end = _parse_window(m["window"], year)
            if start <= today <= end:
                every = int(m.get("every_days", 0) or 0)
                idx = (today - start).days // every if every else 0
                out.append((m, start, idx))
                break
    return out


def moment_story(m: dict, start: date, idx: int, now: datetime, city: str) -> Story:
    rnd = random.Random(f"{m['slug']}-{start.year}-{idx}")
    caption = rnd.choice(m.get("captions") or [m["name"]]).replace("{year}", str(start.year))
    return Story(
        id=f"culture-{m['slug']}-{start.year}-{idx}",
        source="Fort Worth Texas TV",
        source_kind="culture",
        title=caption,
        summary=m.get("name", ""),
        url=m.get("url", ""),
        published=now,
        category_hint=m.get("category", "culture"),
        image_policy="none",
        always_relevant=True,
        weight=float(m.get("weight", 0.9)),
        extra={"image_query": m.get("image_query", f"{city} skyline"), "name": m.get("name"), "slug": m["slug"]},
    )


def load_moments(settings: Settings) -> list[dict]:
    path = settings.root / "config" / "culture.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("moments", []) or [])


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.brand.get("culture_calendar", {}) or {}
    if not cfg.get("enabled", True):
        return []
    today = now.astimezone(settings.tz).date()
    city = settings.brand.get("city", "Fort Worth")
    return [moment_story(m, start, idx, now, city) for m, start, idx in active_moments(load_moments(settings), today)]
