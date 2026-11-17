"""Traffic cameras: when a traffic story names a road we have a camera for, attach a LIVE snapshot as the photo."""
from __future__ import annotations

import logging
from pathlib import Path

from .. import http
from ..config import Settings
from ..models import ImageAsset, Story

log = logging.getLogger(__name__)


def match_camera(story: Story, cameras: list[dict]) -> dict | None:
    text = story.text()
    for cam in cameras or []:
        for road in cam.get("roads", []) or []:
            if road.lower() in text:
                return cam
    return None


def snapshot_for(story: Story, settings: Settings, dest_dir: Path) -> ImageAsset | None:
    cfg = settings.sources.get("traffic_cameras", {}) or {}
    if settings.offline or not cfg.get("enabled", False):
        return None
    cam = match_camera(story, cfg.get("cameras", []))
    if not cam or not cam.get("snapshot_url"):
        return None
    try:
        path = http.download(cam["snapshot_url"], dest_dir / "camera.jpg")
    except Exception as exc:
        log.warning("camera snapshot failed for %s: %s", cam.get("name"), exc)
        return None
    return ImageAsset(path=path, credit=f"Live camera: {cam.get('name')} (TxDOT)", license="camera",
                      provider="camera", source_url=cam["snapshot_url"], photo_id=None)
