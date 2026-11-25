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
    (("university of north texas", "unt ", "unt's", "mean green"), "unt"),      # "North Texas" alone is the region, never the campus
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
    # a person named in the headline is searched for, never stood in for by the Capitol: Nov 24, "Paxton drops series of
    # high-profile Texas lawsuits after election loss" drew the Capitol building
    (("legislature", "lawmakers", "texas house", "texas senate", "state rep", "state sen", "bill filed", "signed into law", "capitol"), "capitol"),
    # the national beat
    (("anthropic", "claude ai", "dario amodei"), "anthropic"),
    (("ipo", "initial public offering", "nasdaq", "nyse", "wall street", "stock market", "dow jones", "s&p 500", "shares soar", "shares fall", "market cap"), "stock-market"),
    (("gta vi", "gta 6", "grand theft auto", "playstation", "xbox", "nintendo", "switch 2", "video game", "rockstar games", "steam"), "gaming"),
    # Nov 23: "$850,000 Texas Two Step jackpot set to expire" searched the game's name and found a firefly (the Texas Two-step Flasher)
    (("powerball", "mega millions", "jackpot", "lottery", "texas two step", "lotto texas", "cash five", "pick 3", "daily 4",
      "all or nothing", "scratch-off", "scratch ticket", "texas lottery", "unclaimed prize"), "lottery"),
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
               "texas-motor-speedway": ("texas motor speedway",), "tcu-football": ("amon g. carter", "amon carter stadium"),
               # the "texas-am" photos are all Kyle Field: Nov 24, an A&M season analysis went out with the stadium at dusk
               "texas-am": ("kyle field",)}
_VENUE_RE = re.compile(r"\b((?:[A-Z][\w&.'’-]*\s+){1,3}(?:Stadium|Arena|Field|Ballpark|Coliseum|Speedway))\b")
_AWAY_RE = re.compile(r"\b(?:visit|visits|visiting|travel to|travels to|traveling to|head to|heads to|road game|road trip|on the road|away game)\b", re.I)
# what says a game is at the team's own venue: a story that only names the opponent says nothing about where it is played (Nov 24,
# NBC 5's "Mavs enter NBA Cup matchup on NBC ..." went out with the American Airlines Center; the game was in Denver)
_HOME_RE = re.compile(r"\b(?:host|hosts|hosted|hosting|home game|home games|home opener|home finale|at home|return home|returns home|"
                      r"back home|home crowd|home fans|home stand|homestand|senior night|senior day)\b", re.I)
# a wire recap's dateline is where the game was: "DENVER (AP) — ..."
_DATELINE_CITY_RE = re.compile(r"\b([A-Z][A-Z .'’-]{2,30}?)\s*\((?:AP|AFP|Reuters)\)\s*[—–-]")
HOME_CITIES = {"att-stadium": ("arlington",), "globe-life-field": ("arlington",), "aac": ("dallas",), "tcu-football": ("fort worth",),
               "texas-am": ("college station",), "toyota-stadium": ("frisco",), "nrg-stadium": ("houston",),
               "dickies-arena": ("fort worth",), "texas-motor-speedway": ("fort worth",)}


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
    the road, and only when the text says the game is at home (it names the venue, the team hosts, "X visits/at <team>",
    or a wire dateline from the home city). The venue named in the headline is always its own picture."""
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
    away = bool(_AWAY_RE.search(text or ""))
    home = bool(_HOME_RE.search(text or ""))
    teams = HOME_TEAMS.get(topic, ())
    for m in _AWAY_RE.finditer(text or ""):
        if any(w in low[m.end():m.end() + 40] for w in teams):
            away, home = False, True                             # "Utah visits TCU": the visitor is the other team
    if any(re.search(r"\bat (?:the )?" + re.escape(w) + r"\b", low) for w in teams):
        home = True                                              # "Nuggets at Mavericks"
    dateline = _DATELINE_CITY_RE.search(text or "")
    if dateline:
        if dateline.group(1).strip().lower() in HOME_CITIES.get(topic, ()):
            home = True
        else:
            away = True                                          # "DENVER (AP) —": the game was there
    return not others and not away and home


# the team that plays at each venue topic, so "Utah visits TCU" reads as a home game
HOME_TEAMS = {"tcu-football": ("tcu", "horned frogs"), "texas-am": ("texas a&m", "aggies"), "att-stadium": ("cowboys",),
              "globe-life-field": ("rangers",), "aac": ("mavericks", "mavs", "stars"), "toyota-stadium": ("fc dallas",),
              "nrg-stadium": ("texans",)}


TITLE_ONLY = {"heb", "stock-market", "gaming", "lottery", "parade", "shopping", "thanksgiving", "christmas", "fireworks", "smartphone", "nfl", "space", "eclipse",
              "concert", "music", "movies", "streaming", "att-stadium", "globe-life", "aac", "dickies-arena", "texas-motor-speedway", "amon-carter", "tcu-football", "dallas-skyline"}   # a venue mentioned in passing in the body is never the picture   # a passing mention in the body must not turn a local story into a turkey photo


# a phrase that names something else carrying the same word: Baylor University Medical Center and Baylor Scott & White are
# Dallas hospitals, not the Waco campus (Nov 22: a transplant lawsuit against the hospital drew McLane Stadium)
TOPIC_EXCLUDE = {"baylor": ("medical center", "scott & white", "scott and white", "baylor health", "baylor hospital", "baylor all saints",
                            "baylor medical", "baylor college of medicine", "baylor scott"),
                 "texas-am": ("texas a&m-commerce", "texas a&m university-commerce", "a&m-commerce", "a&m commerce"),
                 "ut-austin": ("ut southwestern", "ut health", "ut arlington", "ut dallas", "ut tyler", "ut permian")}


_HOLIDAY_AS_TIME_RE = re.compile(r"\b(?:ahead of|before|after|over|during|for) (?:the )?(?:thanksgiving|christmas)\b|"
                                 r"\b(?:thanksgiving|christmas) (?:week|weekend|travel|holiday travel|rush|break)\b")
_HOLIDAY_SUBJECT_RE = re.compile(r"\b(?:turkey|turkeys|dinner|feast|meal|meals|pie|pies|tree|trees|lights|parade|gifts?|santa|food drive|giveaway)\b")
# topics that are the subject itself: no skyline or Capitol stands in when the library has no photo of the subject
SUBJECT_ONLY = {"gas", "lottery", "stock-market", "power", "smartphone", "streaming", "gaming", "space", "eclipse"}


def topic_excluded(topic: str, text: str) -> bool:
    low = (text or "").lower()
    if topic in ("thanksgiving", "christmas") and _HOLIDAY_AS_TIME_RE.search(low) and not _HOLIDAY_SUBJECT_RE.search(low):
        return True                  # "Gas prices drop ahead of Thanksgiving": the holiday is when, not what (Nov 22)
    return any(p in low for p in TOPIC_EXCLUDE.get(topic, ()))


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
        if (any(p in hay for p in phrases) and topic not in out and not (elsewhere and topic in FORT_WORTH_ONLY) and venue_fits(topic, whole, title)
                and not topic_excluded(topic, whole)):
            out.append(topic)
            if len(out) >= 2:
                break
    if out and out[0] in SUBJECT_ONLY:
        return out[:1]               # a gas-price story gets a gas pump or nothing, never the skyline or the Capitol
    for t in CATEGORY_DEFAULTS.get(category, []) + SCOPE_DEFAULTS.get(scope, SCOPE_DEFAULTS["local"]):
        if t not in out and not (elsewhere and t in FORT_WORTH_ONLY) and venue_fits(t, whole, title):
            out.append(t)
    if category == "sports":
        # Nov 24: WFAA's "Texas high school football: Playoff matchups, schedule" drew a Dell City ISD school bus
        out = [t for t in out if t not in ("school-bus", "schools", "courthouse", "courtroom", "jail", "police")]   # Nov 24: a
        # Thanksgiving "record" drew the Tarrant County Courthouse for CBS Sports' Cowboys-and-Lions explainer
        for i, t in enumerate(list(out)):
            variant = SPORTS_VARIANTS.get(t)
            if variant and variant not in out:
                out.insert(i, variant)
    return out


# a team's stadium stands for its games, never for a blood drive, a toy drive or a job fair held there: Nov 23, "Dallas Cowboys
# partner with Carter BloodCare to host blood drive ahead of Thanksgiving" went out with an empty June 2020 AT&T Stadium
STADIUM_TOPICS = {"att-stadium", "globe-life-field", "aac", "toyota-stadium", "daikin-park", "nrg-stadium", "frost-bank-center",
                  "toyota-center", "texas-motor-speedway", "tcu-football"}
_NOT_A_GAME_RE = re.compile(r"\b(?:blood drive|toy drive|food drive|coat drive|clothing drive|donors?|donat\w*|volunteers?|charity|"
                            r"fundraiser|job fair|hiring event|vaccin\w*|clinic|graduation|commencement|lighting ceremony|"
                            r"partnership|giveaway|turkey)\b", re.I)


def drop_stadiums_off_the_field(topics: list[str], text: str) -> list[str]:
    if not _NOT_A_GAME_RE.search(text or ""):
        return topics
    return [t for t in topics if t not in STADIUM_TOPICS]


# a show coming to a local stage takes the stage, not a photo of another company's production: Nov 24, "Mamma Mia! coming
# back to town" (Bass Performance Hall, Dec. 1-6) drew a 2017 community-theater staging with its photographer's watermark
STAGE_TOPICS = {"bass-hall", "will-rogers", "convention-center", "kimbell", "modern", "botanic-garden", "zoo", "stockyards"}


# a library photo marked with the season it shows stays out of the opposite season: Nov 24, the forecast for a 49-degree day
# with a freeze that night drew the courthouse under May's green trees; Nov 23, a June 2020 AT&T Stadium with summer lawns
_OFF_SEASON = {"summer": (11, 12, 1, 2), "winter": (5, 6, 7, 8, 9)}


def in_season(entry: dict, month: int) -> bool:
    return month not in _OFF_SEASON.get(str(entry.get("season") or ""), ())


def pick(root: Path, topics: list[str], *, used: set[str] | None = None, recently_used=None, rng: random.Random | None = None,
         text: str | None = None, month: int | None = None) -> LibraryPhoto | None:
    """The first topic with a photo not used in this run or recently; a random one among its files for variety.
    A photo that shows one agency or one owner (a "DFW Airport Police" SUV) carries `only_when` phrases and is used only
    when the story names one of them: a reader takes the badge on the door for the subject of the post."""
    lib = load_library(root)
    if not lib:
        return None
    rng = rng or random.Random()
    used = used or set()
    if month is None:
        from datetime import datetime
        month = datetime.now().month
    for topic in topics:
        low = (text or "").lower()
        have = [e for e in lib if e.get("topic") == topic and e.get("id") not in used and (root / e["file"]).exists()
                and (not e.get("only_when") or any(p in low for p in e["only_when"])) and in_season(e, month)]
        fresh = [e for e in have if not (recently_used and recently_used(e.get("id")))]
        pool = fresh or have      # a correct photo seen a few days ago beats a wrong one
        if pool:
            e = rng.choice(pool)
            return LibraryPhoto(id=e["id"], path=root / e["file"], topic=topic, credit=clean_credit(e.get("credit", "Photo: Wikimedia Commons")),
                                license=e.get("license", "wikimedia-cc"), source_url=e.get("source_url"))
    return None


OTHER_PLACES = ("houston", "dallas", "austin", "san antonio", "el paso", "lubbock", "waco", "odessa", "midland", "galveston",
                "corpus christi", "amarillo", "plano", "frisco", "mckinney", "denton", "oklahoma", "new york", "chicago",
                "los angeles", "toronto", "london", "seattle", "atlanta", "phoenix", "denver", "miami", "boston", "kansas city",
                # Nov 24: "McAdams" found the McAfee Swimming Pool at McAdams Park in Wichita, Kansas: another state is not here
                "kansas", "wichita", "missouri", "louisiana", "arkansas", "colorado", "california", "florida", "tennessee", "georgia",
                "ohio", "illinois", "michigan", "arizona", "nevada", "new mexico", "alabama", "mississippi", "kentucky", "virginia",
                "carolina", "pennsylvania", "minnesota", "wisconsin", "iowa", "nebraska", "utah", "oregon", "washington state")


def avoid_words_for(text: str) -> tuple[str, ...]:
    """Place names a search-engine photo must not carry for this story (every city the story itself does not mention)."""
    low = (text or "").lower()
    return tuple(p for p in OTHER_PLACES if p not in low)
