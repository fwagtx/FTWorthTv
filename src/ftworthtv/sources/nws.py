"""National Weather Service: active alerts for Tarrant County + a daily forecast post. Free, no key, public domain."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dateutil import parser as dtparse

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import stable_id, to_local, truncate

log = logging.getLogger(__name__)

API = "https://api.weather.gov"
SEVERITY_RANK = {"minor": 1, "moderate": 2, "severe": 3, "extreme": 4, "unknown": 0}


def radar_still_url(station: str) -> str:
    return f"https://radar.weather.gov/ridge/standard/{station}_0.gif"


def radar_loop_url(station: str) -> str:
    return f"https://radar.weather.gov/ridge/standard/{station}_loop.gif"


def _headers(settings: Settings) -> dict:
    return {"User-Agent": settings.nws_user_agent, "Accept": "application/geo+json"}


def parse_alerts(payload: dict, cfg: dict, now: datetime) -> list[Story]:
    """Turn an api.weather.gov alerts payload into Stories (pure function)."""
    min_rank = SEVERITY_RANK.get(str(cfg.get("min_severity", "Moderate")).lower(), 2)
    station = cfg.get("radar_station", "KFWS")
    stories: list[Story] = []
    for feature in payload.get("features", []) or []:
        p = feature.get("properties", {}) or {}
        severity = str(p.get("severity", "Unknown"))
        if SEVERITY_RANK.get(severity.lower(), 0) < min_rank:
            continue
        if str(p.get("status", "Actual")) != "Actual" or str(p.get("messageType", "Alert")) == "Cancel":
            continue
        ends = p.get("ends") or p.get("expires")
        ends_dt = dtparse.isoparse(ends) if ends else None
        if ends_dt and ends_dt < now:
            continue
        sent = p.get("sent") or p.get("effective")
        event = p.get("event", "Weather Alert")
        area = p.get("areaDesc", "Tarrant County")
        headline = p.get("headline") or f"{event} for {area}"
        description = truncate(p.get("description") or "", 900)
        instruction = truncate(p.get("instruction") or "", 400)
        stories.append(Story(
            id=stable_id("nws", p.get("id") or feature.get("id") or headline),
            source="National Weather Service Fort Worth",
            source_kind="nws_alert",
            title=f"{event}: {area}",
            summary=f"{headline}. {description}".strip(),
            url=f"https://forecast.weather.gov/MapClick.php?zoneid={cfg.get('zone', 'TXZ118')}",
            published=dtparse.isoparse(sent) if sent else now,
            category_hint="weather",
            image_url=radar_still_url(station),
            image_credit="Radar: National Weather Service (public domain)",
            image_license="public-domain",
            image_policy="source_image",
            official=True,
            always_relevant=True,
            weight=1.3,
            extra={"severity": severity, "event": event, "area": area, "ends": ends, "instruction": instruction,
                   "urgency": p.get("urgency"), "radar_loop": radar_loop_url(station)},
        ))
    return stories


def fetch_alerts(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("nws", {}) or {}
    if not cfg.get("post_alerts", True):
        return []
    stories: list[Story] = []
    seen: set[str] = set()
    for key in ("zone", "county"):
        code = cfg.get(key)
        if not code:
            continue
        payload = http.get_json(f"{API}/alerts/active", params={"zone": code}, headers=_headers(settings))
        for s in parse_alerts(payload, cfg, now):
            if s.id not in seen:
                seen.add(s.id)
                stories.append(s)
    return stories


def parse_forecast(payload: dict, now: datetime, tz, cfg: dict) -> Story | None:
    periods = (payload.get("properties", {}) or {}).get("periods", []) or []
    if not periods:
        return None
    today = periods[0]
    tonight = periods[1] if len(periods) > 1 else None
    local_day = to_local(now, tz)
    lines = [f"{today.get('name')}: {today.get('shortForecast')}, {'high' if today.get('isDaytime', True) else 'low'} near "
             f"{today.get('temperature')}°{today.get('temperatureUnit', 'F')}. Wind {today.get('windSpeed')} {today.get('windDirection', '')}."]
    pop = (today.get("probabilityOfPrecipitation") or {}).get("value")
    if pop:
        lines.append(f"Rain chance {pop}%.")
    if tonight:
        lines.append(f"{tonight.get('name')}: {tonight.get('shortForecast')}, low near {tonight.get('temperature')}°.")
    detailed = truncate(today.get("detailedForecast") or "", 300)
    return Story(
        id=f"forecast-{local_day.date().isoformat()}",
        source="National Weather Service Fort Worth",
        source_kind="nws_forecast",
        title=f"Fort Worth forecast for {local_day.strftime('%A, %B %d').replace(' 0', ' ')}",
        summary=" ".join(lines) + (f" {detailed}" if detailed else ""),
        url="https://forecast.weather.gov/MapClick.php?lat=32.7555&lon=-97.3308",
        published=now,
        category_hint="weather",
        image_url=None,
        image_license="public-domain",
        official=True,
        always_relevant=True,
        weight=1.0,
        extra={"high": today.get("temperature"), "short": today.get("shortForecast"), "icon": today.get("icon"),
               "low": tonight.get("temperature") if tonight else None, "pop": pop, "wind": today.get("windSpeed")},
    )


def fetch_forecast(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("nws", {}) or {}
    if not cfg.get("daily_forecast", True):
        return []
    hour = int(settings.posting.get("daily_forecast_hour_local", 7))
    local = to_local(now, settings.tz)
    if not (hour <= local.hour < hour + 3):   # only offer the forecast in a 3h morning window
        return []
    points = http.get_json(f"{API}/points/{cfg.get('latitude', 32.7555)},{cfg.get('longitude', -97.3308)}",
                           headers=_headers(settings))
    forecast_url = (points.get("properties", {}) or {}).get("forecast")
    if not forecast_url:
        return []
    payload = http.get_json(forecast_url, headers=_headers(settings))
    story = parse_forecast(payload, now, settings.tz, cfg)
    return [story] if story else []


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("nws", {}) or {}
    if settings.offline or not cfg.get("enabled", True):
        return []
    stories: list[Story] = []
    for fn in (fetch_alerts, fetch_forecast):
        try:
            stories.extend(fn(settings, now))
        except Exception as exc:
            log.warning("nws %s failed: %s", fn.__name__, exc)
    return stories
