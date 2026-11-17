"""Ticketmaster Discovery API: real event photos + ticket links for Dickies Arena, Billy Bob's, TMS, TCU..."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dateutil import parser as dtparse

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import fmt_day, fmt_time, truncate

log = logging.getLogger(__name__)
API = "https://app.ticketmaster.com/discovery/v2/events.json"


def _best_image(images: list[dict], min_width: int) -> dict | None:
    if not images:
        return None
    wide = [i for i in images if i.get("ratio") == "16_9" and int(i.get("width", 0)) >= min_width]
    pool = wide or [i for i in images if int(i.get("width", 0)) >= min_width] or images
    return max(pool, key=lambda i: int(i.get("width", 0)))


def _start(ev: dict) -> datetime | None:
    start = (ev.get("dates", {}) or {}).get("start", {}) or {}
    if start.get("dateTime"):
        return dtparse.isoparse(start["dateTime"])
    if start.get("localDate"):
        return dtparse.isoparse(start["localDate"] + "T" + (start.get("localTime") or "19:00:00")).replace(tzinfo=timezone.utc)
    return None


def parse_events(payload: dict, cfg: dict, now: datetime, tz) -> list[Story]:
    events = ((payload.get("_embedded", {}) or {}).get("events", []) or [])
    min_width = int(cfg.get("min_image_width", 1000))
    boost = [v.lower() for v in cfg.get("venue_boost", [])]
    stories: list[Story] = []
    for ev in events:
        start = _start(ev)
        if not start or start < now - timedelta(hours=2):
            continue
        venue = ((ev.get("_embedded", {}) or {}).get("venues") or [{}])[0]
        venue_name = venue.get("name", "Fort Worth")
        city = (venue.get("city") or {}).get("name", "Fort Worth")
        cls = (ev.get("classifications") or [{}])[0]
        genre = (cls.get("genre") or {}).get("name") or (cls.get("segment") or {}).get("name") or "Event"
        image = _best_image(ev.get("images", []), min_width)
        prices = (ev.get("priceRanges") or [{}])[0]
        when = f"{fmt_day(start, tz)} {fmt_time(start, tz)}".strip()
        summary = f"{ev.get('name')} at {venue_name} ({city}) on {when}. {genre}."
        if prices.get("min"):
            summary += f" Tickets from ${prices['min']:.0f}."
        if ev.get("info"):
            summary += " " + truncate(ev["info"], 200)
        weight = float(cfg.get("weight", 0.9)) * (1.25 if venue_name.lower() in boost else 1.0)
        stories.append(Story(
            id=f"tm-{ev.get('id')}",
            source="Ticketmaster",
            source_kind="event",
            title=f"{ev.get('name')} at {venue_name}",
            summary=summary,
            url=ev.get("url", ""),
            published=now,
            category_hint="sports" if (cls.get("segment") or {}).get("name") == "Sports" else "events",
            image_url=image.get("url") if image else None,
            image_credit="Image: Ticketmaster / event promoter",
            image_license="ticketmaster",
            image_policy="source_image",
            always_relevant=True,
            weight=weight,
            extra={"venue": venue_name, "city": city, "start": start.isoformat(), "genre": genre,
                   "when": when, "price_min": prices.get("min"), "ticket_url": ev.get("url", "")},
        ))
    return stories


def roundup_story(events: list[Story], now: datetime, tz) -> Story | None:
    """Thursday/Friday 'This weekend in Fort Worth' list built from the top event stories."""
    if len(events) < 3:
        return None
    events = sorted(events[:6], key=lambda s: s.extra.get("start", ""))
    local = now.astimezone(tz)
    week = local.isocalendar()
    lines = [f"• {s.extra.get('when', '')} — {s.title}" for s in events[:6]]
    return Story(
        id=f"roundup-{week.year}-W{week.week}",
        source="Ticketmaster",
        source_kind="event_roundup",
        title="This weekend in Fort Worth",
        summary="\n".join(lines),
        url=events[0].url,
        published=now,
        category_hint="events",
        image_url=events[0].image_url,
        image_credit=events[0].image_credit,
        image_license="ticketmaster",
        image_policy="source_image",
        always_relevant=True,
        weight=1.1,
        extra={"events": [{"title": s.title, "when": s.extra.get("when"), "url": s.url, "venue": s.extra.get("venue")} for s in events[:6]]},
    )


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("ticketmaster", {}) or {}
    if settings.offline or not cfg.get("enabled", True) or not settings.ticketmaster_api_key:
        return []
    params = {
        "apikey": settings.ticketmaster_api_key,
        "city": cfg.get("city", "Fort Worth"),
        "stateCode": cfg.get("state_code", "TX"),
        "radius": int(cfg.get("radius_miles", 15)),
        "unit": "miles",
        "sort": "date,asc",
        "size": 60,
        "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": (now + timedelta(days=int(cfg.get("lookahead_days", 3)))).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload = http.get_json(API, params=params)
    stories = parse_events(payload, cfg, now, settings.tz)
    local = now.astimezone(settings.tz)
    if settings.posting.get("weekend_events_roundup", True) and local.weekday() in (3, 4) and local.hour >= 15:
        ranked = sorted(stories, key=lambda s: s.weight, reverse=True)
        roundup = roundup_story(ranked, now, settings.tz)
        if roundup:
            stories.insert(0, roundup)
    return stories
