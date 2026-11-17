"""Optional: turn the NWS radar loop GIF (public domain) into an MP4 for a weather Reel."""
from __future__ import annotations

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
