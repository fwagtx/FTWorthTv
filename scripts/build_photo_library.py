"""Turn reviewed candidate photos into the verified library the pipeline uses.

    python scripts/build_photo_library.py KEEP.txt out/library/candidates.json [more candidates.json / refs.json ...]

KEEP.txt lists one kept file per line as `<file name>` or `<file name> -> <topic>` (to re-file it); blank lines and
`#` comments are ignored. Each kept photo is resized to at most 1600 px wide, saved as JPEG under assets/photos/<topic>/
and listed in assets/photos/library.json with its credit line and source page. Re-running keeps the existing entries whose
files still exist, so the library can grow over time.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = ROOT / "assets" / "photos"
MAX_W = 1280


def load_candidates(paths: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in paths:
        p = Path(p)
        rows = json.loads(p.read_text(encoding="utf-8"))
        for r in rows:
            r = dict(r)
            r["_dir"] = p.parent
            if "credit" not in r:   # refs.json from fetch_skyline_refs.py
                r["credit"] = f"Photo: {r.get('artist') or 'Wikimedia Commons contributor'} via Wikimedia Commons ({r.get('license', '')})".replace("()", "").strip()
            r.setdefault("source_url", r.get("description_url"))
            r.setdefault("topic", "skyline")
            out[r["file"]] = r
    return out


def clean_credit(credit: str) -> str:
    """Commons boilerplate ("No machine-readable author provided. X assumed (based on copyright claims)") becomes "X"."""
    c = re.sub(r"No machine-readable author provided\.?\s*", "", credit or "")
    c = re.sub(r"\s*assumed\s*\(based on copyright claims\)\.?", "", c)
    return re.sub(r"\s{2,}", " ", c).strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def main() -> None:
    keep_path, cand_paths = sys.argv[1], sys.argv[2:]
    cands = load_candidates(cand_paths)
    lib_path = LIB_DIR / "library.json"
    existing = {e["id"]: e for e in json.loads(lib_path.read_text(encoding="utf-8"))} if lib_path.exists() else {}
    entries = {k: v for k, v in existing.items() if (ROOT / v["file"]).exists()}
    added = 0
    for line in Path(keep_path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, _, topic = (x.strip() for x in line.partition("->"))
        c = cands.get(name)
        if not c:
            print("not a candidate:", name)
            continue
        topic = topic or c["topic"]
        pid = "lib-" + slug(Path(name).stem.split("--", 1)[-1])
        dest = LIB_DIR / topic / (pid[4:] + ".jpg")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(c["_dir"] / name) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.width > MAX_W:
                im = im.resize((MAX_W, int(im.height * MAX_W / im.width)), Image.LANCZOS)
            im.save(dest, "JPEG", quality=80, optimize=True)
            w, h = im.size
        entries[pid] = {"id": pid, "file": dest.relative_to(ROOT).as_posix(), "topic": topic, "title": c.get("title", name),
                        "credit": clean_credit(c["credit"]), "license": "wikimedia-cc", "licence_name": c.get("license", ""),
                        "source_url": c.get("source_url"), "width": w, "height": h}
        added += 1
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    lib_path.write_text(json.dumps(sorted(entries.values(), key=lambda e: (e["topic"], e["id"])), indent=1, ensure_ascii=False), encoding="utf-8")
    by_topic: dict[str, int] = {}
    for e in entries.values():
        by_topic[e["topic"]] = by_topic.get(e["topic"], 0) + 1
    print(f"{added} added, {len(entries)} photos in the library:", ", ".join(f"{t} {n}" for t, n in sorted(by_topic.items())))


if __name__ == "__main__":
    main()
