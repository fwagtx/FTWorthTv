"""Decide which real photo illustrates a post, fetch it legally, and render the branded card."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from PIL import Image

from ..config import Settings
from ..models import CATEGORY_LABELS, ImageAsset, PostDraft, Story
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


_THIRD_PARTY_RE = re.compile(r"\b(courtesy|rendering|renderings|getty|ap photo|associated press|reuters|afp|handout|screenshot|screen grab|file photo|"
                             r"via [A-Z])", re.I)


def third_party_photo(story: Story) -> bool:
    """An outlet's CC terms cover its own photographs: a courtesy rendering, a handout or a wire photo on its page is not ours
    to take. The page's first figure caption and credit are read once and kept on the story."""
    if "page_caption" not in story.extra:
        caption = credit = ""
        if story.url:
            try:
                from ..sources.article import fetch_article
                info = fetch_article(story.url) or {}
                caption, credit = info.get("caption", "") or "", info.get("credit", "") or ""
            except Exception as exc:                                     # the page is unreachable: judge by what we have
                log.info("could not read the page credit for %s: %s", story.url, exc)
        story.extra["page_caption"], story.extra["page_credit"] = caption, credit
    text = f"{story.extra.get('page_caption') or ''} {story.extra.get('page_credit') or ''}"
    return bool(_THIRD_PARTY_RE.search(text))


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
        elif not story.official and third_party_photo(story):
            background = None                      # a courtesy rendering or a wire photo on the outlet's page is not covered by its CC terms
            log.info("source photo is not the outlet's own (%s): no picture", (story.extra.get("page_caption") or "")[:80])
        else:
            background = _download(story.image_url, workdir / "source")
        if background:
            credit, license_, provider, source_url = story.image_credit or f"Photo: {story.source}", story.image_license or "official", "source", story.url
            page_credit = (story.extra.get("page_credit") or "").strip()
            if page_credit and not story.official and page_credit.lower() not in credit.lower() and not _THIRD_PARTY_RE.search(page_credit):
                credit = f"Photo: {page_credit}" if story.source.lower() in page_credit.lower() else f"Photo: {page_credit} / {story.source}"
            lic = str(license_).lower()
            if lic.startswith("cc"):
                tag = lic.upper().replace("CC-", "CC ")
                credit = f"{credit} ({tag})" if tag not in credit else credit
            if lic.startswith("cc") and "nd" in lic.split("-") or lic == "republish-ok":
                fit = "contain"          # NoDerivatives, or a newsroom's own republishing terms: the photo is shown whole, never cropped
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

    subject_label: str | None = None if background is None else "own"
    if background is None:
        # The photo must show what the headline is about (images/subject.py). A named subject gets its own library topic
        # or a provider photo whose file name carries the subject's words; an institution gets the beat that depicts it
        # (buses for a school district); a story with no named subject gets the beats and the city as before; and when
        # nothing verified exists the card goes out with no photo rather than the wrong one.
        from .library import PROVIDER_FIRST, avoid_words_for, pick as pick_library, topics_for
        from .subject import plan_subject
        scope = str(story.extra.get("scope", "local"))
        sp = plan_subject(story.title, story.text(), copy.category)
        weather_text = " ".join(str(x) for x in (story.title, story.extra.get("short"), story.extra.get("event"))).lower()
        if story.source_kind in ("nws_forecast", "nws_alert") or copy.category == "weather" and sp.mode == "beat":
            from .subject import weather_topics
            lib_topics = weather_topics(weather_text)
            sp.mode = "beat"
        elif sp.mode == "entity":
            lib_topics = list(sp.entity_topics)
        elif sp.mode == "institution":
            lib_topics = list(sp.fallback_topics)
        elif sp.mode == "search":
            lib_topics = []
        else:
            lib_topics = topics_for(story.text(), copy.category, scope, title=story.title)
        log.info("photo subject for %r: %s (%s)", story.title[:60], sp.mode, sp.primary or ", ".join(lib_topics[:3]))
        avoid = avoid_words_for(story.text())
        from .subject import happened as _happened
        visual_event = _happened(story.title, story.source_kind)   # a play, a crash, a ceremony: a picture of it or none, never the venue
        library_first = (sp.mode in ("entity", "institution") or (copy.category not in PROVIDER_FIRST and story.source_kind not in ("event", "event_roundup"))) and not visual_event

        def from_library():
            if not lib_topics:
                return None
            return pick_library(settings.root, lib_topics, used=exclude_photos,
                                recently_used=state.photo_recently_used if state is not None else None)

        def label_for_library(photo):
            return f"topic:{photo.topic}" if sp.mode in ("entity", "institution") else f"beat:{photo.topic}"

        lib_photo = from_library() if library_first else None
        if lib_photo is None and not settings.offline:
            if sp.mode in ("entity", "search"):
                from datetime import datetime as _dt, timedelta, timezone as _tz
                from .judge import available as judge_available
                from .subject import provider_queries, wants_recent_picture
                import os as _os
                reviewed = _os.environ.get("FTWTV_PHOTO_REVIEW", "").lower() == "session"   # a person looks at every card before it is posted
                local_city = str(brand.get("city", "Fort Worth")) if str(story.extra.get("scope", "local")) == "local" else ""
                pairs = provider_queries(sp, story.title, copy.category, people_allowed=judge_available(settings) or reviewed, city=local_city)
                queries, labels = [q for q, _ in pairs], [lab for _, lab in pairs]
                recent_flags = [False] * len(queries)
                recent_after = ""
                if wants_recent_picture(story.title, copy.category, story.source_kind):
                    # a picture taken in the two weeks around the story comes first (newest-first queries with a date bar);
                    # the same queries without the bar follow, so an old picture of the venue is the fallback, never the first choice
                    stamp = story.published or _dt.now(_tz.utc)
                    recent_after = (stamp - timedelta(days=14)).date().isoformat()
                    fresh = [(q, lab) for q, lab in pairs if str(q[0]).startswith("fresh:")]
                    queries = [q for q, _ in fresh] + queries
                    labels = [lab for _, lab in fresh] + labels
                    recent_flags = [True] * len(fresh) + [False] * len(pairs)
            elif sp.mode == "institution":
                queries, labels = [], []
            else:
                queries, labels = [copy.image_query], [f"beat:{copy.image_query}"]
                venue = story.extra.get("venue")
                if story.source_kind in ("event", "event_roundup") and venue:
                    # generic genre photo first; a venue photo only when the file is clearly of the building, never another artist's show
                    from .providers import PERFORMANCE_WORDS
                    venue_words = tuple(w for w in venue.lower().split() if len(w) > 2)
                    queries = [(f"category:{venue}", PERFORMANCE_WORDS), copy.image_query,
                               (f"{venue} exterior", PERFORMANCE_WORDS, venue_words), (f"{venue} building", PERFORMANCE_WORDS, venue_words)]
                    labels = [f"entity:{venue.lower()}", f"beat:{copy.image_query}", f"entity:{venue.lower()}", f"entity:{venue.lower()}"]
            from .judge import photo_fits
            if sp.mode not in ("entity", "search"):
                recent_after, recent_flags = "", [False] * len(queries)
            from datetime import datetime as _dt2, timezone as _tz2
            from .subject import photo_age_bar
            stamp_all = story.published or _dt2.now(_tz2.utc)
            for query, lab, recent in zip(queries, labels, recent_flags):
                if visual_event and not recent:
                    continue                                  # only a picture taken at the event will do
                bar = max(recent_after if recent else "", photo_age_bar(lab, stamp_all))   # a 2012 team photo is not the 2026 team
                cand = find_photo([query], settings, state, exclude=exclude_photos, avoid_words=avoid, fallback=sp.mode == "beat",
                                  taken_after=bar)
                if not cand:
                    continue
                background = _download(cand.url, workdir / "photo")
                if background and sp.mode in ("entity", "search"):
                    verdict = photo_fits(settings, headline=copy.headline or story.title, summary=story.summary or "",
                                         title=cand.title or cand.source_url.rsplit("/", 1)[-1].replace("_", " "), alt=cand.alt or "",
                                         credit=cand.credit, path=str(background))
                    if verdict is False:
                        log.info("photo judged off-subject for %r: %s", story.title[:50], cand.source_url)
                        if exclude_photos is not None:
                            exclude_photos.add(cand.id)
                        background = None
                        continue
                if background:
                    credit, license_, provider, photo_id, source_url = cand.credit, cand.license, cand.provider, cand.id, cand.source_url
                    subject_label = lab
                    if exclude_photos is not None:
                        exclude_photos.update({cand.id, cand.family})
                    if cand.download_hook and settings.unsplash_access_key:  # Unsplash API guideline: register the download
                        try:
                            from .. import http as _http
                            _http.get(cand.download_hook, headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"}, timeout=10)
                        except Exception:
                            pass
                    break
        if background is None and lib_photo is None and not visual_event:
            lib_photo = from_library()
        if background is None and lib_photo is not None:
            background = lib_photo.path
            credit, license_, provider, photo_id, source_url = lib_photo.credit, lib_photo.license, "library", lib_photo.id, lib_photo.source_url
            subject_label = label_for_library(lib_photo)
            if exclude_photos is not None:
                exclude_photos.add(lib_photo.id)
        if background is None:
            log.info("no %s of %r: the card goes out without one", "picture of the event itself" if visual_event else "verified photo",
                     sp.primary or story.title[:60])

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
                          source_url=source_url, photo_id=photo_id, width=w, height=h, subject=subject_label)
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
                          source_url=source_url, photo_id=photo_id, width=w, height=h, subject=subject_label)
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
                              width=width, height=height, subject=subject_label)

    mood = {"nws_forecast": "sunrise", "nws_alert": "storm", "event": "dusk", "event_roundup": "dusk"}.get(story.source_kind) or \
        {"food": "day", "business": "day", "community": "day", "weather": "day", "culture": "sunrise", "sports": "dusk"}.get(copy.category, "night")
    out = render_card(
        background=background, headline=copy.headline or story.title, category_label=label, brand=brand,
        out_path=workdir / "card.jpg", fonts_dir=settings.fonts_dir,
        source_line=f"Source: {story.source}", photo_credit=credit if provider != "placeholder" else None,
        subline=subline, fit=fit, logo_path=settings.assets_dir / "logo.png", mood=mood,
    )
    return ImageAsset(path=out, credit=credit, license=license_, provider=provider, source_url=source_url, photo_id=photo_id,
                      width=brand.get("card", {}).get("size", [1080, 1350])[0], height=brand.get("card", {}).get("size", [1080, 1350])[1],
                      subject=subject_label)
