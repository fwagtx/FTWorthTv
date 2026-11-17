"""Load the bundled demo data (examples/) as Stories with fresh timestamps. Used by `ftworthtv preview` and the tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

from .config import Settings
from .models import Story
from .sources import nws, rss, ticketmaster


def _rss_cfg(settings: Settings, name: str, fallback: dict) -> dict:
    for cfg in settings.sources.get("rss", []) or []:
        if cfg.get("name") == name:
            return cfg
    return fallback


def _fill(text: str, now: datetime, tz) -> str:
    local = now.astimezone(tz)
    tonight = local.replace(hour=19, minute=30, second=0, microsecond=0)
    if tonight < local:
        tonight += timedelta(days=1)
    repl = {
        "__NOW__": now.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "__ENDS__": (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "__EVT1__": tonight.astimezone(now.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "__EVT2__": (tonight + timedelta(days=1, minutes=30)).astimezone(now.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "__EVT3__": (tonight + timedelta(days=2, minutes=-30)).astimezone(now.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "__EVT4__": (tonight + timedelta(days=2, hours=1, minutes=30)).astimezone(now.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for i in range(1, 9):
        repl[f"__PUB{i}__"] = format_datetime(now - timedelta(minutes=35 * i))
    for key, value in repl.items():
        text = text.replace(key, value)
    return text


def example_stories(settings: Settings, now: datetime, examples_dir: Path | None = None) -> list[Story]:
    examples_dir = examples_dir or settings.root / "examples"
    tz = settings.tz
    stories: list[Story] = []
    feeds = [
        ("fortworth_report_feed.xml", _rss_cfg(settings, "Fort Worth Report", {"name": "Fort Worth Report", "always_relevant": True, "weight": 1.0})),
        ("fox4_feed.xml", _rss_cfg(settings, "FOX 4 Dallas-Fort Worth", {"name": "FOX 4 Dallas-Fort Worth", "weight": 0.8})),
    ]
    for filename, cfg in feeds:
        path = examples_dir / filename
        if path.exists():
            stories.extend(rss.parse_feed(cfg, _fill(path.read_text(encoding="utf-8"), now, tz), now))
    nws_path = examples_dir / "nws_alerts.json"
    if nws_path.exists():
        stories.extend(nws.parse_alerts(json.loads(_fill(nws_path.read_text(encoding="utf-8"), now, tz)), settings.sources.get("nws", {}), now))
    tm_path = examples_dir / "ticketmaster_events.json"
    if tm_path.exists():
        events = ticketmaster.parse_events(json.loads(_fill(tm_path.read_text(encoding="utf-8"), now, tz)), settings.sources.get("ticketmaster", {}), now, tz)
        roundup = ticketmaster.roundup_story(sorted(events, key=lambda s: s.weight, reverse=True), now, tz)
        stories.extend(events)
        if roundup:
            stories.append(roundup)
    return stories
