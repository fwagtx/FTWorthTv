"""Persistent memory of what was posted (committed back to the repo by the GitHub Actions workflow)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import PostDraft, PublishResult

PRUNE_DAYS = 45
MAX_USED_PHOTOS = 80


class State:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = {"version": 1, "posted": {}, "used_photos": [], "last_post_at": None,
                     "daily": {}, "total_posts": 0, "flags": {}}
        self.load()

    # ---- io -------------------------------------------------------------
    def load(self) -> None:
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8") or "{}")
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except json.JSONDecodeError:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---- queries ----------------------------------------------------------
    def has(self, story_id: str) -> bool:
        return story_id in self.data["posted"]

    @property
    def last_post_at(self) -> datetime | None:
        raw = self.data.get("last_post_at")
        return datetime.fromisoformat(raw) if raw else None

    def posts_on(self, day: str) -> int:
        return int(self.data.get("daily", {}).get(day, 0))

    def posts_on_by_category(self, day: str, category: str) -> int:
        return int(self.data.get("daily_by_category", {}).get(day, {}).get(category, 0))

    def photo_recently_used(self, photo_id: str | None) -> bool:
        return bool(photo_id) and photo_id in self.data.get("used_photos", [])

    def flag(self, name: str) -> str | None:
        return self.data.get("flags", {}).get(name)

    def set_flag(self, name: str, value: str) -> None:
        self.data.setdefault("flags", {})[name] = value

    @property
    def total_posts(self) -> int:
        return int(self.data.get("total_posts", 0))

    # ---- mutations --------------------------------------------------------
    def record(self, draft: PostDraft, result: PublishResult, when: datetime, day: str) -> None:
        story = draft.story
        self.data["posted"][story.id] = {
            "at": when.isoformat(),
            "title": story.title[:140],
            "url": story.url,
            "source": story.source,
            "kind": story.source_kind,
            "category": draft.copy.category,
            "publisher": result.publisher,
            "post_id": result.post_id,
            "post_url": result.url,
            "mode": draft.mode,
        }
        self.data["last_post_at"] = when.isoformat()
        self.data.setdefault("daily", {})[day] = self.posts_on(day) + 1
        cat = draft.copy.category or "other"
        by_cat = self.data.setdefault("daily_by_category", {}).setdefault(day, {})
        by_cat[cat] = int(by_cat.get(cat, 0)) + 1
        self.data["total_posts"] = self.total_posts + 1
        if draft.image and draft.image.photo_id:
            used = self.data.setdefault("used_photos", [])
            used.append(draft.image.photo_id)
            del used[:-MAX_USED_PHOTOS]

    def prune(self, now: datetime | None = None, days: int = PRUNE_DAYS) -> int:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)
        posted = self.data.get("posted", {})
        stale = [k for k, v in posted.items() if datetime.fromisoformat(v["at"]) < cutoff]
        for k in stale:
            del posted[k]
        for key in ("daily", "daily_by_category"):
            daily = self.data.get(key, {})
            for day in [d for d in daily if d < cutoff.date().isoformat()]:
                del daily[day]
        return len(stale)
