from __future__ import annotations

from ..config import Settings
from ..models import PostDraft, PublishResult


class Publisher:
    name = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    def publish(self, draft: PostDraft) -> PublishResult:  # pragma: no cover
        raise NotImplementedError


def public_media_url(draft: PostDraft, settings: Settings) -> str | None:
    """Public URL of the post image once the workflow has committed it (MEDIA_BASE_URL + path inside the repo)."""
    if not draft.image or not settings.media_base_url:
        return None
    try:
        rel = draft.image.path.resolve().relative_to(settings.root.resolve()).as_posix()
    except ValueError:
        return None
    return settings.media_base_url.rstrip("/") + "/" + rel
