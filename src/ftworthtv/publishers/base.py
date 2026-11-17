from __future__ import annotations

from ..config import Settings
from ..models import PostDraft, PublishResult


class Publisher:
    name = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    def publish(self, draft: PostDraft) -> PublishResult:  # pragma: no cover
        raise NotImplementedError
