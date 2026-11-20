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
               "longhorns", "aggies", "razorbacks", "sooners", "senior day", "sec championship", "big 12 championship", "touchdown",
               "quarterback", "halftime", "kickoff", "playoff", "head coach",
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


PLACE_WORDS = ("texas", "fort worth", "dallas", "arlington", "dfw", "north texas", "houston", "austin", "san antonio", "el paso", "lubbock",
               "waco", "cowboys", "rangers", "mavericks", "mavs", "dallas stars", "spurs", "astros", "rockets", "texans", "longhorns", "aggies",
               "tcu", "horned frogs", "smu", "baylor", "texas tech", "at&t stadium", "globe life", "ercot", "h-e-b", "buc-ee", "whataburger")
OTHER_METROS = ("austin", "san antonio", "houston", "el paso", "waco", "lubbock", "amarillo", "corpus christi", "dallas", "denton", "plano",
                "frisco", "mckinney", "tyler", "laredo", "midland", "odessa", "abilene", "killeen", "temple", "bryan", "college station",
                "beaumont", "galveston", "the woodlands", "round rock", "new braunfels", "san marcos", "oklahoma city", "tulsa", "shreveport")
_ROUNDUP_RE = re.compile(r"\b(weekend|things to do|this week|events this|what's happening|what to do)\b", re.I)


OTHER_REGIONS = ("south central texas", "central texas", "hill country", "coastal bend", "rio grande valley", "east texas", "west texas",
                 "south texas", "southeast texas", "panhandle", "gulf coast", "big bend", "permian basin", "brazos valley", "deep east texas",
                 "golden triangle", "concho valley", "the valley")


DISASTER_WORDS = ("flood", "tornado", "wildfire", "hurricane", "explosion", "evacuat", "killed", "dead", "dies", "die ", "death", "shooting",
                  "crash", "derail", "outage", "emergency", "rescue", "missing", "amber alert")


def other_region(title: str) -> bool:
    """A story told for another part of the state ('Why fall foliage looks different across South Central Texas'); North
    Texas and statewide stories are not touched."""
    low = (title or "").lower()
    if "north texas" in low or "north central texas" in low or "fort worth" in low or "dfw" in low:
        return False
    if any(w in low for w in DISASTER_WORDS):          # a Hill Country flood is statewide news
        return False
    return any(re.search(r"\b" + re.escape(r) + r"\b", low) for r in OTHER_REGIONS)


_CIVIC_RE = re.compile(r"\b(mayor|mayor pro tem|city council|council ?(?:member|man|woman)|city manager|police chief|fire chief|isd|school board|"
                       r"county judge|commissioners?|city hall|town hall|trustees?|voters?|residents|prop\.? ?[a-z0-9]{1,3}|proposition|"
                       r"bond election|zoning|city budget|tax rate)\b", re.I)


def other_metro_local(title: str) -> bool:
    """'Austin Mayor Pro Tem announces resignation, run for Texas Senate': another city's government is that city's news."""
    low = (title or "").lower()
    if any(w in low for w in ("fort worth", "tarrant", "dfw", "north texas", "arlington", "keller", "southlake", "mansfield")):
        return False
    return bool(_CIVIC_RE.search(low)) and any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS)


def other_metro_roundup(title: str) -> bool:
    """'Austin weekend: Theater performances, Bastrop B-day', 'Things to do in Houston this weekend': another city's events
    calendar, however good the weekend is there."""
    low = (title or "").lower()
    return bool(_ROUNDUP_RE.search(low)) and any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS) and "fort worth" not in low and "tarrant" not in low


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
    ka, kb = {_stem(w) for w in title_key(a)}, {_stem(w) for w in title_key(b)}
    if len(ka) < 3 or len(kb) < 3:
        return False
    shared = len(ka & kb)
    return shared >= 4 and shared / min(len(ka), len(kb)) >= threshold


def _stem(word: str) -> str:
    """reopens/reopen, years/year, explosions/explosion: enough for two headlines about one event to meet."""
    for end in ("ies", "es", "s", "ed", "ing"):
        if len(word) > len(end) + 3 and word.endswith(end):
            return word[:-len(end)] + ("y" if end == "ies" else "")
    return word


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


def _plain(title: str) -> str:
    """Feeds use non-breaking spaces, curly quotes and emoji: match on plain text."""
    t = unicodedata.normalize("NFKC", title or "").lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", t)


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
    if story.source_kind in ("nws_alert", "nws_forecast", "event", "event_roundup", "wanted", "arrest_log", "culture", "submission"):
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
    term_outlets: dict[str, set[str]] = {}
    for s in stories:
        if s.extra.get("national"):
            t = _plain(s.title)
            for term in national_terms:
                if term in t:
                    term_outlets.setdefault(term, set()).add(s.source)
    for story in stories:
        if state.skipped(story.id):
            dropped.append((story, "skipped by the reviewing session"))
            continue
        twin = state.recent_title_like(story.title, now, hours=48, match=same_story)
        if twin:
            dropped.append((story, f"same story already posted (another outlet or format): {twin[:60]}"))   # WFAA's article after WFAA's video of the same reopening
            continue
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
        if story.source_kind in ("rss", "video") and not story.official and len(story.title.split()) < 4:
            dropped.append((story, "title too short to be a story"))         # "Notes and News", column stubs
            continue
        story.relevance = relevance_score(story, keywords)
        story.extra.setdefault("scope", "local")
        if not story.always_relevant and story.relevance < min_rel:
            # the Dallas page is Dallas-first but posts DFW and Texas-wide stories every day (new Texas bills, H-E-B,
            # gas prices, outages). Keep those at a lower weight and a lower share; drop the rest.
            tier = None
            # a national outlet is only "Texas news" when its headline names the place or the team, never on words
            # like "lawmakers" or "governor" that any state's story carries
            place_in_title = any(w in _plain(story.title) for w in PLACE_WORDS)
            for name, mult in (("dfw", 0.85), ("texas", 0.7)):
                tier_keys = rel.get(f"{name}_keywords", []) or []
                if story.extra.get("national") and not place_in_title:
                    continue
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
            if tier[0] == "texas" and other_region(story.title) and not any(w in story.text() for w in STATEWIDE_WORDS):
                dropped.append((story, "another region's story"))              # fall foliage in South Central Texas is KENS 5's weather blog
                continue
            if tier[0] == "texas" and other_metro_local(story.title) and not any(w in story.text() for w in STATEWIDE_WORDS):
                dropped.append((story, "another city's government"))             # Austin's mayor pro tem is Austin's news
                continue
            if tier[0] in ("texas", "dfw") and other_metro_roundup(story.title):
                dropped.append((story, "another city's weekend roundup"))      # "Austin weekend: theater, Bastrop B-day" is KXAN's calendar
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


_DATED_TITLE = re.compile(r"\b(?:for|on)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b", re.I)


def stale_dated_title(title: str, now_local) -> bool:
    """'Fort Worth forecast for Tuesday, November 17' on a Thursday is not news; a title dated before today is dropped."""
    m = _DATED_TITLE.search(title or "")
    if not m:
        return False
    from datetime import date
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    try:
        when = date(now_local.year, months.index(m.group(1).lower()) + 1, int(m.group(2)))
    except ValueError:
        return False
    if when - now_local.date() > __import__("datetime").timedelta(days=200):   # a January date seen in December belongs to next year
        when = when.replace(year=when.year - 1)
    return when < now_local.date()
