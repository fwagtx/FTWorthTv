"""Persistent memory of what was posted (committed back to the repo by the GitHub Actions workflow)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import PostDraft, PublishResult

PRUNE_DAYS = 45
MAX_USED_PHOTOS = 80
DEFER_PRUNE_HOURS = 48      # a cap-held story is forgotten two days after it was held


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

    def skipped(self, story_id: str) -> bool:
        return story_id in self.data.get("skipped", {})

    def mark_skipped(self, story_id: str, reason: str, when: datetime) -> None:
        """A story the reviewing session chose not to post (a Dallas park amenity, a column): it must not be drafted again."""
        self.data.setdefault("skipped", {})[story_id] = {"reason": reason[:140], "at": when.isoformat()}

    def deferred(self, story_id: str) -> bool:
        return story_id in self.data.get("deferred", {})

    def defer(self, story_id: str, title: str, reason: str, when: datetime) -> None:
        """A story a daily cap held back (the fourth community item of a busy day): remembered so the next day's render
        may still draft it while it is under filters.DEFERRED_MAX_AGE_HOURS old, instead of letting it age out of the window."""
        self.data.setdefault("deferred", {}).setdefault(story_id, {"title": title[:140], "reason": reason[:140], "at": when.isoformat()})

    @property
    def last_post_at(self) -> datetime | None:
        raw = self.data.get("last_post_at")
        return datetime.fromisoformat(raw) if raw else None

    def posts_on(self, day: str) -> int:
        return int(self.data.get("daily", {}).get(day, 0))

    def posts_on_by_category(self, day: str, category: str) -> int:
        return int(self.data.get("daily_by_category", {}).get(day, {}).get(category, 0))

    def non_local_posts_on(self, day: str) -> int:
        """DFW-wide and Texas-wide posts made on `day` (the share of the feed that is not Fort Worth / Tarrant County)."""
        by_scope = self.data.get("daily_by_scope", {}).get(day, {})
        return int(by_scope.get("dfw", 0)) + int(by_scope.get("texas", 0)) + int(by_scope.get("national", 0))

    def posts_on_scope(self, day: str, scope: str) -> int:
        return int(self.data.get("daily_by_scope", {}).get(day, {}).get(scope, 0))

    def recent_title_like(self, title: str, now: datetime, hours: int = 48, match=None) -> str | None:
        """The title of a post from the last `hours` that `match(title, posted_title)` says is the same story, else None."""
        if match is None:
            return None
        for info in self.data.get("posted", {}).values():
            try:
                at = datetime.fromisoformat(info.get("at", ""))
            except Exception:
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if abs((now - at).total_seconds()) <= hours * 3600 and match(title, info.get("title", "")):
                return info.get("title", "")
        return None

    def posts_on_kind(self, day: str, kind: str) -> int:
        return int(self.data.get("daily_by_kind", {}).get(day, {}).get(kind, 0))

    def photo_recently_used(self, photo_id: str | None) -> bool:
        return bool(photo_id) and photo_id in self.data.get("used_photos", [])

    def flag(self, name: str) -> str | None:
        return self.data.get("flags", {}).get(name)

    def set_flag(self, name: str, value: str) -> None:
        self.data.setdefault("flags", {})[name] = value

    def recent_titles(self, now: datetime, hours: int = 72) -> list[str]:
        """Titles posted in the last `hours`, so the same story from a second outlet is not posted twice."""
        cutoff = now - timedelta(hours=hours)
        out = []
        for v in self.data.get("posted", {}).values():
            try:
                if datetime.fromisoformat(v["at"]) >= cutoff and v.get("title"):
                    out.append(v["title"])
            except (KeyError, ValueError):
                continue
        return out

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
        prev = self.last_post_at
        if prev is None or when > prev:               # a session records several posts in any order: keep the latest time
            self.data["last_post_at"] = when.isoformat()
        self.data.setdefault("daily", {})[day] = self.posts_on(day) + 1
        cat = draft.copy.category or "other"
        by_cat = self.data.setdefault("daily_by_category", {}).setdefault(day, {})
        by_cat[cat] = int(by_cat.get(cat, 0)) + 1
        scope = story.extra.get("scope", "local")
        by_scope = self.data.setdefault("daily_by_scope", {}).setdefault(day, {})
        by_scope[scope] = int(by_scope.get(scope, 0)) + 1
        by_kind = self.data.setdefault("daily_by_kind", {}).setdefault(day, {})
        by_kind[story.source_kind] = int(by_kind.get(story.source_kind, 0)) + 1
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
        deferred = self.data.get("deferred", {})
        for k in [k for k, v in deferred.items() if datetime.fromisoformat(v["at"]) < now - timedelta(hours=DEFER_PRUNE_HOURS)]:
            del deferred[k]
        for key in ("daily", "daily_by_category", "daily_by_scope"):
            daily = self.data.get(key, {})
            for day in [d for d in daily if d < cutoff.date().isoformat()]:
                del daily[day]
        return len(stale)
