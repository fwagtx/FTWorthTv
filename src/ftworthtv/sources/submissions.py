"""Viewer clips, approved by hand in a shared Google Sheet, posted as native video with credit.

The page's "DM us your videos & photos" line brings clips in by Messenger, Instagram and e-mail. A person checks that the
sender shot the clip and agreed to its use, drops the file in the public uploads folder and adds a row to the sheet:
credit | caption | where | video link | consent | approved. Nothing is posted that is not marked consented AND approved:
viewer video is the one place a human stays in the loop, because consent cannot be automated. Station and creator video
is never re-uploaded; those channels are shared as YouTube links (sources/youtube.py).

The sheet is read as CSV (File > Share > "Anyone with the link", or File > Share > Publish to web > CSV), the clips come
from Google Drive links in the public folder (or any direct mp4 URL). The pipeline downloads a clip once, keeps it under
out/submissions/, and remembers what it posted, so an approved row is posted exactly once.
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dtparse

from .. import http
from ..config import Settings
from ..models import Story

log = logging.getLogger(__name__)

YES = {"yes", "y", "true", "x", "✓", "✔", "1", "ok", "approved", "consented", "agreed"}
COLUMNS = {   # a header cell is matched by any of these words, so the sheet can be a Form's response tab or hand-typed
    "credit": ("credit", "name", "who"),
    "caption": ("caption", "what", "description", "text"),
    "where": ("where", "location", "place"),
    "video": ("video", "link", "url", "file", "clip", "photo"),
    "kind": ("kind", "type"),
    "consent": ("consent", "permission", "agree"),
    "approved": ("approved", "approve", "ok to post", "publish", "post"),
    "when": ("timestamp", "date", "when", "time"),
}
_DRIVE_ID = (re.compile(r"/file/d/([A-Za-z0-9_-]{10,})"), re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"), re.compile(r"/open\?id=([A-Za-z0-9_-]{10,})"))


def drive_file_id(url: str) -> str | None:
    for pat in _DRIVE_ID:
        m = pat.search(url or "")
        if m and "drive.google.com" in url:
            return m.group(1)
    return None


def download_urls(url: str) -> list[str]:
    """A Drive share link becomes the direct-download endpoints (the usercontent one skips the virus-scan page);
    anything else is taken as a direct file URL."""
    fid = drive_file_id(url)
    if fid:
        return [f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t",
                f"https://drive.google.com/uc?export=download&id={fid}&confirm=t"]
    return [url]


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in YES


def map_columns(header: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, cell in enumerate(header):
        low = (cell or "").strip().lower()
        for key, words in COLUMNS.items():
            if key not in cols and any(w in low for w in words):
                cols[key] = i
                break
    return cols


def parse_rows(text: str) -> list[dict]:
    """CSV text -> [{credit, caption, where, video, consent, approved, when}] for rows that have a video link."""
    if not text or "<html" in text[:300].lower():
        raise ValueError("the sheet did not come back as CSV (is it shared with 'anyone with the link'?)")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    cols = map_columns(rows[0])
    if "video" not in cols:
        raise ValueError(f"no video/link column in the sheet header: {rows[0]}")
    out = []
    for raw in rows[1:]:
        cells = [c.strip() for c in raw] + [""] * (len(rows[0]) - len(raw))
        get = lambda key: cells[cols[key]] if key in cols else ""   # noqa: E731
        if not get("video").startswith("http"):
            continue
        out.append({k: get(k) for k in COLUMNS})
    return out


def submission_id(video_url: str) -> str:
    return "submission:" + (drive_file_id(video_url) or hashlib.sha1(video_url.encode("utf-8")).hexdigest()[:16])


IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")


def is_photo_link(url: str, kind: str = "") -> bool:
    """A photo by its extension, by the sheet's Kind column, or (for a Drive link) by the file's content type."""
    if (kind or "").strip().lower().startswith(("photo", "image", "pic")):
        return True
    if (kind or "").strip().lower().startswith("video"):
        return False
    if url.lower().split("?")[0].endswith(IMAGE_EXT):
        return True
    if drive_file_id(url):
        try:
            resp = http.session().head(download_urls(url)[0], timeout=20, allow_redirects=True)
            return (resp.headers.get("Content-Type") or "").lower().startswith("image/")
        except Exception:
            return False
    return False


def photo_story(row: dict, now: datetime, direct_url: str, city: str) -> Story:
    """A viewer photo: the picture itself is the post (image_policy source_image), credited to the sender."""
    base = row_story(row, now, Path("/dev/null"), city)
    credit = base.extra["credit"]
    base.image_url, base.image_policy, base.image_credit = direct_url, "source_image", f"Photo: {credit}"
    base.extra.pop("video_path", None)
    base.extra["photo"] = True
    return base


def row_story(row: dict, now: datetime, clip: Path, city: str) -> Story:
    caption = re.sub(r"\s+", " ", row["caption"]).strip()
    where = row["where"] or city
    first = re.split(r"(?<=[.!?])\s+", caption, maxsplit=1)[0] if caption else ""
    title = (first if 12 <= len(first) <= 120 else caption[:117].rsplit(" ", 1)[0] + "…" if len(caption) > 120 else caption) or f"Viewer video from {where}"
    when = now
    if row.get("when"):
        try:
            when = dtparse.parse(row["when"])
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        except (ValueError, OverflowError):
            pass
    credit = row["credit"].strip() or "a viewer"
    return Story(id=submission_id(row["video"]), source="Viewer video", source_kind="submission", title=title, summary=caption,
                 url="", published=when, category_hint="community", image_url=None, image_credit=f"Video: {credit}",
                 image_license="viewer-consented", image_policy="none", official=False, always_relevant=True, weight=1.0,
                 extra={"video_path": str(clip), "credit": credit, "where": where, "scope": "local", "submission": True,
                        "video_link": row["video"]})


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("submissions", {}) or {}
    csv_url = os.environ.get("FTWTV_SUBMISSIONS_CSV_URL") or str(cfg.get("csv_url") or "")
    if not cfg.get("enabled", False) or not csv_url.startswith("http") or settings.offline:
        return []
    try:
        text = http.get(csv_url, timeout=30).text
        rows = parse_rows(text)
    except Exception as exc:
        log.warning("submissions sheet not read: %s", exc)
        return []
    from ..state import State
    posted = State(settings.state_path)
    max_mb = float(cfg.get("max_mb", 200))
    max_age_days = float(cfg.get("max_age_days", 14))
    clips_dir = settings.out_dir / "submissions"
    stories: list[Story] = []
    for row in rows:
        if not (truthy(row["approved"]) and truthy(row["consent"])):
            continue                                   # the two human decisions nothing here can make
        sid = submission_id(row["video"])
        if posted.has(sid):
            continue
        if row.get("when"):
            try:
                when = dtparse.parse(row["when"])
                when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
                if (now - when).total_seconds() > max_age_days * 86400:
                    continue                           # an old row somebody approved late is not news any more
            except (ValueError, OverflowError):
                pass
        if is_photo_link(row["video"], row.get("kind", "")):
            stories.append(photo_story(row, now, download_urls(row["video"])[0], settings.brand.get("city", "Fort Worth")))
            continue
        clip = clips_dir / f"{sid.split(':', 1)[1]}.mp4"
        if not clip.exists():
            for url in download_urls(row["video"]):
                try:
                    http.download(url, clip, max_bytes=int(max_mb * 1_000_000),
                                  allowed_prefixes=("video/", "application/octet-stream"), timeout=120)
                    break
                except Exception as exc:               # the virus-scan page, a private file, too big: try the next form, then give up
                    log.info("clip not fetched from %s: %s", url, exc)
                    clip.unlink(missing_ok=True)
        if not clip.exists() or clip.stat().st_size < 20_000:
            log.warning("submission %s skipped: clip not available (%s)", sid, row["video"])
            clip.unlink(missing_ok=True)
            continue
        stories.append(row_story(row, now, clip, settings.brand.get("city", "Fort Worth")))
    log.info("submissions: %d approved clip(s) ready", len(stories))
    return stories
