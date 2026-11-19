"""One scheduled run: collect -> filter -> rank -> write -> illustrate -> publish -> remember."""
from __future__ import annotations

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
    log.info("%d candidates -> %d kept after filters", len(stories), len(kept))

    # 2. cadence gates
    quiet = in_quiet_hours(local, posting.get("quiet_hours_local"))
    min_gap = timedelta(minutes=int(posting.get("min_minutes_between_posts", 75)))
    gap_ok = state.last_post_at is None or (now - state.last_post_at) >= min_gap
    cap_left = int(posting.get("daily_cap", 10)) - state.posts_on(day)
    per_run = settings.max_posts
    if local.hour in (posting.get("peak_hours_local") or []):       # the reference page's 7-11am and 4pm waves
        per_run = max(per_run, int(posting.get("peak_max_posts_per_run", per_run)))
    k = max(0, min(per_run, cap_left))
    non_local_left = int((settings.brand.get("content_mix", {}) or {}).get("non_local_per_run", 1))
    if quiet:
        report.notes.append(f"quiet hours ({local.strftime('%H:%M')} local): only severe weather posts")
    if not gap_ok:
        report.notes.append("too soon since the last post: only severe weather posts")
    if cap_left <= 0:
        report.notes.append("daily cap reached")

    # 3. write + illustrate
    publisher_label = (publisher_name or settings.publisher).lower()
    drafts: list[PostDraft] = []
    used_photos: set[str] = set()
    for story in pick(ranked, max(k, 1) * 3):
        if len(drafts) >= k and not story.is_urgent:
            break
        if (quiet or not gap_ok or cap_left <= 0) and not story.is_urgent:
            continue
        wanted_cap = int(os.environ.get("FTWTV_WANTED_MAX_PER_RUN") or (settings.sources.get("wanted", {}) or {}).get("max_per_run", 1))
        if story.source_kind == "wanted" and sum(1 for d in drafts if d.story.source_kind == "wanted") >= wanted_cap:
            continue
        caps = (settings.brand.get("content_mix", {}) or {}).get("caps_per_day", {}) or {}
        cat = story.category or "other"
        from .filters import same_story
        if any(same_story(story.title, d.story.title) for d in drafts):
            report.skipped.append((story, "same story as one already chosen this run"))
            continue
        if story.extra.get("scope", "local") != "local" and not story.is_urgent:
            if non_local_left <= 0:
                report.skipped.append((story, "DFW/Texas share for this run used"))
                continue
            non_local_left -= 1
        if cat in caps and not story.is_urgent:
            used_today = state.posts_on_by_category(day, cat) + sum(1 for d in drafts if (d.copy.category or "other") == cat)
            if used_today >= int(caps[cat]):
                report.skipped.append((story, f"daily cap for {cat} reached"))
                continue
        if not settings.offline and story.source_kind == "rss" and not story.official and len(story.summary or "") < 160:
            from .sources.article import enrich_summary
            enrich_summary(story)      # the feed gave a teaser: read the article lead so the caption is a real summary
        copy, writer = write_copy(story, settings, now)
        if copy.skip:
            report.skipped.append((story, copy.skip_reason or "writer skipped"))
            continue
        draft = PostDraft(story=story, copy=copy, writer=writer)
        n = len(drafts) + 1
        workdir = run_dir / f"{n:02d}-{slugify(story.title)}"
        link_mode = posting.get("news_photo_mode", "card") == "link"
        if story.extra.get("facebook_post_url"):   # submissions / sources that give us a public post: share it as a nested post
            draft.mode, draft.link = "share", story.extra["facebook_post_url"]
            workdir.mkdir(parents=True, exist_ok=True)
        elif story.source_kind == "reddit" or (story.source_kind == "rss" and story.image_policy == "none" and link_mode):
            draft.mode, draft.link = "link", story.url
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
        "skipped_by_writer": [{"title": s.title, "reason": r} for s, r in report.skipped],
        "dropped": [{"title": s.title, "source": s.source, "reason": r} for s, r in report.dropped[:200]],
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
