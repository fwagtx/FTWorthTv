"""Decide which real photo illustrates a post, fetch it legally, and render the branded card."""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from ..config import Settings
from ..models import CATEGORY_LABELS, ImageAsset, PostDraft
from ..sources import cameras
from ..state import State
from ..textutil import fmt_time, to_local
from .card import render_card, render_plain, render_quote_card, render_tweet_card
from .fetch import download_image
from .providers import find_photo

log = logging.getLogger(__name__)


def quote_fields(story, settings) -> tuple[str, str | None, str, str, bool]:
    """(author, source line, quoted text, when, bold_first_line) for the post-inside-a-post card.

    The card quotes the source's own public text (headline + first sentence, or the bulletin fields) under the source's name.
    The grey line shows where that text comes from: the real @handle when the story *is* a social post (extra.post_url),
    otherwise the website domain. No platform logos, no invented engagement numbers. Paragraphs are separated by a blank
    line; the renderer shows later paragraphs only when they fit whole."""
    import re
    from urllib.parse import urlparse
    from ..textutil import fmt_time, to_local, smart_headline
    from ..writer import _first_sentence, _tidy
    brand = settings.brand
    handles = (brand.get("card", {}) or {}).get("quoted_handles", {}) or {}
    x = story.extra
    kind = story.source_kind
    bold = False
    when = ""
    if story.published:
        local = to_local(story.published, settings.tz)
        when = fmt_time(story.published, settings.tz) if kind in ("nws_alert", "nws_forecast") else local.strftime("%b %d").replace(" 0", " ")
    if kind == "wanted":
        author = x.get("agency", story.source)
        bold = True
        text = (f"WANTED: {x.get('name')}\nWanted for {str(x.get('charge', '')).lower()}.\n"
                f"Crime Stoppers will pay up to {x.get('reward')} for information leading to an arrest. Call {x.get('tip_phone')}.")
    elif kind == "nws_alert":
        author = "NWS Fort Worth"
        bold = True
        text = f"{x.get('event', 'Weather alert')} for {x.get('area', 'Tarrant County')}" + (f" until {x.get('ends_text')}" if x.get("ends_text") else "") + "."
        instr = _first_sentence(x.get("instruction", "")) if x.get("instruction") else ""
        if instr:
            text += f"\n\n{instr}"
    elif kind == "nws_forecast":
        author = "NWS Fort Worth"
        text = f"Today: {x.get('short', '')}, high near {x.get('high', '')}°." + (f" Wind {x['wind']}." if x.get("wind") else "")
        m = re.search(r"Tonight: ([^.]+)\.", story.summary or "")
        if m:
            tonight = m.group(1)
            text += f"\nTonight: {tonight[0] + tonight[1:].lower() if tonight else ''}."
    elif kind in ("event", "event_roundup"):
        author = x.get("venue") or story.source
        bold = True
        text = f"{story.title.split(' at ')[0]}\n{x.get('when', '')}" + (f" · {x.get('venue')}" if x.get("venue") else "")
    elif kind == "arrest_log":
        author = story.source
        bold = True
        text = story.title + "\n" + "\n".join(f"• {e.get('name')} – {_tidy(str(e.get('charge', '')))}" for e in x.get("entries", [])[:6])
    else:
        author = story.source
        first = _first_sentence(story.summary) if story.summary else ""
        head = _tidy(smart_headline(story.title, 110))
        text = head + (f"\n\n{first}" if first and first.lower()[:30] != head.lower()[:30] else "")
    if x.get("post_url"):
        line = handles.get(author) or handles.get(story.source) or urlparse(x["post_url"]).netloc.replace("www.", "")
    else:
        line = urlparse(story.url).netloc.replace("www.", "") if story.url else None
    return author, line, text.strip(), when, bold


def quote_footer(story, credit: str | None) -> str | None:
    """Only a photo credit, and only when the photo is not the source's own (stock / Creative Commons)."""
    if not credit or credit.lower().startswith(("photo: " + story.source.lower(), "radar:", "image: ticketmaster")):
        return None
    if story.image_policy == "source_image" and credit == (story.image_credit or ""):
        return None
    return credit


def short_agency(name: str) -> str:
    """'Fort Worth Police Department' -> 'FWPD', 'Texas DPS' stays."""
    words = [w for w in name.replace("-", " ").split() if w[0].isupper()]
    if len(words) >= 3 and "Police" in words:
        return "".join(w[0] for w in words)
    return name


def _download(url: str, dest: Path, headers: dict | None = None) -> Path | None:
    try:
        return download_image(url, dest, headers=headers)
    except Exception as exc:
        log.warning("image download failed %s: %s", url, exc)
        return None


def plan_image(draft: PostDraft, settings: Settings, state: State, workdir: Path, exclude_photos: set[str] | None = None) -> ImageAsset | None:
    """A real licensed/public photo when possible. In `plain` style a story without a photo returns None (-> link post);
    in `headline` style the branded placeholder card is used instead."""
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
        crime_cfg = brand.get("crime", {}) or {}
        if copy.category == "crime" and crime_cfg.get("mugshots", "official_releases_only") == "never":
            background = None
        else:
            background = _download(story.image_url, workdir / "source")
        if background:
            credit, license_, provider, source_url = story.image_credit or f"Photo: {story.source}", story.image_license or "official", "source", story.url
            if copy.category == "crime":
                fit = "contain"  # booking photos are portraits: never crop a face, show on a blurred backdrop like TV news does
                text = story.text()
                label = "WANTED" if any(w in text for w in ("wanted", "seeking", "searching for", "looking for", "help identify")) else "ARRESTED" if any(w in text for w in ("arrest", "charged", "custody", "booked", "indicted")) else "CRIME"
                subline = story.source.upper()

    if story.source_kind == "arrest_log":
        label, subline = "ARREST LOG", story.source.upper()
    if story.source_kind == "culture":
        label = CATEGORY_LABELS.get(copy.category, "FORT WORTH")
        copy = copy.model_copy(update={"image_query": story.extra.get("image_query") or copy.image_query})
    if story.source_kind == "wanted":
        label = "WANTED"
        subline = f"{story.extra.get('charge', '')} · {short_agency(story.extra.get('agency', story.source))}"[:70]

    if background is None and copy.category == "traffic":
        cam = cameras.snapshot_for(story, settings, workdir)
        if cam:
            background, credit, license_, provider, label = cam.path, cam.credit, cam.license, cam.provider, "LIVE TRAFFIC"

    if background is None and not settings.offline:
        queries = [copy.image_query]
        venue = story.extra.get("venue")
        if story.source_kind in ("event", "event_roundup") and venue:
            # generic genre photo first; a venue photo only when the file is clearly of the building, never another artist's show
            from .providers import PERFORMANCE_WORDS
            venue_words = tuple(w for w in venue.lower().split() if len(w) > 2)
            queries = [(f"category:{venue}", PERFORMANCE_WORDS), copy.image_query,
                       (f"{venue} exterior", PERFORMANCE_WORDS, venue_words), (f"{venue} building", PERFORMANCE_WORDS, venue_words)]
        cand = find_photo(queries, settings, state, exclude=exclude_photos)
        if cand:
            background = _download(cand.url, workdir / "photo")
            if background:
                credit, license_, provider, photo_id, source_url = cand.credit, cand.license, cand.provider, cand.id, cand.source_url
                if exclude_photos is not None:
                    exclude_photos.update({cand.id, cand.family})
                if cand.download_hook and settings.unsplash_access_key:  # Unsplash API guideline: register the download
                    try:
                        from .. import http as _http
                        _http.get(cand.download_hook, headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"}, timeout=10)
                    except Exception:
                        pass

    card_cfg = brand.get("card", {}) or {}
    style = card_cfg.get("style", "tweet")
    if style == "tweet":
        logo = settings.root / str(card_cfg.get("logo") or brand.get("logo") or "assets/logo.png")
        own_photo = provider in ("placeholder", "source", "nws", "ticketmaster")
        show_credit = bool(card_cfg.get("photo_credit_on_card", False)) and not own_photo
        headline = copy.headline or story.title
        out = render_tweet_card(name=brand.get("page_name", ""), handle=brand.get("instagram_handle") or brand.get("handle") or "",
                                headline=headline, photo=background, logo=logo, out_path=workdir / "post.jpg", fonts_dir=settings.fonts_dir,
                                verified=bool(card_cfg.get("verified_badge", False)), credit=credit if show_credit else None)
        with Image.open(out) as im:
            w, h = im.size
        return ImageAsset(path=out, credit=credit if provider != "placeholder" else f"Card: {brand.get('short_name', 'FTW TV')}",
                          license=license_ if provider != "placeholder" else "card", provider=provider if provider != "placeholder" else "card",
                          source_url=source_url, photo_id=photo_id, width=w, height=h)
    if style == "quoted" and story.source_kind not in ("culture",):
        author, handle, text, when, bold = quote_fields(story, settings)
        out = render_quote_card(author=author, handle=handle, when=when, text=text, photo=background, out_path=workdir / "quote.jpg",
                                brand=brand, fonts_dir=settings.fonts_dir, bold_first_line=bold,
                                watermark=(brand.get("instagram_handle") or brand.get("handle")) if card_cfg.get("watermark_handle", True) else None,
                                footer=quote_footer(story, credit if provider != "placeholder" else None))
        with Image.open(out) as im:
            w, h = im.size
        return ImageAsset(path=out, credit=credit if provider != "placeholder" else f"Card: {brand.get('short_name', 'FTW TV')}",
                          license=license_ if provider != "placeholder" else "card", provider=provider if provider != "placeholder" else "quote",
                          source_url=source_url, photo_id=photo_id, width=w, height=h)
    if style in ("plain", "quoted"):
        if background is None:
            if not card_cfg.get("placeholder_when_no_photo", False):
                return None
        else:
            handle = brand.get("instagram_handle") or brand.get("handle")
            out = render_plain(background, workdir / "photo.jpg", brand=brand, fonts_dir=settings.fonts_dir,
                               watermark=handle if card_cfg.get("watermark_handle", True) else None,
                               max_side=int(card_cfg.get("max_side", 1440)))
            from PIL import Image as _Image
            with _Image.open(out) as im:
                width, height = im.size
            return ImageAsset(path=out, credit=credit, license=license_, provider=provider, source_url=source_url, photo_id=photo_id,
                              width=width, height=height)

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
