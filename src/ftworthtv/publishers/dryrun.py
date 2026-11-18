"""Writes every post (card + caption + comment + metadata) into the run folder for review. Posts nothing."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..models import PostDraft, PublishResult
from .base import Publisher


class DryRunPublisher(Publisher):
    name = "dryrun"

    def __init__(self, settings, run_dir: Path):
        super().__init__(settings)
        self.run_dir = Path(run_dir)

    def publish(self, draft: PostDraft) -> PublishResult:
        from ..textutil import slugify
        folder = draft.image.path.parent if draft.image else next((p for p in sorted(self.run_dir.glob(f"*-{slugify(draft.story.title)}")) if p.is_dir()), self.run_dir / draft.story.id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "caption.txt").write_text(draft.caption_text() + "\n", encoding="utf-8")
        (folder / "first_comment.txt").write_text(draft.first_comment_text() + "\n", encoding="utf-8")
        story = asdict(draft.story)
        story["published"] = draft.story.published.isoformat() if draft.story.published else None
        meta = {
            "mode": draft.mode, "writer": draft.writer, "link": draft.link,
            "scheduled_at": draft.scheduled_at.isoformat() if draft.scheduled_at else None,
            "image": {"path": str(draft.image.path), "credit": draft.image.credit, "license": draft.image.license,
                      "provider": draft.image.provider, "source_url": draft.image.source_url} if draft.image else None,
            "video": str(draft.video_path) if draft.video_path else None,
            "copy": draft.copy.model_dump(), "story": story,
        }
        (folder / "post.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        return PublishResult(ok=True, publisher=self.name, post_id=None, url=str(folder), detail="written to disk (dry run)")
