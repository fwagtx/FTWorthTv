"""Publishing from a Claude session through the Metricool connector, with a person looking at every card first.

GitHub Actions generates the posts (render.yml: live sources, dry run, cards committed to a renders/<run> branch). A
scheduled Claude session then runs `ftworthtv session queue <run_dir> --branch <renders branch>`, which writes a
manifest with, for every draft, the headline, the caption, the first comment, the public image URLs and the exact
Metricool payloads; the session opens each card, keeps or fixes it, schedules the kept ones with the connector, and
records them with `ftworthtv session record`. No API token, no secret, and nothing is posted that nobody looked at.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .checks import preflight
from .config import Settings
from .models import PostDraft, PublishResult
from .queue import load_draft, review_log
from .state import State

log = logging.getLogger(__name__)
RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def raw_url(repo: str, branch: str, run_dir: Path, path: Path | None, root: Path) -> str | None:
    """Public URL of a file in the run folder as committed on the renders branch (the branch holds out/runs/<run>/...)."""
    if not path or not Path(path).exists():
        return None
    posix = Path(path).as_posix()
    if "out/runs/" not in posix:
        return None
    rel = "out/runs/" + posix.split("out/runs/", 1)[-1]
    return RAW.format(repo=repo, branch=branch, path=rel)


def payloads(draft: PostDraft, image_url: str | None, story_url: str | None, when_local: datetime, tz, networks: list[str],
             stories_cfg: dict) -> dict:
    """The Metricool createScheduledPost `info` for the post and (when a story image exists) its Story."""
    text = draft.caption_text()
    media = [image_url] if image_url and draft.mode != "link" else []
    nets = list(networks)
    if not media and "instagram" in nets:
        nets.remove("instagram")                     # Instagram takes no link posts
    if draft.mode in ("link", "share") or not media:
        text += f"\n\n{draft.link or draft.story.url}"
    post = {
        "providers": [{"network": n} for n in nets],
        "publicationDate": {"dateTime": when_local.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": str(tz)},
        "text": text, "media": media, "mediaAltText": [draft.copy.headline] if media else [],
        "autoPublish": True, "draft": False, "firstCommentText": draft.first_comment_text(), "shortener": False,
        "descendants": [], "smartLinkData": {"ids": []}, "hasNotReadNotes": False,
    }
    if "facebook" in nets:
        post["facebookData"] = {"type": "POST"}
    if "instagram" in nets:
        post["instagramData"] = {"type": "POST", "showReelOnFeed": True, "isAiGenerated": False}
    story = None
    if story_url and stories_cfg.get("enabled", True) and media:
        wanted = [n for n in (stories_cfg.get("networks") or ["facebook", "instagram"]) if n in networks]
        at = when_local + timedelta(minutes=int(stories_cfg.get("delay_minutes", 2)))
        story = {
            "providers": [{"network": n} for n in wanted],
            "publicationDate": {"dateTime": at.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": str(tz)},
            "text": "", "media": [story_url], "mediaAltText": [draft.copy.headline], "autoPublish": True, "draft": False,
            "firstCommentText": "", "shortener": False, "descendants": [], "smartLinkData": {"ids": []}, "hasNotReadNotes": False,
        }
        if "facebook" in wanted:
            story["facebookData"] = {"type": "STORY"}
        if "instagram" in wanted:
            story["instagramData"] = {"type": "STORY", "showReelOnFeed": True, "isAiGenerated": False}
    return {"post": post, "story": story}


def latest_scheduled(state: State) -> datetime | None:
    """The latest publication time recorded in state (a session may have scheduled posts for later today)."""
    times = []
    for info in state.data.get("posted", {}).values():
        try:
            times.append(datetime.fromisoformat(info["at"]))
        except Exception:
            continue
    return max(times) if times else None


def build_manifest(run_dir: Path, settings: Settings, *, branch: str, repo: str, start: datetime | None = None,
                   spacing_minutes: int | None = None) -> list[dict]:
    """One entry per draft folder: what to look at, what to check, what to send. Posts already in the memory are skipped
    and the rest are spaced like the pipeline would space them."""
    state = State(settings.state_path)
    posting = settings.brand.get("posting", {}) or {}
    spacing = int(spacing_minutes or posting.get("min_minutes_between_posts", 25))
    networks = [str(n) for n in (posting.get("networks") or ["facebook", "instagram"])]   # the brand's networks, not an env var
    tz = settings.tz
    when = (start or datetime.now(timezone.utc) + timedelta(minutes=6)).astimezone(tz)
    latest = latest_scheduled(state)
    if latest is not None and latest + timedelta(minutes=spacing) > when:   # posts already scheduled ahead: queue behind them
        when = (latest + timedelta(minutes=spacing)).astimezone(tz)
    rows: list[dict] = []
    for folder in sorted(p for p in Path(run_dir).iterdir() if p.is_dir()):
        draft = load_draft(folder)
        if not draft:
            continue
        if state.has(draft.story.id):
            rows.append({"folder": str(folder), "story_id": draft.story.id, "skip": "already posted", "headline": draft.copy.headline})
            continue
        card = next((folder / n for n in ("post.jpg", "card.jpg", "photo.jpg", "quote.jpg") if (folder / n).exists()), None)
        story_img = folder / "story.jpg" if (folder / "story.jpg").exists() else None
        image_url = raw_url(repo, branch, run_dir, card, settings.root) if draft.mode != "link" else None
        story_url = raw_url(repo, branch, run_dir, story_img, settings.root)
        problems = preflight(draft, network=False)
        im = draft.image
        rows.append({
            "folder": str(folder), "story_id": draft.story.id, "headline": draft.copy.headline, "title": draft.story.title,
            "source": draft.story.source, "url": draft.story.url, "category": draft.copy.category,
            "scope": draft.story.extra.get("scope", "local"), "mode": draft.mode, "link": draft.link,
            "card": str(card) if card else None, "image_url": image_url, "story_url": story_url,
            "photo": {"subject": im.subject, "credit": im.credit, "provider": im.provider, "source_url": im.source_url} if im else None,
            "caption": draft.caption_text(), "first_comment": draft.first_comment_text(),
            "problems": problems, "at": when.isoformat(),
            "metricool": payloads(draft, image_url, story_url, when, tz, networks, settings.brand.get("stories", {}) or {}),
        })
        when += timedelta(minutes=spacing)
    return rows


def cap_held(run_dir: Path) -> list[tuple[str, str, str]]:
    """(story_id, title, reason) for the run's drafts that only a daily category cap kept out (from report.json)."""
    path = Path(run_dir) / "report.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("skipped_by_writer", []) or []
    except (json.JSONDecodeError, AttributeError):
        return []
    return [(str(r["id"]), str(r.get("title", "")), str(r.get("reason", ""))) for r in rows
            if isinstance(r, dict) and r.get("id") and str(r.get("reason", "")).startswith("daily cap for")]


# what the writer says when a story it tried cannot be used as it stands; the same story fails the same way next run
WRITER_RETRY_REASONS = ("no picture of the subject that we may use", "no summary to post: the feed gave only a headline")


def writer_failed(run_dir: Path) -> list[tuple[str, str, str]]:
    """(story_id, title, reason) for the run's stories the writer tried and could not use (from report.json)."""
    path = Path(run_dir) / "report.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("skipped_by_writer", []) or []
    except (json.JSONDecodeError, AttributeError):
        return []
    return [(str(r["id"]), str(r.get("title", "")), str(r.get("reason", ""))) for r in rows
            if isinstance(r, dict) and r.get("id") and str(r.get("reason", "")) in WRITER_RETRY_REASONS]


def record_posted(run_dir: Path, settings: Settings, posted: dict[str, dict], skipped: dict[str, str] | None = None) -> int:
    """posted: {story_id: {"post_id": ..., "story_post_id": ..., "at": iso}} -> state + review log, like the publish step.
    skipped: {story_id: reason} for drafts the session chose not to post; they are remembered so no later render redrafts them."""
    state = State(settings.state_path)
    n = 0
    titles = {}
    for folder in sorted(p for p in Path(run_dir).iterdir() if p.is_dir()):
        try:
            d = load_draft(folder)
            titles[d.story.id] = d.story.title
        except Exception:
            continue
    for story_id, reason in (skipped or {}).items():
        if not state.has(story_id):
            state.mark_skipped(story_id, reason, datetime.now(timezone.utc), title=titles.get(story_id, ""))
    for sid, title, reason in cap_held(Path(run_dir)):
        if not state.has(sid) and sid not in posted and not state.skipped(sid):
            state.defer(sid, title, reason, datetime.now(timezone.utc))      # tomorrow's render may still take it
    for sid, title, reason in writer_failed(Path(run_dir)):
        if not state.has(sid) and sid not in posted and not state.skipped(sid):
            state.mark_tried(sid, title, reason, datetime.now(timezone.utc))   # the next runs give its slot to another story
    for folder in sorted(p for p in Path(run_dir).iterdir() if p.is_dir()):
        draft = load_draft(folder)
        if not draft or draft.story.id not in posted or state.has(draft.story.id):
            continue
        info = posted[draft.story.id]
        when = datetime.fromisoformat(info["at"]) if info.get("at") else datetime.now(timezone.utc)
        result = PublishResult(ok=True, publisher="metricool-session", post_id=str(info.get("post_id") or ""),
                               url=info.get("url"), detail=f"scheduled from a session; story {info.get('story_post_id', '')}")
        day = when.astimezone(settings.tz).date().isoformat()
        state.record(draft, result, when, day)
        review_log(settings, draft, result, when, extra={k: info[k] for k in ("image_url", "networks") if info.get(k)})
        n += 1
    state.prune(datetime.now(timezone.utc))
    state.save()
    return n
