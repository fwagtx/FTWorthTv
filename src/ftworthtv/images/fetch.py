"""Download an image and normalize it to an RGB JPEG we can draw on."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .. import http


def download_image(url: str, dest: Path, *, headers: dict | None = None, max_side: int = 3000) -> Path:
    if url.startswith("data:image"):  # agencies such as Texas DPS embed the photo in the page
        import base64
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = dest.with_suffix(".download")
        raw.write_bytes(base64.b64decode(url.partition(",")[2]))
    else:
        raw = http.download(url, dest.with_suffix(".download"), headers=headers)
    with Image.open(raw) as im:
        im.load()
        if getattr(im, "is_animated", False):
            im.seek(0)
        rgb = im.convert("RGB")
        if max(rgb.size) > max_side:
            rgb.thumbnail((max_side, max_side))
        out = dest.with_suffix(".jpg")
        rgb.save(out, "JPEG", quality=92, optimize=True)
    raw.unlink(missing_ok=True)
    return out
