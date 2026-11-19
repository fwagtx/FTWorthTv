"""Turn a study of the reference page (Dallas Texas TV) into numbers and examples the pipeline uses.

Input: a JSON file in the schema described in docs/REFERENCE_STUDY.md (what Claude for Chrome brings back):
    {"page": {...}, "posts": [{"posted_at", "caption", "media_type", "media_description", "headline_on_card",
                               "reactions", "comments", "shares", ...}, ...]}
Output:
    config/reference_profile.json   cadence (posts per day, hour-of-day histogram in Central time), media mix,
                                    category mix, caption length and emoji stats, x-screenshot share, suggested caps
    config/caption_examples.json    the 40 best-performing captions with their category and card headline, used by the
                                    Claude writer as real examples of the voice

    python scripts/ingest_reference_posts.py study.json
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/Chicago")
CATEGORY_WORDS = {
    "crime": ("police", "arrest", "shot", "shooting", "stabb", "wanted", "suspect", "charged", "murder", "robbery", "crime", "jail", "officer"),
    "traffic": ("crash", "wreck", "highway", "i-35", "i-30", "635", "loop", "lanes", "closed", "traffic", "tollway", "rollover"),
    "weather": ("weather", "storm", "tornado", "rain", "hail", "snow", "ice", "freeze", "heat", "forecast", "degrees", "flood", "lightning"),
    "sports": ("cowboys", "mavericks", "mavs", "rangers", "stars", "tcu", "fc dallas", "game", "playoff", "coach", "quarterback", "nba", "nfl", "mlb"),
    "events": ("concert", "tour", "tickets", "festival", "parade", "show", "arena", "stadium", "fair", "fest", "performs", "live at"),
    "food": ("restaurant", "taco", "bbq", "barbecue", "burger", "brunch", "bar ", "cafe", "opens", "menu", "chef", "food"),
    "business": ("store", "opening", "company", "hq", "headquarters", "jobs", "development", "mall", "h-e-b", "costco", "buc-ee", "walmart"),
    "politics": ("council", "mayor", "bill", "lawmakers", "governor", "senate", "election", "vote", "ice ", "immigration", "legislature"),
    "community": ("community", "school", "students", "teacher", "church", "volunteer", "fundraiser", "neighborhood", "family", "veteran"),
    "culture": ("dallas is", "ranked", "texas is", "y'all", "only in", "viral", "famous", "celebrity", "spotted", "rapper", "artist", "fans", "video"),
}
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")


def classify(text: str) -> str:
    low = (text or "").lower()
    scores = {cat: sum(low.count(w) for w in words) for cat, words in CATEGORY_WORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "other"


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def main(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    if not posts:
        sys.exit("no posts in the file")
    by_day: dict[str, int] = defaultdict(int)
    hours = Counter()
    media = Counter()
    cats = Counter()
    lengths, emojis, screenshots = [], 0, 0
    scored = []
    for p in posts:
        dt = parse_time(p.get("posted_at"))
        if dt:
            by_day[dt.date().isoformat()] += 1
            hours[dt.hour] += 1
        cap = (p.get("caption") or "").strip()
        media[(p.get("media_type") or "unknown").lower()] += 1
        cat = p.get("category") or classify(cap + " " + (p.get("headline_on_card") or ""))
        cats[cat] += 1
        lengths.append(len(cap))
        emojis += 1 if EMOJI_RE.search(cap) else 0
        desc = ((p.get("media_description") or "") + " " + (p.get("media_type") or "")).lower()
        if "screenshot" in desc or "x_screenshot" in desc or "tweet" in desc:
            screenshots += 1
        eng = (p.get("reactions") or 0) + 3 * (p.get("comments") or 0) + 5 * (p.get("shares") or 0)
        scored.append((eng, cat, cap, p.get("headline_on_card") or "", p.get("media_type") or ""))
    n = len(posts)
    days = max(1, len(by_day))
    per_day = n / days
    cat_share = {c: round(v / n, 3) for c, v in cats.most_common()}
    suggested = {c: max(1, round(share * 12)) for c, share in cat_share.items() if c != "politics"}
    suggested["politics"] = 0
    profile = {
        "source": data.get("page", {}).get("name", "reference page"),
        "posts_studied": n, "days_covered": days, "posts_per_day": round(per_day, 1),
        "hour_of_day_central": {str(h): hours[h] for h in range(24)},
        "busiest_hours_central": [h for h, _ in hours.most_common(6)],
        "media_mix": {m: round(v / n, 3) for m, v in media.most_common()},
        "category_mix": cat_share,
        "caption_chars_median": int(statistics.median(lengths)) if lengths else 0,
        "caption_chars_p90": int(sorted(lengths)[int(len(lengths) * 0.9) - 1]) if lengths else 0,
        "captions_with_emoji": round(emojis / n, 3),
        "share_screenshot_cards": round(screenshots / n, 3),
        "suggested_caps_per_day": suggested,
    }
    (ROOT / "config" / "reference_profile.json").write_text(json.dumps(profile, indent=1), encoding="utf-8")
    scored.sort(key=lambda t: -t[0])
    examples = [{"category": c, "caption": cap, "headline": head, "media_type": mt, "engagement": e}
                for e, c, cap, head, mt in scored if cap][:40]
    (ROOT / "config" / "caption_examples.json").write_text(json.dumps(examples, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(profile, indent=1))
    print(f"\nwrote config/reference_profile.json and config/caption_examples.json ({len(examples)} examples)")
    print("suggested content_mix.caps_per_day for config/brand.yaml:", suggested)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
