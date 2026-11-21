"""A curated library of verified, openly licensed photos of Fort Worth (and the Texas places the page covers).

Search engines return "Texas" photos that locals recognise as Houston or Dallas in a second. The library is the opposite:
every file in assets/photos/library.json was looked at and filed under a subject, so a Trinity Metro story gets Central
Station, a court story gets the Tarrant County Courthouse and a statewide bill gets the Capitol. The pipeline tries the
library first for the subjects it knows; search providers remain the fallback for everything else (food, concerts ...).
"""
from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# (phrases in the story text, library topic) - first match wins; specific places before generic beats
TOPIC_RULES: list[tuple[tuple[str, ...], str]] = [
    (("dickies arena",), "dickies-arena"),
    (("will rogers", "stock show"), "will-rogers"),
    (("at&t stadium", "cowboys"), "att-stadium"),
    (("globe life", "rangers"), "globe-life-field"),
    (("dallas stars", "stars goalie", "stars win", "stars lose", "stars beat", "nhl"), "stars-ice"),
    (("american airlines center", "mavericks", "mavs"), "aac"),
    (("fc dallas", "toyota stadium"), "toyota-stadium"),
    (("texas motor speedway", "nascar", "indycar"), "texas-motor-speedway"),
    (("horned frogs", "amon g. carter", "amon carter stadium", "tcu football", "sonny dykes", "tcu quarterback", "tcu vs", "vs. tcu",
      "at tcu", "tcu game", "tcu wins", "tcu loses", "tcu beat", "frogs "), "tcu-football"),
    (("tcu",), "tcu"),
    (("ut arlington", "uta ", "uta mavericks", "texas-arlington"), "uta"),
    (("nrg stadium", "houston texans", "texans "), "nrg-stadium"),
    (("daikin park", "minute maid", "astros"), "daikin-park"),
    (("toyota center", "rockets"), "toyota-center"),
    (("frost bank center", "spurs"), "frost-bank-center"),
    (("longhorns", "ut austin", "university of texas at austin", "darrell k royal"), "ut-austin"),
    (("texas a&m", "aggies", "kyle field"), "texas-am"),
    (("texas tech", "red raiders"), "texas-tech"),
    (("baylor", "mclane stadium"), "baylor"),
    (("smu", "mustangs", "southern methodist"), "smu"),
    (("north texas", "unt ", "mean green"), "unt"),
    (("trinity metro", "texrail", "tex rail", "bus route", "bus rider", "transit", "central station", "microtransit"), "transit"),
    (("tarrant county courthouse", "adoption day", "jury", "verdict", "sentenced", "guilty", "lawsuit", "indicted", "district judge", "courtroom", "courthouse"), "courthouse"),
    (("sundance square",), "sundance-square"),
    (("stockyards", "rodeo", "cattle drive"), "stockyards"),
    (("kimbell",), "kimbell"),
    (("modern art museum", "the modern"), "modern"),
    (("bass hall", "bass performance hall"), "bass-hall"),
    (("fort worth zoo", "zoo "), "zoo"),
    (("botanic garden", "botanical garden"), "botanic-garden"),
    (("water gardens",), "water-gardens"),
    (("convention center",), "convention-center"),
    (("dfw airport", "dfw international", "d/fw airport"), "dfw-airport"),
    (("alliance airport",), "alliance"),
    (("trinity river", "panther island", "trinity trails", "river trail"), "trinity-river"),
    (("h-e-b", "heb "), "heb"),
    (("buc-ee",), "bucees"),
    (("whataburger",), "whataburger"),
    (("ercot", "power grid", "power outage", "outages", "blackout"), "power"),
    (("gas prices", "gasoline", "price of gas", "pump prices"), "gas"),
    (("snap benefits", "snap ", "food bank", "food stamps", "grocery", "groceries"), "grocery"),
    (("property tax", "tax rate", "budget", "salary", "salaries", "wages", "raise", "cost of living", "paycheck"), "money"),
    (("election", "ballot", "early voting", "polls open", "runoff", "voters"), "voting"),
    (("keller isd", "keller high", "fossil ridge", "timber creek", "keller central"), "keller-isd"),
    (("northwest isd", "byron nelson high", "eaton high", "northwest high school"), "northwest-isd"),
    (("isd", "school district", "school board", "enrollment", "students", "teachers", "superintendent", "classroom", "high school", "elementary"), "school-bus"),
    (("isd", "school district", "school board", "enrollment", "students", "teachers", "superintendent", "classroom", "high school", "elementary"), "schools"),
    (("city council", "city hall", "council members", "councilmember", "ordinance", "city manager", "mayor "), "city-hall"),
    (("hospital", "medical center", "jps health", "texas health", "cook children", "baylor scott", "er visits", "patients"), "hospital"),
    (("fire department", "firefighters", "house fire", "apartment fire", "fire crews", "blaze"), "fire"),
    (("jail", "inmate", "detention center", "booked into"), "jail"),
    (("i-35w", "i-30", "i-20", "i-820", "loop 820", "highway", "freeway", "lanes", "crash", "wreck", "pileup", "road closure", "txdot", "interstate"), "highway"),
    (("police", "fwpd", "officers", "shooting", "shot ", "stabbing", "robbery", "homicide", "murder", "arrested", "suspect", "wanted", "carjack", "burglar", "theft"), "police"),
    (("tornado", "thunderstorm", "severe storm", "hail", "lightning", "storms", "flash flood", "wind advisory"), "storm"),
    (("ice storm", "sleet", "freezing rain", "winter storm", "snow", "hard freeze", "freeze warning", "wind chill"), "ice"),
    (("heat advisory", "excessive heat", "triple digit", "heat wave", "100 degrees"), "heat"),
    (("barbecue", "bbq", "brisket"), "bbq"),
    (("taco", "tacos", "taqueria"), "tacos"),
    (("apartments", "apartment complex", "mixed-use", "development", "construction", "developer", "rezoning"), "apartments"),
    (("home prices", "housing", "homebuyers", "mortgage", "homeowners", "neighborhood"), "housing"),
    (("legislature", "lawmakers", "texas house", "texas senate", "governor", "abbott", "state rep", "state sen", "bill filed", "signed into law", "capitol", "attorney general", "paxton"), "capitol"),
    # the national beat
    (("anthropic", "claude ai", "dario amodei"), "anthropic"),
    (("ipo", "initial public offering", "nasdaq", "nyse", "wall street", "stock market", "dow jones", "s&p 500", "shares soar", "shares fall", "market cap"), "stock-market"),
    (("gta vi", "gta 6", "grand theft auto", "playstation", "xbox", "nintendo", "switch 2", "video game", "rockstar games", "steam"), "gaming"),
    (("powerball", "mega millions", "jackpot", "lottery"), "lottery"),
    (("thanksgiving day parade", "macy's parade"), "parade"),
    (("black friday", "cyber monday", "holiday shopping"), "shopping"),
    (("thanksgiving",), "thanksgiving"),
    (("christmas", "holiday lights"), "christmas"),
    (("new year's eve", "fireworks", "fourth of july", "july 4"), "fireworks"),
    (("iphone", "apple ", "samsung galaxy", "android"), "smartphone"),
    (("super bowl", "nfl ", "halftime show"), "nfl"),
    (("spacex", "starship", "nasa", "rocket launch", "astronaut"), "space"),
    (("eclipse",), "eclipse"),
    (("tour dates", "announces tour", "stadium tour", "eras tour", "concert", "grammys", "grammy", "halftime"), "concert"),
    (("album", "single", "billboard", "spotify", "vinyl"), "music"),
    (("box office", "trailer", "movie", "film ", "theaters", "in theaters", "oscars", "oscar"), "movies"),
    (("netflix", "disney+", "hbo", "hulu", "paramount+", "prime video", "finale", "season premiere", "streaming", "series"), "streaming"),
    (("arlington",), "arlington"),
    (("san antonio",), "san-antonio-skyline"),
    (("houston",), "houston-skyline"),
    (("austin",), "austin-skyline"),
    (("dallas",), "dallas-skyline"),
]
# when nothing above matches: by category, then by scope
CATEGORY_DEFAULTS = {"traffic": ["highway"], "crime": ["police"], "politics": ["city-hall"], "weather": ["storm", "skyline"],
                     "business": ["downtown", "skyline"], "community": ["downtown", "sundance-square", "skyline"],
                     "breaking": ["skyline-night", "skyline"], "sports": ["skyline"], "other": ["skyline", "downtown"]}
SCOPE_DEFAULTS = {"local": ["skyline", "downtown", "sundance-square", "skyline-night"], "dfw": ["dallas-skyline", "skyline"],
                  "texas": ["capitol", "skyline"], "national": ["skyline-night", "skyline"]}
PROVIDER_FIRST = {"food", "events", "culture"}     # subjects the library cannot carry well; search engines go first
# a sports story about a school wants its stadium or team, never a lecture hall: the sports variant of a campus topic goes first
SPORTS_VARIANTS = {"tcu": "tcu-football", "uta": "uta-sports", "unt": "unt-football", "ut-austin": "ut-football", "smu": "smu-football"}

_cache: dict[str, list[dict]] = {}


@dataclass
class LibraryPhoto:
    id: str
    path: Path
    topic: str
    credit: str
    license: str
    source_url: str | None


def load_library(root: Path) -> list[dict]:
    key = str(root)
    if key not in _cache:
        p = root / "assets" / "photos" / "library.json"
        try:
            _cache[key] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        except Exception as exc:
            log.warning("photo library unreadable: %s", exc)
            _cache[key] = []
    return _cache[key]


FORT_WORTH_ONLY = {"skyline", "skyline-night", "downtown", "sundance-square", "courthouse", "city-hall", "transit", "stockyards", "police", "fire",
                   "trinity-river", "highway", "police", "fire", "hospital", "water-gardens", "convention-center", "kimbell", "modern",
                   "bass-hall", "zoo", "botanic-garden", "will-rogers", "dickies-arena"}
OTHER_CITIES = ("dallas", "houston", "austin", "san antonio", "arlington", "denton", "plano", "frisco", "carrollton", "irving",
                "garland", "mckinney", "el paso", "lubbock", "waco", "galveston", "corpus christi", "college station", "amarillo")


VENUE_NAMES = {"att-stadium": ("at&t stadium",), "globe-life-field": ("globe life",), "aac": ("american airlines center",),
               "toyota-stadium": ("toyota stadium",), "dickies-arena": ("dickies arena",), "nrg-stadium": ("nrg stadium",),
               "texas-motor-speedway": ("texas motor speedway",), "tcu-football": ("amon g. carter", "amon carter stadium")}
_VENUE_RE = re.compile(r"\b((?:[A-Z][\w&.'’-]*\s+){1,3}(?:Stadium|Arena|Field|Ballpark|Coliseum|Speedway))\b")
_AWAY_RE = re.compile(r"\b(?:visit|visits|visiting|travel to|travels to|traveling to|head to|heads to|road game|road trip|on the road|away game)\b", re.I)


def clean_credit(credit: str) -> str:
    """A stored credit line with Commons boilerplate ("Billy Hathorn assumed (based on copyright c via Wikimedia Commons") loses it."""
    c = re.sub(r"\s*assumed\s*\(based on copyright(?: claims\)\.?| ?\w*)", "", credit or "", flags=re.I)   # whole, or cut short
    c = re.sub(r"\s*No machine-readable author provided\.?", "", c, flags=re.I)
    return re.sub(r"\s{2,}", " ", c).strip()


_GAME_RE = re.compile(r"\b(?:vs\.?|versus|beat|beats|defeat|defeats|win|wins|won|loss|lose|loses|lost|host|hosts|game|kickoff|opener|playoff|playoffs|"
                      r"final|finals|matchup|rematch|tip-?off|first pitch|series|bowl|championship|overtime|shutout|comeback|rally|rallies|score|scores|"
                      r"scored|lead|leads|upset|sweep|swept|clinch|clinches|preview|face|faces|home)\b", re.I)


def venue_fits(topic: str, text: str, title: str | None = None) -> bool:
    """A team name brings its home venue only for a game there: never for a coaching, roster or contract story ("Parker
    disappointed Cowboys pulled play-calling duties"), never when the text names another stadium or says the team is on
    the road. The venue named in the headline is always its own picture."""
    names = VENUE_NAMES.get(topic)
    if not names:
        return True
    low = (text or "").lower()
    head = (title if title is not None else text or "")
    if any(n in head.lower() for n in names):
        return True                                              # the venue itself is in the headline: it is the picture
    if not _GAME_RE.search(head):
        return False                                             # a person or a decision is the subject, not the building
    if any(n in low for n in names):
        return True
    others = [v for v in _VENUE_RE.findall(text or "") if not any(n in v.lower() for n in names)]
    return not others and not _AWAY_RE.search(text or "")


TITLE_ONLY = {"heb", "stock-market", "gaming", "lottery", "parade", "shopping", "thanksgiving", "christmas", "fireworks", "smartphone", "nfl", "space", "eclipse",
              "concert", "music", "movies", "streaming", "att-stadium", "globe-life", "aac", "dickies-arena", "texas-motor-speedway", "amon-carter", "tcu-football", "dallas-skyline"}   # a venue mentioned in passing in the body is never the picture   # a passing mention in the body must not turn a local story into a turkey photo


def topics_for(text: str, category: str, scope: str, title: str | None = None) -> list[str]:
    """Ordered library topics worth trying for a story: specific subject first, then category and scope defaults.
    A story set in another city never gets a Fort Worth landmark (its own city's skyline, a generic subject, or nothing)."""
    low = " " + (text or "").lower() + " "
    head = " " + (title if title is not None else text or "").lower() + " "
    elsewhere = "fort worth" not in low and "tarrant" not in low and any(c in low for c in OTHER_CITIES)
    whole = f"{title or ''} {text or ''}"                      # original case: another venue's name is read from capitals
    out: list[str] = []
    for phrases, topic in TOPIC_RULES:
        hay = head if topic in TITLE_ONLY else low
        if any(p in hay for p in phrases) and topic not in out and not (elsewhere and topic in FORT_WORTH_ONLY) and venue_fits(topic, whole, title):
            out.append(topic)
            if len(out) >= 2:
                break
    for t in CATEGORY_DEFAULTS.get(category, []) + SCOPE_DEFAULTS.get(scope, SCOPE_DEFAULTS["local"]):
        if t not in out and not (elsewhere and t in FORT_WORTH_ONLY) and venue_fits(t, whole, title):
            out.append(t)
    if category == "sports":
        for i, t in enumerate(list(out)):
            variant = SPORTS_VARIANTS.get(t)
            if variant and variant not in out:
                out.insert(i, variant)
    return out


def pick(root: Path, topics: list[str], *, used: set[str] | None = None, recently_used=None, rng: random.Random | None = None) -> LibraryPhoto | None:
    """The first topic with a photo not used in this run or recently; a random one among its files for variety."""
    lib = load_library(root)
    if not lib:
        return None
    rng = rng or random.Random()
    used = used or set()
    for topic in topics:
        have = [e for e in lib if e.get("topic") == topic and e.get("id") not in used and (root / e["file"]).exists()]
        fresh = [e for e in have if not (recently_used and recently_used(e.get("id")))]
        pool = fresh or have      # a correct photo seen a few days ago beats a wrong one
        if pool:
            e = rng.choice(pool)
            return LibraryPhoto(id=e["id"], path=root / e["file"], topic=topic, credit=clean_credit(e.get("credit", "Photo: Wikimedia Commons")),
                                license=e.get("license", "wikimedia-cc"), source_url=e.get("source_url"))
    return None


OTHER_PLACES = ("houston", "dallas", "austin", "san antonio", "el paso", "lubbock", "waco", "odessa", "midland", "galveston",
                "corpus christi", "amarillo", "plano", "frisco", "mckinney", "denton", "oklahoma", "new york", "chicago",
                "los angeles", "toronto", "london", "seattle", "atlanta", "phoenix", "denver", "miami", "boston", "kansas city")


def avoid_words_for(text: str) -> tuple[str, ...]:
    """Place names a search-engine photo must not carry for this story (every city the story itself does not mention)."""
    low = (text or "").lower()
    return tuple(p for p in OTHER_PLACES if p not in low)
