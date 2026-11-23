"""One scheduled run: collect -> filter -> rank -> write -> illustrate -> publish -> remember."""
from __future__ import annotations

import re

import html
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .filters import filter_stories
from .images import plan_image
from .images.video import gif_to_mp4
from .models import PostDraft, PublishResult, Story
from .publishers import get_publisher
from .ranking import pick, rank
from .sources import collect
from .state import State
from .textutil import slugify
from .writer import write_copy

log = logging.getLogger(__name__)


@dataclass
class RunReport:
    started: datetime
    run_dir: Path
    candidates: int = 0
    drafts: list[PostDraft] = field(default_factory=list)
    results: list[PublishResult] = field(default_factory=list)
    dropped: list[tuple[Story, str]] = field(default_factory=list)
    skipped: list[tuple[Story, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    ranked: list[Story] = field(default_factory=list)          # kept after the filters, best first (the review sees what waits)

    def summary(self) -> str:
        lines = [f"run {self.run_dir.name}: {self.candidates} candidates, {len(self.drafts)} post(s)"]
        for draft, result in zip(self.drafts, self.results):
            flag = "OK " if result.ok else "ERR"
            lines.append(f"  {flag} [{draft.copy.category}] {draft.story.title[:70]}  ->  {result.publisher}: {result.detail}")
        for note in self.notes:
            lines.append(f"  note: {note}")
        return "\n".join(lines)


def in_quiet_hours(local: datetime, window) -> bool:
    if not window or len(window) != 2:
        return False
    start, end = int(window[0]), int(window[1])
    if start == end:
        return False
    if start < end:
        return start <= local.hour < end
    return local.hour >= start or local.hour < end


WRITER_POOL_MIN = 12      # ranked candidates the writer may look at in one run, however few posts it needs
TEXT_CARD_CATEGORIES = ("crime", "breaking", "traffic", "weather", "sports")   # hard news and results may go out as a text card when no licensed picture exists


def run(settings: Settings, *, now: datetime | None = None, stories: list[Story] | None = None,
        publisher_name: str | None = None, only_kinds: list[str] | None = None) -> RunReport:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(settings.tz)
    day = local.date().isoformat()
    posting = settings.posting
    run_dir = settings.out_dir / "runs" / local.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    report = RunReport(started=now, run_dir=run_dir)
    state = State(settings.state_path)

    # 1. collect + filter + rank
    stories = collect(settings, now) if stories is None else stories
    if only_kinds:
        stories = [s for s in stories if s.source_kind in only_kinds]
    report.candidates = len(stories)
    kept, report.dropped = filter_stories(stories, settings, state, now)
    ranked = rank(kept, now)
    report.ranked = list(ranked)
    log.info("%d candidates -> %d kept after filters", len(stories), len(kept))

    # 2. cadence gates
    quiet = in_quiet_hours(local, posting.get("quiet_hours_local"))
    min_gap = timedelta(minutes=int(posting.get("min_minutes_between_posts", 75)))
    last_at = state.last_post_at
    scheduled_ahead = last_at is not None and last_at > now           # a session scheduled the last post for later
    publisher_label = (publisher_name or settings.publisher).lower()
    renders_for_session = publisher_label == "dryrun"               # the session spaces its posts itself (build_manifest): a render never waits
    gap_ok = last_at is None or scheduled_ahead or renders_for_session or (now - last_at) >= min_gap
    cap_left = int(posting.get("daily_cap", 10)) - state.posts_on(day)
    per_run = settings.max_posts
    if local.hour in (posting.get("peak_hours_local") or []):       # the reference page's 7-11am and 4pm waves
        per_run = max(per_run, int(posting.get("peak_max_posts_per_run", per_run)))
    k = max(0, min(per_run, cap_left))
    mix = settings.brand.get("content_mix", {}) or {}
    import os
    non_local_left = int(os.environ.get("FTWTV_NON_LOCAL_PER_RUN") or mix.get("non_local_per_run", 1))
    non_local_day_left = int(mix.get("non_local_per_day", 8)) - state.non_local_posts_on(day)
    national_day_left = int(mix.get("national_per_day", 2)) - state.posts_on_scope(day, "national")
    videos_day_left = int((settings.sources.get("youtube", {}) or {}).get("max_per_day", 4)) - state.posts_on_kind(day, "video")
    clips_day_left = int((settings.sources.get("submissions", {}) or {}).get("max_per_day", 2)) - state.posts_on_kind(day, "submission")
    wanted_day_left = int((settings.sources.get("wanted", {}) or {}).get("max_per_day", 3)) - state.posts_on_kind(day, "wanted")
    if quiet:
        report.notes.append(f"quiet hours ({local.strftime('%H:%M')} local): only severe weather posts")
    if not gap_ok:
        report.notes.append("too soon since the last post: only severe weather posts")
    if scheduled_ahead:
        report.notes.append(f"last post is scheduled ahead ({last_at.astimezone(settings.tz).strftime('%H:%M')} local); new posts are spaced after it")
    if cap_left <= 0:
        report.notes.append("daily cap reached")

    # 3. write + illustrate
    drafts: list[PostDraft] = []
    used_photos: set[str] = set()
    pool = max(max(k, 1) * 3, WRITER_POOL_MIN)           # a few stuck candidates (a cap, a twin) must not starve the run

    def day_budget_spent(story: Story) -> str | None:
        """A kind whose share of the day is already used can never be drafted today: it must not take a pool slot.
        Nov 21, 10:49 pm: six wanted bulletins and three videos filled the pool and the Mavericks' and FC Dallas'
        recaps, ranked 13th and 14th, were never written."""
        if story.is_urgent:
            return None
        if story.source_kind == "wanted" and wanted_day_left <= 0:
            return "wanted bulletins for today are used up"
        if story.source_kind == "video" and videos_day_left <= 0:
            return "video share used (a few a day, one a run)"
        if story.source_kind == "submission" and clips_day_left <= 0:
            return "viewer clip used (a couple a day, one a run)"
        if story.extra.get("scope", "local") != "local":
            if non_local_day_left <= 0:
                return "DFW/Texas share used (per run or per day)"
            if story.extra.get("scope") == "national" and national_day_left <= 0:
                return "national share used (two a day, one a run)"
        return None

    draftable: list[Story] = []
    for story in ranked:
        why = day_budget_spent(story)
        if why:
            report.skipped.append((story, why))
        else:
            draftable.append(story)
    for story in pick(draftable, pool):
        if len(drafts) >= k and not story.is_urgent:
            break
        if (quiet or not gap_ok or cap_left <= 0) and not story.is_urgent:
            continue
        wanted_cap = int(os.environ.get("FTWTV_WANTED_MAX_PER_RUN") or (settings.sources.get("wanted", {}) or {}).get("max_per_run", 1))
        if story.source_kind == "wanted" and sum(1 for d in drafts if d.story.source_kind == "wanted") >= wanted_cap:
            continue
        if story.source_kind == "wanted" and wanted_day_left - sum(1 for d in drafts if d.story.source_kind == "wanted") <= 0:
            report.skipped.append((story, "wanted bulletins for today are used up"))   # a feed is not a registry
            continue
        caps = (settings.brand.get("content_mix", {}) or {}).get("caps_per_day", {}) or {}
        cat = story.category or "other"
        if cat == "weather" and story.source_kind in ("rss", "video") and _same_outlet_forecast(state, story, now):
            report.skipped.append((story, "this outlet's forecast already went out in the last 12 hours"))
            continue
        from .filters import same_story
        if any(same_story(story.title, d.story.title) for d in drafts):
            report.skipped.append((story, "same story as one already chosen this run"))
            continue
        if story.source_kind == "video":
            if videos_day_left <= 0 or any(d.story.source_kind == "video" for d in drafts):
                report.skipped.append((story, "video share used (a few a day, one a run)"))
                continue
        from .filters import stale_dated_title
        if stale_dated_title(story.title, now.astimezone(settings.tz)):
            report.skipped.append((story, "dated for a day that has passed"))
            continue
        if story.source_kind == "submission":
            if clips_day_left <= 0 or any(d.story.source_kind == "submission" for d in drafts):
                report.skipped.append((story, "viewer clip used (a couple a day, one a run)"))
                continue
        if story.extra.get("scope") in ("texas", "national") and story.source_kind == "rss" and not story.is_urgent \
                and _source_posts_on(state, story.source, day) >= 1:
            report.skipped.append((story, "this statewide outlet already had its post today"))   # Nov 23: two Texas Tribune
            continue                                                                             # agenda explainers in an hour
        if story.extra.get("scope", "local") != "local" and not story.is_urgent:
            if non_local_left <= 0 or non_local_day_left <= 0:
                report.skipped.append((story, "DFW/Texas share used (per run or per day)"))
                continue
            if story.extra.get("scope") == "national":
                if national_day_left <= 0 or any(d.story.extra.get("scope") == "national" for d in drafts):
                    report.skipped.append((story, "national share used (two a day, one a run)"))
                    continue
        if cat in caps and not story.is_urgent and story.source_kind != "wanted":        # bulletins have their own daily cap (wanted.max_per_day)
            used_today = state.posts_on_by_category(day, cat) + sum(1 for d in drafts if (d.copy.category or "other") == cat)
            if cat == "crime":                                                        # the morning's bulletins must not silence the day's crime news
                used_today -= state.posts_on_kind(day, "wanted") + sum(1 for d in drafts if d.story.source_kind == "wanted")
            if used_today >= int(caps[cat]) and story.source_kind != "submission":   # viewer clips have their own cap
                report.skipped.append((story, f"daily cap for {cat} reached"))
                continue
        from .writer import cut_off
        if not settings.offline and story.source_kind == "rss" and not story.official and (len(story.summary or "") < 160 or cut_off(story.summary or "")):
            from .sources.article import enrich_summary
            enrich_summary(story)      # the feed gave a teaser (short, or cut off with "..."): read the article lead
            from .filters import same_personnel_news
            twin = state.recent_title_like(story.title, now, hours=48, match=lambda x, y: same_personnel_news(x, story.summary or "", y))
            twin = twin or next((d.story.title for d in drafts if same_personnel_news(story.title, story.summary or "", d.story.title)), None)
            if twin:                   # the lead the article gave names the departure already posted ("Change in Leadership")
                report.skipped.append((story, f"same news already posted: {twin[:60]}"))
                continue
        copy, writer = write_copy(story, settings, now, force_template=story.source_kind == "submission")   # a viewer's words stay theirs
        if copy.skip:
            report.skipped.append((story, copy.skip_reason or "writer skipped"))
            continue
        if story.source_kind == "rss" and _stale_relative_time(state, story, copy.caption or "", now):
            report.skipped.append((story, "its caption says 'overnight' or 'this morning', but the event was first reported over 14 hours ago"))
            continue
        from .checks import caption_problems
        problems = caption_problems(copy, story, writer=writer)
        if problems and writer != "template":        # a Claude caption the source does not support: use the source's own sentences
            log.warning("caption by %s failed the source check (%s); using the template writer", writer, problems[0])
            copy, writer = write_copy(story, settings, now, force_template=True)
            problems = [] if copy.skip else caption_problems(copy, story, writer=writer)
        if problems:
            report.skipped.append((story, "caption not supported by the source: " + problems[0]))
            continue
        draft = PostDraft(story=story, copy=copy, writer=writer)
        n = len(drafts) + 1
        workdir = run_dir / f"{n:02d}-{slugify(story.title)}"
        link_mode = posting.get("news_photo_mode", "card") == "link"
        if story.extra.get("facebook_post_url"):   # submissions / sources that give us a public post: share it as a nested post
            draft.mode, draft.link = "share", story.extra["facebook_post_url"]
            workdir.mkdir(parents=True, exist_ok=True)
        elif story.source_kind == "submission" and story.extra.get("video_path") and Path(story.extra["video_path"]).exists():   # a viewer photo falls through to the photo path
            workdir.mkdir(parents=True, exist_ok=True)       # the clip itself is the post: cycle.sh hosts it, the publisher posts it
            import shutil
            draft.video_path = Path(shutil.copyfile(story.extra["video_path"], workdir / "clip.mp4"))
            draft.mode = "video"
        elif story.source_kind in ("reddit", "video") or (story.source_kind == "rss" and link_mode and (story.image_policy == "none" or not story.image_url)):
            draft.mode, draft.link = "link", story.url     # a YouTube link: Facebook renders the channel's video, playable, credited
            workdir.mkdir(parents=True, exist_ok=True)
        else:
            draft.mode = "photo"
            try:
                draft.image = plan_image(draft, settings, state, workdir, exclude_photos=used_photos)
                if draft.image is None:
                    workdir.mkdir(parents=True, exist_ok=True)
                    draft.mode, draft.link = ("link", story.url) if story.url else ("text", None)
                if draft.image and draft.image.photo_id:
                    used_photos.add(draft.image.photo_id)
                if draft.image and draft.image.provider in ("card", "placeholder") and story.source_kind == "event":
                    report.skipped.append((story, "event listing without its own picture"))
                    draft = None
                if draft is None:
                    continue
                if draft.image and draft.image.provider in ("card", "placeholder") and story.source_kind == "rss" and story.url:
                    if posting.get("link_when_no_photo", False):
                        # the article's own photo appears through Facebook's link preview (the outlet's image, no copy made)
                        draft.image, draft.story_path, draft.mode, draft.link = None, None, "link", story.url
                        report.notes.append(f"link post (outlet's own photo in the preview): {story.title[:60]}")
                    elif draft.image.provider == "card" and ((copy.category or "other") in TEXT_CARD_CATEGORIES or story.is_urgent):
                        # hard news with no licensed picture of it still goes out, as a text card: an original post with
                        # nothing to mismatch (a fan's death at the stadium must not wait for a photo that cannot exist)
                        report.notes.append(f"text card (no licensed picture of the subject): {story.title[:60]}")
                    else:
                        # the owner wants original posts only: a link preview reads as a post inside a post. No picture
                        # of the subject, no post.
                        report.skipped.append((story, "no picture of the subject that we may use"))
                        continue
                stories_cfg = settings.brand.get("stories", {}) or {}
                if draft.image and stories_cfg.get("enabled", True) and Path(draft.image.path).exists():
                    try:
                        from .images.card import render_story
                        card_cfg = settings.brand.get("card", {}) or {}
                        logo = settings.root / str(card_cfg.get("logo") or settings.brand.get("logo") or "assets/logo.png")
                        draft.story_path = render_story(Path(draft.image.path), workdir / "story.jpg", brand=settings.brand,
                                                        fonts_dir=settings.fonts_dir, logo=logo)
                    except Exception as exc:
                        log.warning("story image failed for %s: %s", story.title[:60], exc)
                crime_cfg = settings.brand.get("crime", {}) or {}
                if copy.category == "crime" and draft.image and draft.image.provider == "source" and crime_cfg.get("disclaimer"):
                    draft.copy = copy.model_copy(update={"first_comment": copy.first_comment.rstrip() + "\n" + crime_cfg["disclaimer"]})
            except Exception as exc:
                log.warning("image pipeline failed for %s: %s", story.title[:60], exc)
                draft.mode, draft.link = "link", story.url
            if story.source_kind == "nws_alert" and posting.get("weather_radar_video", False) and story.extra.get("radar_loop") and not settings.offline:
                try:
                    from . import http
                    gif = http.download(story.extra["radar_loop"], workdir / "radar_loop.gif", headers={"User-Agent": settings.nws_user_agent})
                    mp4 = gif_to_mp4(gif, workdir / "radar.mp4")
                    if mp4:
                        draft.video_path, draft.mode = mp4, "video"
                except Exception as exc:
                    log.warning("radar video failed: %s", exc)
        if drafts:  # space multiple posts out instead of dropping them at the same minute
            draft.scheduled_at = now + min_gap * len(drafts)
        sponsor = settings.brand.get("sponsor", {}) or {}
        if sponsor.get("enabled") and sponsor.get("line") and (state.total_posts + len(drafts) + 1) % max(1, int(sponsor.get("every_n_posts", 5))) == 0:
            draft.sponsor_line = sponsor["line"]
        drafts.append(draft)
        # the shares are spent by drafts, never by candidates that failed on the way (a Dallas story with no picture must not
        # use up the DFW share for the NBC 5 forecast behind it)
        if story.source_kind == "video":
            videos_day_left -= 1
        if story.source_kind == "submission":
            clips_day_left -= 1
        if story.extra.get("scope", "local") != "local" and not story.is_urgent:
            non_local_left -= 1
            non_local_day_left -= 1
            if story.extra.get("scope") == "national":
                national_day_left -= 1

    # 4. publish + remember
    publisher = get_publisher(publisher_label, settings, run_dir)
    for draft in drafts:
        result = publisher.publish(draft)
        report.drafts.append(draft)
        report.results.append(result)
        if result.ok:
            state.record(draft, result, now, day)
        log.info("%s %s -> %s", "posted" if result.ok else "FAILED", draft.story.title[:60], result.detail)
    if publisher.name == "dryrun":
        state.path = run_dir / "state-after-dry-run.json"  # never let a dry run pollute the real memory
    state.prune(now)
    state.save()
    write_report(report, settings)
    return report


def _rel(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def write_report(report: RunReport, settings: Settings) -> None:
    rows = []
    for draft, result in zip(report.drafts, report.results):
        rows.append({
            "title": draft.story.title, "source": draft.story.source, "kind": draft.story.source_kind, "category": draft.copy.category,
            "mode": draft.mode, "writer": draft.writer, "score": draft.story.score, "ok": result.ok, "publisher": result.publisher,
            "post_id": result.post_id, "post_url": result.url, "detail": result.detail,
            "scheduled_at": draft.scheduled_at.isoformat() if draft.scheduled_at else None,
            "image": _rel(draft.image.path if draft.image else None, settings.root),
        })
    data = {
        "started": report.started.isoformat(), "candidates": report.candidates, "posts": rows,
        "skipped_by_writer": [{"title": s.title, "reason": r, "id": s.id, "source": s.source, "url": s.url,
                               "published": s.published.isoformat() if s.published else None}
                              for s, r in report.skipped],          # source + url: the reviewing session can look the story up
        "dropped": [{"title": s.title, "source": s.source, "reason": r} for s, r in report.dropped[:600]],
        # every story that passed the filters, best first: a TCU result that waits behind three drafts is visible to the review
        "waiting": [{"title": s.title, "source": s.source, "id": s.id, "category": s.category, "score": round(float(getattr(s, "score", 0) or 0), 4),
                     "scope": s.extra.get("scope", "local"), "published": s.published.isoformat() if s.published else None}
                    for s in report.ranked[:60] if s.id not in {d.story.id for d in report.drafts}],
        "notes": report.notes,
    }
    (report.run_dir / "report.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_preview(report, settings)


def write_preview(report: RunReport, settings: Settings) -> Path:
    """A Facebook-feed-looking HTML page of this run's posts, for eyeballing before you go live."""
    b = settings.brand
    cards = []
    for draft, result in zip(report.drafts, report.results):
        img = ""
        if draft.image:
            rel = Path(draft.image.path).relative_to(report.run_dir).as_posix()
            img = f'<img src="{html.escape(rel)}" alt="">'
        elif draft.mode == "share":
            img = f'<div class="linkbox">🔁 Shared post: Facebook renders the original post nested inside ours<br><small>{html.escape(draft.link or "")}</small></div>'
        elif draft.mode == "link":
            img = f'<div class="linkbox">🔗 Link post: Facebook will render the outlet\'s own preview photo<br><small>{html.escape(draft.link or "")}</small></div>'
        when = draft.scheduled_at.astimezone(settings.tz).strftime("%b %d, %I:%M %p") if draft.scheduled_at else "Just now"
        status = "✅ " + html.escape(result.detail) if result.ok else "❌ " + html.escape(result.detail)
        cards.append(f"""
<article class="post">
  <header><div class="avatar">{html.escape(b.get('short_name', 'FTW'))[:3]}</div>
    <div><b>{html.escape(b.get('page_name', ''))}</b><br><small>{when} · 🌎 · {html.escape(draft.copy.category)} · {html.escape(draft.writer)} writer</small></div></header>
  <pre class="caption">{html.escape(draft.caption_text())}</pre>
  {img}
  <div class="meta">👍 ❤️ 😮 &nbsp; <span>{status}</span></div>
  <div class="comment"><div class="avatar small">{html.escape(b.get('short_name', 'FTW'))[:3]}</div><pre>{html.escape(draft.first_comment_text())}</pre></div>
  <details><summary>story + scoring</summary><pre>{html.escape(json.dumps({
      'source': draft.story.source, 'kind': draft.story.source_kind, 'score': draft.story.score, 'relevance': draft.story.relevance,
      'url': draft.story.url, 'image_license': draft.image.license if draft.image else None, 'image_credit': draft.image.credit if draft.image else None,
  }, indent=2, ensure_ascii=False))}</pre></details>
</article>""")
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in report.notes)
    skipped = "".join(f"<li><b>{html.escape(s.title[:90])}</b> — {html.escape(r)}</li>" for s, r in report.skipped)
    dropped = "".join(f"<li>{html.escape(s.title[:90])} <small>({html.escape(s.source)}: {html.escape(r)})</small></li>" for s, r in report.dropped[:60])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(b.get('page_name', 'FTWorthTv'))} preview</title>
<style>
:root{{--bg:#f0f2f5;--card:#fff;--text:#050505;--muted:#65676b;--accent:{b.get('colors', {}).get('accent', '#F2B134')}}}
@media (prefers-color-scheme:dark){{:root{{--bg:#18191a;--card:#242526;--text:#e4e6eb;--muted:#b0b3b8}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.4 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}}
main{{max-width:560px;margin:0 auto;padding:16px}}
.post{{background:var(--card);border-radius:10px;box-shadow:0 1px 2px rgba(0,0,0,.2);margin:0 0 20px;overflow:hidden}}
header{{display:flex;gap:10px;align-items:center;padding:12px 16px}}
.avatar{{width:40px;height:40px;border-radius:50%;background:var(--accent);color:#14182B;font-weight:800;display:flex;align-items:center;justify-content:center;flex:none;font-size:13px}}
.avatar.small{{width:28px;height:28px;font-size:10px}}
pre{{white-space:pre-wrap;font:inherit;margin:0}}
.caption{{padding:0 16px 12px}}
img{{display:block;width:100%}}
.linkbox{{margin:0 16px 12px;padding:16px;border:1px solid #ccd0d5;border-radius:8px;color:var(--muted)}}
.meta{{padding:10px 16px;color:var(--muted);border-top:1px solid rgba(0,0,0,.08);display:flex;justify-content:space-between;gap:12px}}
.comment{{display:flex;gap:8px;padding:8px 16px 14px}}
.comment pre{{background:var(--bg);border-radius:16px;padding:8px 12px;flex:1}}
details{{padding:0 16px 14px;color:var(--muted)}} summary{{cursor:pointer}}
h1{{font-size:18px}} ul{{color:var(--muted);font-size:13px}} small{{color:var(--muted)}}
</style></head><body><main>
<h1>{html.escape(b.get('page_name', ''))} — run {html.escape(report.run_dir.name)}</h1>
<p><small>{report.candidates} candidates · {len(report.drafts)} post(s) · publisher: {html.escape(report.results[0].publisher if report.results else settings.publisher)}</small></p>
{''.join(cards) or '<p>No posts this run.</p>'}
{f'<h3>Notes</h3><ul>{notes}</ul>' if notes else ''}
{f'<h3>Skipped by the writer</h3><ul>{skipped}</ul>' if skipped else ''}
{f'<h3>Filtered out ({len(report.dropped)})</h3><ul>{dropped}</ul>' if dropped else ''}
</main></body></html>"""
    out = report.run_dir / "preview.html"
    out.write_text(page, encoding="utf-8")
    latest = settings.out_dir / "latest-preview.html"
    latest.write_text(page.replace('src="', f'src="runs/{report.run_dir.name}/'), encoding="utf-8")
    return out


def _same_outlet_forecast(state, story, now) -> bool:
    """Nov 23: WFAA's 'Possible Frost and Freeze for North Texas This Week' went out at 6:47 and WFAA's 'Chilly temperatures
    to start the week, here's your Thanksgiving forecast' was drafted for 7:12: one outlet's forecast is one post a morning."""
    from datetime import datetime as _dt, timezone as _tz
    for info in (state.data.get("posted", {}) or {}).values():
        if info.get("category") != "weather" or info.get("source") != story.source:
            continue
        try:
            at = _dt.fromisoformat(str(info.get("at", "")))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=_tz.utc)
        if abs((now - at).total_seconds()) <= 12 * 3600:
            return True
    return False


def _source_posts_on(state, source: str, day: str) -> int:
    """How many statewide or national posts one outlet had on a local day. A local station's own local stories do not count:
    Nov 23, NBC 5's Texas Tech result was held as "this statewide outlet already had its post today" after NBC 5's local
    shooting, schedule and parade posts. Entries recorded before scopes were stored count as before."""
    return sum(1 for info in (state.data.get("posted", {}) or {}).values()
               if info.get("source") == source and str(info.get("at", ""))[:10] == day
               and info.get("scope", "texas") in ("texas", "national"))


_RELATIVE_TIME_RE = re.compile(r"\b(?:overnight|last night|this morning|early this morning|this afternoon|this evening|tonight|"
                               r"early (?:today|sunday|monday|tuesday|wednesday|thursday|friday|saturday) morning)\b", re.I)


def _stale_relative_time(state, story, caption: str, now) -> bool:
    """Nov 23: NBC 5's 'Driver arrested after car crashes into Bedford business following pursuit' (published 2 a.m.
    Monday) said 'The crash happened overnight'; FOX 4 had reported the same crash Sunday morning, and a cap held both.
    A caption that dates the event relative to today cannot run once the event is more than 14 hours old."""
    if not _RELATIVE_TIME_RE.search(caption or ""):
        return False
    from datetime import datetime as _dt, timezone as _tz
    from .filters import same_story
    first = story.published
    for bucket in ("deferred", "posted", "skipped"):
        for info in (state.data.get(bucket, {}) or {}).values():
            if not isinstance(info, dict) or not info.get("title") or not same_story(story.title, info["title"]):
                continue
            try:
                at = _dt.fromisoformat(str(info.get("at", "")))
            except ValueError:
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=_tz.utc)
            first = at if first is None or at < first else first
    return first is not None and (now - first).total_seconds() > 14 * 3600
