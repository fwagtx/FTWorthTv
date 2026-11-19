"""Two-phase publishing: `run --publisher dryrun` writes drafts to a run folder; `publish <run_dir>` posts them later.

Needed for Metricool (images must already be public on GitHub) and handy for a human-in-the-loop review step.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dtparse

from .config import Settings
from .models import ImageAsset, PostCopy, PostDraft, PublishResult, Story
from .publishers import get_publisher
from .state import State

log = logging.getLogger(__name__)


def load_draft(folder: Path) -> PostDraft | None:
    meta_path = folder / "post.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    s = dict(meta["story"])
    s["published"] = dtparse.isoparse(s["published"]) if s.get("published") else None
    story = Story(**{k: v for k, v in s.items() if k in Story.__dataclass_fields__})
    copy = PostCopy(**meta["copy"])
    image = None
    if meta.get("image"):
        im = meta["image"]
        path = Path(im["path"])
        if not path.is_absolute():
            path = folder / path
        if not path.exists() and (folder / "card.jpg").exists():
            path = folder / "card.jpg"
        image = ImageAsset(path=path, credit=im.get("credit", ""), license=im.get("license", ""), provider=im.get("provider", ""),
                           source_url=im.get("source_url"), photo_id=im.get("photo_id"), subject=im.get("subject"))
    draft = PostDraft(story=story, copy=copy, writer=meta.get("writer", "unknown"), mode=meta.get("mode", "photo"), image=image,
                      video_path=Path(meta["video"]) if meta.get("video") else None, link=meta.get("link"),
                      story_path=Path(meta["story_image"]) if meta.get("story_image") else None,
                      scheduled_at=dtparse.isoparse(meta["scheduled_at"]) if meta.get("scheduled_at") else None)
    if draft.video_path and not draft.video_path.is_absolute():
        draft.video_path = folder / draft.video_path
    url_file = folder / "video_url.txt"                      # cycle.sh uploads the clip to a GitHub release and leaves its URL here
    if url_file.exists() and url_file.read_text(encoding="utf-8").strip().startswith("http"):
        draft.video_url = url_file.read_text(encoding="utf-8").strip()
    return draft


def publish_run(run_dir: Path, settings: Settings, publisher_name: str) -> list[tuple[PostDraft, PublishResult]]:
    run_dir = Path(run_dir)
    state = State(settings.state_path)
    publisher = get_publisher(publisher_name, settings, run_dir)
    now = datetime.now(timezone.utc)
    day = now.astimezone(settings.tz).date().isoformat()
    out: list[tuple[PostDraft, PublishResult]] = []
    for folder in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        draft = load_draft(folder)
        if not draft:
            continue
        if state.has(draft.story.id):
            log.info("skip %s: already posted", draft.story.title[:60])
            continue
        if draft.scheduled_at and draft.scheduled_at < now:
            draft.scheduled_at = None  # the moment passed while we were committing images: post now
        from .checks import preflight
        problems = preflight(draft, network=publisher.name != "dryrun" and not settings.offline)
        if problems:
            result = PublishResult(ok=False, publisher=publisher.name, detail="held back: " + "; ".join(problems))
            out.append((draft, result))
            log.warning("HELD %s -> %s", draft.story.title[:60], result.detail)
            continue
        result = publisher.publish(draft)
        if result.ok and publisher.name != "dryrun":
            state.record(draft, result, now, day)
        out.append((draft, result))
        log.info("%s %s -> %s", "posted" if result.ok else "FAILED", draft.story.title[:60], result.detail)
    if publisher.name != "dryrun":
        state.prune(now)
        state.save()
    return out
