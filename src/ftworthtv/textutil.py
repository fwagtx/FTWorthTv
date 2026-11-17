"""Small text helpers shared across the pipeline."""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<\s*br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"</\s*(p|div|li|h\d)\s*>", " ", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return collapse_ws(text)


def collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def truncate(text: str, limit: int, ellipsis: str = "…") -> str:
    text = collapse_ws(text)
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - len(ellipsis))]
    # don't cut in the middle of a word if we can avoid it
    if " " in cut[-20:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-") + ellipsis


def slugify(text: str, limit: int = 48) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").lower()).strip("-")
    return (text[:limit] or "post").strip("-")


def stable_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(p or "" for p in parts).encode("utf-8")).hexdigest()
    return h[:16]


def to_local(dt: datetime | None, tz: ZoneInfo) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def fmt_time(dt: datetime | None, tz: ZoneInfo) -> str:
    """'6:45 PM'"""
    local = to_local(dt, tz)
    if not local:
        return ""
    return local.strftime("%I:%M %p").lstrip("0")


def fmt_day(dt: datetime | None, tz: ZoneInfo) -> str:
    """'Sat, Nov 22'"""
    local = to_local(dt, tz)
    if not local:
        return ""
    return local.strftime("%a, %b %d").replace(" 0", " ")


def relative_day(dt: datetime, now: datetime, tz: ZoneInfo) -> str:
    """'Tonight' / 'Tomorrow' / 'This Saturday' / 'Nov 22' for event captions."""
    d = to_local(dt, tz).date()
    today = to_local(now, tz).date()
    delta = (d - today).days
    if delta <= 0:
        return "Tonight" if to_local(dt, tz).hour >= 16 else "Today"
    if delta == 1:
        return "Tomorrow"
    if delta < 7:
        return "This " + to_local(dt, tz).strftime("%A")
    return fmt_day(dt, tz)


def clean_hashtag(tag: str) -> str:
    tag = re.sub(r"[^0-9A-Za-z_]", "", tag.strip())
    return f"#{tag}" if tag else ""
