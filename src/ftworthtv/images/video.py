"""Video helpers: the NWS radar loop GIF (public domain) as an MP4, and ffprobe facts about a clip."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def gif_to_mp4(gif_path: Path, out_path: Path, fps: int = 8) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.info("ffmpeg not installed; skipping radar video")
        return None
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(gif_path),
           "-vf", f"fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,format=yuv420p",
           "-movflags", "+faststart", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(out_path)]
    try:
        subprocess.run(cmd, check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        log.warning("ffmpeg failed: %s", exc)
        return None
    return out_path if out_path.exists() else None


def video_dimensions(path: Path) -> tuple[int, int] | None:
    """(width, height) of the first video stream, or None when ffprobe is missing or the file is not a video."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not Path(path).exists():
        return None
    try:
        out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "json", str(path)], capture_output=True, text=True, timeout=60, check=True).stdout
        stream = (json.loads(out).get("streams") or [{}])[0]
        w, h = int(stream.get("width") or 0), int(stream.get("height") or 0)
        return (w, h) if w and h else None
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        log.warning("ffprobe failed for %s: %s", path, exc)
        return None


def is_portrait(path: Path) -> bool:
    dims = video_dimensions(path)
    return bool(dims) and dims[1] >= dims[0]
