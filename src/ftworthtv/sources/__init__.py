"""Content sources. Each module exposes fetch(settings, now) -> list[Story] and never raises."""
from __future__ import annotations

import logging
from datetime import datetime

from ..config import Settings
from ..models import Story
from . import nws, opencities, reddit, rss, ticketmaster

log = logging.getLogger(__name__)


def collect(settings: Settings, now: datetime) -> list[Story]:
    stories: list[Story] = []
    for module in (rss, opencities, nws, ticketmaster, reddit):
        try:
            found = module.fetch(settings, now)
            log.info("%s: %d candidate(s)", module.__name__.rsplit(".", 1)[-1], len(found))
            stories.extend(found)
        except Exception as exc:  # a broken source must never stop the run
            log.warning("source %s failed: %s", module.__name__, exc)
    # de-duplicate by id, keep the first (sources are ordered by trust)
    seen: set[str] = set()
    unique: list[Story] = []
    for s in stories:
        if s.id not in seen:
            seen.add(s.id)
            unique.append(s)
    return unique
