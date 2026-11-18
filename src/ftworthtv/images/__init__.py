"""Decide which real photo illustrates a post, fetch it legally, and render the branded card."""
from __future__ import annotations

import logging
from pathlib import Path

from ..config import Settings
from ..models import CATEGORY_LABELS, ImageAsset, PostDraft
from ..sources import cameras
from ..state import State
from ..textutil import fmt_time, to_local
from .card import render_card
from .fetch import download_image
from .providers import find_photo

log = logging.getLogger(__name__)


def _download(url: str, dest: Path, headers: dict | None = None) -> Path | None:
    try:
        return download_image(url, dest, headers=headers)
    except Exception as exc:
        log.warning("image download failed %s: %s", url, exc)
        return None


def plan_image(draft: PostDraft, settings: Settings, state: State, workdir: Path, exclude_photos: set[str] | None = None) -> ImageAsset:
    """Always returns an ImageAsset: a real licensed/public photo when possible, our branded placeholder otherwise."""
    story, copy = draft.story, draft.copy
    workdir.mkdir(parents=True, exist_ok=True)
    brand = settings.brand
    label = CATEGORY_LABELS.get(copy.category, "FORT WORTH")
    background: Path | None = None
    credit = "Illustration: " + brand.get("short_name", "FTW TV")
    license_ = "placeholder"
    provider = "placeholder"
    photo_id = None
    source_url = None
    fit = "cover"
    subline = None
    tz = settings.tz

    if story.source_kind == "nws_alert":
        label = "WEATHER ALERT" if story.severity in ("severe", "extreme") else "WEATHER"
        ends = story.extra.get("ends")
        if ends:
            from dateutil import parser as dtparse
            subline = f"{story.extra.get('severity', '')} · until {fmt_time(dtparse.isoparse(ends), tz)}"
        if story.image_url and not settings.offline:
            background = _download(story.image_url, workdir / "radar", headers={"User-Agent": settings.nws_user_agent})
            if background:
                credit, license_, provider, fit = "Radar: NWS Fort Worth (public domain)", "public-domain", "nws", "contain"
    elif story.source_kind == "nws_forecast":
        label = "FORECAST"
        high, short = story.extra.get("high"), story.extra.get("short")
        if high and short:
            subline = f"{high}° · {short}"
    elif story.source_kind in ("event", "event_roundup"):
        label = "THIS WEEKEND" if story.source_kind == "event_roundup" else "EVENTS"
        if story.extra.get("when") or story.extra.get("venue"):
            subline = " · ".join(x for x in (story.extra.get("when"), story.extra.get("venue")) if x)
        if story.image_url and not settings.offline:
            background = _download(story.image_url, workdir / "event")
            if background:
                credit, license_, provider, source_url = story.image_credit or "Image: Ticketmaster", "ticketmaster", "ticketmaster", story.url
    elif story.image_policy == "source_image" and story.image_url and not settings.offline:
        background = _download(story.image_url, workdir / "source")
        if background:
            credit, license_, provider, source_url = story.image_credit or f"Photo: {story.source}", story.image_license or "official", "source", story.url

    if background is None and copy.category == "traffic":
        cam = cameras.snapshot_for(story, settings, workdir)
        if cam:
            background, credit, license_, provider, label = cam.path, cam.credit, cam.license, cam.provider, "LIVE TRAFFIC"

    if background is None and not settings.offline:
        queries = [copy.image_query]
        venue = story.extra.get("venue")
        if story.source_kind in ("event", "event_roundup") and venue:  # a photo of the venue beats a random concert
            queries = [f"{venue} {brand.get('city', 'Fort Worth')}", venue, copy.image_query]
        cand = find_photo(queries, settings, state, exclude=exclude_photos)
        if cand:
            background = _download(cand.url, workdir / "photo")
            if background:
                credit, license_, provider, photo_id, source_url = cand.credit, cand.license, cand.provider, cand.id, cand.source_url
                if exclude_photos is not None:
                    exclude_photos.update({cand.id, cand.family})

    mood = {"nws_forecast": "sunrise", "nws_alert": "storm", "event": "dusk", "event_roundup": "dusk"}.get(story.source_kind) or \
        {"food": "day", "business": "day", "community": "day", "weather": "day", "culture": "sunrise", "sports": "dusk"}.get(copy.category, "night")
    out = render_card(
        background=background, headline=copy.headline or story.title, category_label=label, brand=brand,
        out_path=workdir / "card.jpg", fonts_dir=settings.fonts_dir,
        source_line=f"Source: {story.source}", photo_credit=credit if provider != "placeholder" else None,
        subline=subline, fit=fit, logo_path=settings.assets_dir / "logo.png", mood=mood,
    )
    return ImageAsset(path=out, credit=credit, license=license_, provider=provider, source_url=source_url, photo_id=photo_id,
                      width=brand.get("card", {}).get("size", [1080, 1350])[0], height=brand.get("card", {}).get("size", [1080, 1350])[1])
