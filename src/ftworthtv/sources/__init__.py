"""Content sources. Each module exposes fetch(settings, now) -> list[Story] and never raises."""
from __future__ import annotations

import logging
from datetime import datetime

from ..config import Settings
from ..models import Story
from . import arrests, calendar, nws, opencities, reddit, rss, ticketmaster, wanted

log = logging.getLogger(__name__)


def collect(settings: Settings, now: datetime) -> list[Story]:
    stories: list[Story] = []
    for module in (rss, opencities, nws, ticketmaster, wanted, arrests, calendar, reddit):
        try:
            found = module.fetch(settings, now)
            log.info("%s: %d candidate(s)", module.__name__.rsplit(".", 1)[-1], len(found))
            stories.extend(found)
        except Exception as exc:  # a broken source must never stop the run
            log.warning("source %s failed: %s", module.__name__, exc)
    # de-duplicate by id, keep the first (sources are ordered by trust); a story carried by a national outlet as well
    # keeps that flag, whichever copy survives (ESPN's league feeds and its top headlines overlap, for example)
    by_id: dict[str, Story] = {}
    for s in stories:
        kept = by_id.get(s.id)
        if kept is None:
            by_id[s.id] = s
        elif s.extra.get("national") and not kept.extra.get("national"):
            kept.extra["national"] = True
    return list(by_id.values())
