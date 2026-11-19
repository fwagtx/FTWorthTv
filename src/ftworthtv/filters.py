"""Is this story about Fort Worth, fresh, brand-safe, and what kind of story is it?"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime

from .config import Settings
from .models import CATEGORIES, Story
from .state import State

log = logging.getLogger(__name__)

# keyword heuristics used before Claude refines the category (and as the only signal in template mode)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "weather": ["storm", "tornado", "thunder", "hail", "flood", "freeze", "ice storm", "icy", "sleet", "freezing rain", "snow", "heat advisory", "weather",
                "forecast", "rain", "wind advisory", "cold front", "warning for"],
    "traffic": ["crash", "wreck", "i-35w", "35w", "i-30", "i-20", "loop 820", "highway", "lanes closed", "road closure",
                "traffic", "pileup", "18-wheeler", "trinity metro", "texrail", "dfw airport delays"],
    "crime": ["police", "shooting", "shot", "arrested", "arrest", "stabbing", "robbery", "homicide", "murder", "suspect", "steal", "stole",
              "stolen", "theft", "thieves", "bandit", "burglar", "carjack", "wanted", "sentenced", "indicted",
              "fwpd", "deputies", "sheriff", "charged with", "manhunt", "burglary", "carjack"],
    "sports": ["tcu", "horned frogs", "frogs", "cowboys", "rangers", "mavericks", "stars", "fc dallas", "texas motor speedway",
               "nascar", "indycar", "rodeo", "stock show", "panther city", "pga", "colonial", "golf", "football", "basketball", "baseball"],
    "food": ["restaurant", "barbecue", "bbq", "brisket", "taco", "brewery", "bar ", "cafe", "coffee", "bakery", "food hall",
             "menu", "chef", "opens its", "grand opening", "margarita", "tex-mex", "burger", "pizza"],
    "events": ["concert", "festival", "tour", "live at", "dickies arena", "billy bob", "bass hall", "will rogers", "fair",
               "parade", "fireworks", "mayfest", "oktoberfest", "arts festival", "tickets", "show at", "comedy"],
    "culture": ["museum", "kimbell", "amon carter", "modern art", "stockyards", "cattle drive", "sundance square", "cultural district",
                "band", "album", "single", "song", "singer", "residency", "music", "mural", "artist",
                "zoo", "botanic", "theater", "theatre", "gallery", "mural", "historic", "film", "cinema", "documentary", "film festival"],
    "business": ["headquarters", "development", "jobs", "layoffs", "opening", "expansion", "investment", "real estate",
                 "apartments", "retail", "store", "company", "startup", "acquisition"],
    "politics": ["city council", "council vote", "mayor", "election", "ballot", "campaign", "legislature", "governor", "senate",
                 "congress", "republican", "democrat", "isd board", "school board", "trustees", "bond election", "ordinance"],
    "community": ["volunteer", "nonprofit", "fundraiser", "community", "neighborhood", "school", "schools", "students", "library", "park",
                  "church", "celebration", "holiday", "christmas", "thanksgiving", "enrollment", "isd", "superintendent", "teachers",
                  "teacher", "classroom", "campus", "families", "foster", "adoption"],
    "breaking": ["breaking:", "breaking news", "developing:", "developing story", "evacuat", "explosion", "massive fire", "amber alert",
                 "active shooter", "lockdown", "shelter in place"],   # "breaking records" is not breaking news
}


STATEWIDE_WORDS = ("amber alert", "manhunt", "statewide", "across texas", "texas dps", "border patrol", "cartel", "human smuggling",
                   "ercot", "interstate 35 ", "i-35 ", "texas rangers investigat")


_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "after", "as", "by", "is", "are", "was", "be",
         "from", "its", "it", "this", "that", "new", "fort", "worth", "texas", "tx", "says", "say", "said", "will", "over", "into", "up"}


def title_key(title: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9']+", (title or "").lower())
    return frozenset(w for w in words if len(w) > 2 and w not in _STOP)


def same_story(a: str, b: str, threshold: float = 0.7) -> bool:
    """Two headlines about the same event (an outlet's and a station's): the shorter one's content words are mostly
    contained in the other's, and at least four of them match."""
    ka, kb = title_key(a), title_key(b)
    if len(ka) < 3 or len(kb) < 3:
        return False
    shared = len(ka & kb)
    return shared >= 4 and shared / min(len(ka), len(kb)) >= threshold


def relevance_score(story: Story, keywords: list[str]) -> int:
    title = story.title.lower()
    summary = story.summary.lower()
    score = 0
    for kw in keywords:
        kw = kw.lower()
        if _has_word(kw, title):
            score += 2
        elif _has_word(kw, summary):
            score += 1
    return score


OBIT_TITLE_RE = re.compile(r"\b(19|20)\d{2}\b.*[–\-—].*\b(19|20)\d{2}\b")   # "Jane Doe – June 29, 1932 – Nov. 8, 2026"


def blocked(story: Story, blocklist: list[str]) -> str | None:
    text = story.text()
    for term in blocklist or []:
        if term.lower() in text:
            return term
    if OBIT_TITLE_RE.search(story.title) and len(story.title) < 90:
        return "obituary (name + life dates)"
    if re.search(r"/obit", story.url or "", re.I) or re.search(r"\b(passed away|in loving memory|funeral services?)\b", text):
        return "obituary"
    return None


_WORD_RE: dict[str, "re.Pattern[str]"] = {}


def _has_word(word: str, text: str) -> bool:
    """Whole-word match so 'rain' does not fire on 'drainage' or 'art' on 'party'."""
    pat = _WORD_RE.get(word)
    if pat is None:
        pat = _WORD_RE[word] = re.compile(r"(?<![a-z0-9])" + re.escape(word.strip()) + r"(?![a-z0-9])", re.I)
    return bool(pat.search(text))


def infer_category(story: Story) -> str:
    text = story.text()
    title = story.title.lower()
    best, best_hits = None, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        hits = sum(1 for w in words if _has_word(w, text))
        # title hits count double
        hits += sum(1 for w in words if _has_word(w, title))
        if hits > best_hits:
            best, best_hits = cat, hits
    if story.category_hint and (best_hits == 0 or story.category_hint in ("weather", "events", "sports", "crime")):
        return story.category_hint if story.category_hint in CATEGORIES else (best or "other")
    return best or story.category_hint or "other"


def is_fresh(story: Story, now: datetime, max_age_hours: float) -> bool:
    if story.source_kind in ("nws_alert", "nws_forecast", "event", "event_roundup", "wanted", "arrest_log", "culture"):
        return True
    if story.published is None:
        return True  # feeds without dates: trust the feed order / dedupe state
    return story.age_hours(now) <= max_age_hours


def filter_stories(stories: list[Story], settings: Settings, state: State, now: datetime) -> tuple[list[Story], list[tuple[Story, str]]]:
    """Returns (kept, [(story, reason)]) and annotates kept stories with category + relevance."""
    rel = settings.relevance
    keywords = rel.get("keywords", ["fort worth"])
    blocklist = rel.get("blocklist", [])
    excluded = set(rel.get("exclude_categories", []) or [])
    min_rel = int(rel.get("min_relevance", 2))
    max_age = float(settings.since_hours or rel.get("max_age_hours", 36))

    kept: list[Story] = []
    dropped: list[tuple[Story, str]] = []
    recent_titles = state.recent_titles(now, hours=72)
    watchlist = [w.lower() for w in (rel.get("watchlist", []) or [])]
    national_terms = [w.lower() for w in (rel.get("national_keywords", []) or [])]
    min_outlets = int(rel.get("national_min_outlets", 2))
    # how many national outlets carry each big-moment term right now: one outlet is a story, several is a moment
    def _plain(title: str) -> str:   # feeds use non-breaking spaces, curly quotes and emoji: match on plain text
        t = unicodedata.normalize("NFKC", title or "").lower().replace("’", "'").replace("‘", "'")
        return re.sub(r"\s+", " ", t)

    term_outlets: dict[str, set[str]] = {}
    for s in stories:
        if s.extra.get("national"):
            t = _plain(s.title)
            for term in national_terms:
                if term in t:
                    term_outlets.setdefault(term, set()).add(s.source)
    for story in stories:
        if state.has(story.id):
            dropped.append((story, "already posted"))
            continue
        twin = next((t for t in recent_titles if same_story(story.title, t)), None)
        if twin:
            dropped.append((story, f"already posted from another outlet: {twin[:60]}"))
            continue
        if not is_fresh(story, now, max_age):
            dropped.append((story, f"older than {max_age:.0f}h"))
            continue
        term = blocked(story, blocklist)
        if term:
            dropped.append((story, f"blocklist: {term}"))
            continue
        if story.source_kind == "rss" and not story.official and len(story.title.split()) < 4:
            dropped.append((story, "title too short to be a story"))         # "Notes and News", column stubs
            continue
        story.relevance = relevance_score(story, keywords)
        story.extra.setdefault("scope", "local")
        if not story.always_relevant and story.relevance < min_rel:
            # the Dallas page is Dallas-first but posts DFW and Texas-wide stories every day (new Texas bills, H-E-B,
            # gas prices, outages). Keep those at a lower weight and a lower share; drop the rest.
            tier = None
            for name, mult in (("dfw", 0.85), ("texas", 0.7)):
                tier_keys = rel.get(f"{name}_keywords", []) or []
                if tier_keys and relevance_score(story, tier_keys) >= 2:
                    tier = (name, mult)
                    break
            if tier is None and story.extra.get("national"):
                title = _plain(story.title)
                hit = next((w for w in watchlist if w in title), None)
                if hit is None:
                    hit = next((t for t in national_terms if t in title and len(term_outlets.get(t, ())) >= min_outlets), None)
                if hit and infer_category(story) in ("crime", "traffic"):
                    hit = None
                if hit and any(hit in t.lower() for t in recent_titles):
                    dropped.append((story, f"national moment already covered: {hit}"))
                    continue
                if hit:
                    tier = ("national", 0.6)
                    story.extra["national_term"] = hit
            if tier is None:
                why = "national outlet, no watchlist or shared big-moment term" if story.extra.get("national") else f"not local enough (relevance {story.relevance} < {min_rel})"
                dropped.append((story, why))
                continue
            cat = infer_category(story)
            if tier[0] == "texas" and cat in ("crime", "traffic", "food", "events") and not any(w in story.text() for w in STATEWIDE_WORDS):
                dropped.append((story, f"other-metro {cat}, not statewide"))   # a San Antonio DWI verdict or food truck is not Fort Worth news
                continue
            story.extra["scope"] = tier[0]
            story.weight *= tier[1]
            if cat == "sports":        # Texas teams are followed like local news
                story.weight = min(story.weight / tier[1] * 0.9, story.weight * 1.3)
            story.relevance = min_rel
        story.category = infer_category(story)
        if story.category in excluded:
            dropped.append((story, f"excluded category: {story.category}"))
            continue
        kept.append(story)
    return kept, dropped
