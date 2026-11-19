import json
import subprocess
import sys
from pathlib import Path

SAMPLE = {"page": {"name": "Reference"}, "posts": [
    {"posted_at": "2026-11-13T15:20:00-06:00", "caption": "Rep. Eddie Morales Jr. of Eagle Pass filed House Bill 410. It would make it illegal for ICE agents in Texas to cover their faces.",
     "media_type": "photo", "media_description": "x_screenshot of their own post with a photo of an ICE agent", "headline_on_card": "New Texas bill filed would ban ICE agents from wearing masks",
     "reactions": 17100, "comments": 2100, "shares": 692},
    {"posted_at": "2026-11-13T18:05:00-06:00", "caption": "Things got heated between Cowboys and 49ers fans at Texas Live during the game. Arlington police responded to the scene. 🚨",
     "media_type": "video", "media_description": "fan video", "reactions": 9000, "comments": 1500, "shares": 774},
    {"posted_at": "2026-11-14T09:00:00-06:00", "caption": "Dallas was ranked the top U.S. Thanksgiving destination for 2026", "media_type": "photo",
     "media_description": "x_screenshot", "reactions": 3000, "comments": 200, "shares": 100},
]}


def test_ingest_writes_profile_and_examples(settings, tmp_path, monkeypatch):
    src = tmp_path / "study.json"; src.write_text(json.dumps(SAMPLE), encoding="utf-8")
    root = settings.root
    before = {(root / "config" / n).exists() for n in ("reference_profile.json", "caption_examples.json")}
    out = subprocess.run([sys.executable, str(root / "scripts" / "ingest_reference_posts.py"), str(src)], capture_output=True, text=True, check=True)
    try:
        prof = json.loads((root / "config" / "reference_profile.json").read_text())
        ex = json.loads((root / "config" / "caption_examples.json").read_text())
        assert prof["posts_studied"] == 3 and prof["days_covered"] == 2 and prof["share_screenshot_cards"] > 0.5
        assert prof["category_mix"].get("politics", 0) > 0 and prof["suggested_caps_per_day"]["politics"] == 0
        assert ex[0]["caption"].startswith("Rep. Eddie Morales") and "suggested" in out.stdout
        from ftworthtv.writer import build_system_prompt
        prompt = build_system_prompt(settings)
        assert "REAL CAPTIONS FROM THE REFERENCE PAGE" in prompt and "Texas Live" in prompt
    finally:
        if not any(before):   # leave the repo as it was when no study had been ingested
            for n in ("reference_profile.json", "caption_examples.json"):
                (root / "config" / n).unlink(missing_ok=True)
