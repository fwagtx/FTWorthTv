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
    try:
        rel = Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = Path(path).as_posix().split("out/runs/", 1)[-1]
        rel = "out/runs/" + rel
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


def build_manifest(run_dir: Path, settings: Settings, *, branch: str, repo: str, start: datetime | None = None,
                   spacing_minutes: int | None = None) -> list[dict]:
    """One entry per draft folder: what to look at, what to check, what to send. Posts already in the memory are skipped
    and the rest are spaced like the pipeline would space them."""
    state = State(settings.state_path)
    posting = settings.brand.get("posting", {}) or {}
    spacing = int(spacing_minutes or posting.get("min_minutes_between_posts", 25))
    tz = settings.tz
    when = (start or datetime.now(timezone.utc) + timedelta(minutes=6)).astimezone(tz)
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
            "metricool": payloads(draft, image_url, story_url, when, tz, list(settings.metricool_networks or ["facebook", "instagram"]),
                                  settings.brand.get("stories", {}) or {}),
        })
        when += timedelta(minutes=spacing)
    return rows


def record_posted(run_dir: Path, settings: Settings, posted: dict[str, dict]) -> int:
    """posted: {story_id: {"post_id": ..., "story_post_id": ..., "at": iso}} -> state + review log, like the publish step."""
    state = State(settings.state_path)
    n = 0
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
        review_log(settings, draft, result, when)
        n += 1
    state.prune(datetime.now(timezone.utc))
    state.save()
    return n
