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
                "forecast", "rain", "wind advisory", "cold front", "cold fronts", "warning for", "temps", "temperatures", "wind chill",
                "wind chills", "frost", "first freeze", "chilly", "highs in", "lows in", "drizzle", "showers"],
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
                 "active shooter", "lockdown", "shelter in place",   # "breaking records" is not breaking news
                 "house fire", "apartment fire", "structure fire", "home fire", "grass fire", "brush fire", "wildfire", "blaze",
                 "firefighters", "gas leak", "hazmat"],              # Nov 22: a 2-story house fire was filed "other" and got a parked fire truck
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


_SHOPPING_RE = re.compile(r"\b(gift guide|gifts? of 20\d\d|best gifts|holiday gift|black friday deals|deals? (?:on|for)|where to buy|shopping guide|"
                          r"top \d+ (?:gifts|products)|stocking stuffers)\b", re.I)


_MOVE_RE = re.compile(r"\b(names? [A-Z][\w.'-]+ (?:[A-Z][\w.'-]+ )?(?:to|as)\b|joins? .{0,40}\bas (?:chief|vice president|director|officer|partner)|"
                      r"appoint(?:s|ed)\b|promot(?:es|ed) .{0,40}\bto\b|hires? .{0,40}\bas\b|tapped as|named (?:chief|vice president|director|officer|partner)\b|"
                      r"executive leadership team|board of directors)", re.I)
_PUBLIC_ROLES = ("police chief", "fire chief", "superintendent", "city manager", "head coach", "athletic director", "mayor", "sheriff",
                 "judge", "chancellor", "university president", "county administrator", "district attorney", "commissioner", "general manager",
                 "ceo of", "tcu", "texas rangers", "cowboys", "mavericks", "stars")


def personnel_move(title: str) -> bool:
    """'Unbound Now names Andrea Sparks to executive leadership team': a press release about a hire. The page posts the
    public roles people would notice (a police chief, a superintendent, a head coach), not corporate and nonprofit staffing."""
    low = (title or "").lower()
    if any(r in low for r in _PUBLIC_ROLES):
        return False
    return bool(_MOVE_RE.search(title or ""))


_SALES_RE = re.compile(r"\b(black friday|cyber monday|prime day)\b", re.I)
_DEALS_RE = re.compile(r"\bdeals\b.*\b(guide|best|shop|save|prices?|plans?)\b|\b(guide|best)\b.*\bdeals\b", re.I)   # "A Guide to the Best ... Deals"


def shopping_guide(title: str, url: str = "") -> bool:
    """'The Top Texas Gifts of 2026', 'A Guide to the Best Black Friday Streaming Deals': a shopping guide, not news."""
    t = title or ""
    return bool(_SHOPPING_RE.search(t) or _SALES_RE.search(t) or _DEALS_RE.search(t)) or "/gift-guide" in (url or "") or "/style/" in (url or "")


_BETTING_RE = re.compile(r"\b(best bets?|best picks|odds,? (?:and )?(?:picks?|predictions?|lines?|spreads?)|(?:picks?|predictions?),? (?:picks?,? )?(?:and )?odds|"
                         r"betting (?:odds|picks|apps?|promos?|lines?|tips|guide)|"
                         r"sportsbooks?|promo codes?|bonus codes?|bonus bets?|player props?|(?:same-game )?parlay picks|same-game parlays?|"
                         r"expert picks|computer picks|model picks|against the spread|upset alerts?|upset picks|locks? of the week|"
                         r"(?:week \d+ )?(?:nfl|nba|mlb|nhl|college football|college basketball|cfb|bowl)(?: week \d+)? picks)\b", re.I)


def betting_promo(title: str, summary: str = "") -> bool:
    """'Cowboys vs. Eagles odds, picks, best bets', 'Get almost $4,000 in bonuses from betting apps': a sportsbook pitch
    carries a team name, so the DFW tier would keep it; it is an ad, not news."""
    return bool(_BETTING_RE.search(title or "") or _BETTING_RE.search((summary or "")[:300]))


_GAME_NOTES_RE = re.compile(r"^(?:(?:post|pre)-?game|game|weekly|match|series|week \d+)\s+(?:notes|quotes|notebook|stats)\b|"
                           r"^(?:notes|quotes)\s*(?:&|and)\s*(?:notes|quotes)\b|^box score\b|\bpostgame (?:notes|quotes)\b|"
                           r"^(?:game|match) (?:info|central|day central)\b|\bdepth chart\b|\bweekly release\b|"
                           r"^stats?\s*:|\bgrades\s*:|\breport cards?\b|^by the numbers\b", re.I)   # Nov 22: CBS's grades column, KXAN's stats explainer


def game_notes(title: str) -> bool:
    """'Postgame Notes - vs. Utah', 'Notes & Quotes', 'Box Score', 'Weekly Release': a team's stat sheet for a game the page
    has already posted (Nov 22: TCU's postgame notes came an hour after the recap and opened "TEAM NOTES TCU has now scored
    in 432 consecutive games")."""
    return bool(_GAME_NOTES_RE.search((title or "").strip()))


_COLUMN_RE = re.compile(r"^(?:[A-Z][a-z]+ on [A-Z][a-z]+|Opinion|Column|Commentary|Editorial|Letters?(?: to the [Ee]ditor)?|Analysis|Perspective|"
                        r"Guest column|Op-Ed|Essay|Review|Where I Live|My Fort Worth|Diary|Notebook|Letter from [A-Z][a-z]+|First Person|Voices)\s*[:|—–-]\s")


_EXPERT_RE = re.compile(r"\b(?:experts?|ethicists?|analysts?|professors?|economists?|attorneys?|lawyers?|historians?|psychologists?|"
                        r"doctors?|scientists?|strategists?|insiders?)\s+(?:weighs?|weighed)\s+in\b", re.I)


_ARCHIVE_RE = re.compile(r"^(?:watch|replay|rewind)\b[^.]{0,160}?\b(?:as it happened|archived? (?:footage|coverage|video|broadcast)|"
                         r"original (?:broadcast|coverage)|full (?:broadcast|newscast))\b|^(?:from the archives?|flashback|throwback)\b", re.I)


_RANKINGS_RE = re.compile(r"\b(?:top 25|top-25|power rankings?|coaches poll|ap poll|cfp rankings?|playoff rankings?|"
                          r"college (?:football|basketball) rankings?|bracketology)\b", re.I)
_LOCAL_TEAMS_RE = re.compile(r"\b(?:tcu|horned frogs|frogs|cowboys|mavericks|mavs|rangers|stars|fc dallas|wings|smu|mean green|unt|"
                             r"ut arlington|uta|mavericks)\b", re.I)


def rankings_list(title: str) -> bool:
    """'Coaches Poll top 25: Texas, Tennessee climb; UCLA, Indiana tumble': a national ranking is a list, and two sentences
    from the middle of it ('Previously slotted at No. 13, Iowa remained there...') are not a post (Nov 22, render 123).
    A ranking that names a local team is that team's news and stays."""
    t = title or ""
    return bool(_RANKINGS_RE.search(t)) and not _LOCAL_TEAMS_RE.search(t)


_PRESS_RELEASE_RE = re.compile(r"\b(?:is|are|was|were) (?:pleased|proud|thrilled|excited|delighted|honored|happy) to "
                               r"(?:announce|share|welcome|introduce|unveil)\b", re.I)


def press_release(title: str, summary: str = "") -> bool:
    """'The Tarrant County Young Lawyers Association (TCYLA) is pleased to announce that it has been awarded a grant ...':
    an organization's own announcement, reprinted by a business paper, speaks in its voice ('our community') and reads
    like an ad on the page (Nov 22, Fort Worth Business Press)."""
    return bool(_PRESS_RELEASE_RE.search(f"{title or ''} {(summary or '')[:600]}"))


_IN_GAME_RE = re.compile(r"\b(?:at halftime|at the half|at the break|halftime (?:lead|score|deficit|update)|lead[s]? .{0,40} at halftime|"
                         r"after (?:the )?(?:first|second|third|1st|2nd|3rd) (?:quarter|period|half|inning)|through \d+ innings|"
                         r"live updates?|live score|live blog|live coverage|in progress)\b", re.I)


def in_game_update(title: str) -> bool:
    """'Dominant Cowboys offense shines as they lead Titans 27-9 at halftime': a score while the game is still on is stale
    the moment it ends, and the final is the post (Nov 22: a daily cap deferred it to the next morning). A halftime show
    is an event, not a score."""
    t = title or ""
    if re.search(r"\bhalftime (?:show|performance|performer|act)\b", t, re.I):
        return False
    return bool(_IN_GAME_RE.search(t))


def archive_replay(title: str) -> bool:
    """'Watch the breaking news, coverage of President JFK's assassination in Dallas as it happened in 1963': a station's
    archive broadcast to watch on its site is history, not today's news, and has nothing to post but a link (Nov 22, KVUE)."""
    return bool(_ARCHIVE_RE.search((title or "").strip()))


def expert_commentary(title: str) -> bool:
    """'Medical ethicist weighs in on North Texas transplant case': an outside expert's opinion of a story, not the story
    (Nov 22: two outlets' versions reached review an hour apart)."""
    return bool(_EXPERT_RE.search(title or ""))


def column_label(title: str) -> bool:
    """"Bob on Business: Biz in the front, party in the back ...", "Opinion: ...": a column speaks in its writer's voice, which is
    not a caption we can post as news."""
    return bool(_COLUMN_RE.match((title or "").strip()))


OTHER_METRO_STATIONS = ("kvue", "kxan", "keye", "khou", "ktrk", "kprc", "kens", "ksat", "woai", "kiii", "kris", "kcen", "kwtx", "kxxv",
                        "kbtx", "kfdx", "kltv", "ktxs", "kgns", "kfox", "ktsm", "kvia", "kcbd", "klbk", "kamr", "kfda", "kavu", "kwes")


def other_metro_forecast(source: str, title: str, url: str) -> bool:
    """A station's rolling forecast page ("Forecast: What to expect across Texas as Thanksgiving travel gets underway" on
    kvue.com/.../austin-weather-central-texas-forecast) is that metro's weather however the headline is worded; ours comes
    from the NWS Fort Worth office and the DFW stations."""
    src = (source or "").lower()
    if not any(s in src for s in OTHER_METRO_STATIONS):
        return False
    t = (title or "").lower().strip()
    u = (url or "").lower()
    return t.startswith("forecast") or "/forecast" in u or "-forecast" in u or "/weather/" in u


def other_metro_local(title: str) -> bool:
    """'Austin Mayor Pro Tem announces resignation, run for Texas Senate': another city's government is that city's news."""
    low = (title or "").lower()
    if any(w in low for w in ("fort worth", "tarrant", "dfw", "north texas", "arlington", "keller", "southlake", "mansfield")):
        return False
    return bool(_CIVIC_RE.search(low)) and any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS)


_DIGEST_RE = re.compile(r"(?:\band more top stories\b|\btop stories\b|\bhottest headlines\b|\bnews roundup\b|\bweekly roundup\b|\bmorning briefing\b|"
                        r"\bdaily digest\b|\bthings to know\b|\bwhat you need to know this week\b|\bheadlines of the week\b|\bin case you missed it\b)", re.I)


def digest_title(title: str) -> bool:
    """'Hot dog chain Portillo\'s closes 2 DFW restaurants and more top stories': an outlet\'s weekly digest is not one story to caption."""
    return bool(_DIGEST_RE.search(title or ""))


_BLOTTER_RE = re.compile(r"\b(?:stable condition|no injuries|minor injuries|non-life-threatening|non life-threatening|expected to survive|no arrests?|"
                         r"one person (?:shot|injured|hurt)|1 (?:shot|injured|hurt)|burglar|car break-ins?|shoplift)\b", re.I)


def another_citys_blotter(title: str) -> bool:
    """'Juvenile shot in vehicle in stable condition, Dallas police say no arrests made yet': a single shooting with no death
    and no arrest in another DFW city is that city's police blotter, not Fort Worth news."""
    low = (title or "").lower()
    if any(w in low for w in ("fort worth", "tarrant", "arlington", "keller", "southlake", "mansfield", "haltom", "hurst", "euless", "bedford",
                              "grapevine", "north richland", "benbrook", "burleson", "crowley", "white settlement", "saginaw", "watauga", "azle", "weatherford")):
        return False
    return bool(_BLOTTER_RE.search(low)) and not any(w in low for w in ("dead", "dies", "died", "killed", "fatal", "murder", "homicide", "manhunt", "amber alert"))


OTHER_METRO_AGENCIES = ("hpd", "apd", "sapd", "harris county", "travis county", "bexar county", "el paso county", "houston isd", "austin isd")


def other_metro_title(title: str) -> bool:
    """'HPD: Teens find man\'s body in elevator shaft of abandoned downtown Houston building': a headline set in another metro,
    with none of our places in it, is that metro's local story whatever its beat."""
    low = (title or "").lower()
    if any(w in low for w in ("fort worth", "tarrant", "dfw", "north texas", "arlington", "keller", "southlake", "mansfield", "texas")):
        return False
    return any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS + OTHER_METRO_AGENCIES)


def other_metro_roundup(title: str) -> bool:
    """'Austin weekend: Theater performances, Bastrop B-day', 'Things to do in Houston this weekend': another city's events
    calendar, however good the weekend is there."""
    low = (title or "").lower()
    return bool(_ROUNDUP_RE.search(low)) and any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS) and "fort worth" not in low and "tarrant" not in low


STATEWIDE_WORDS = ("amber alert", "manhunt", "statewide", "across texas", "texas dps", "border patrol", "cartel", "human smuggling",
                   "ercot", "texas rangers investigat")      # a highway's name alone is not statewide news: a crash on San Antonio's I-35 is San Antonio's


_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "after", "as", "by", "is", "are", "was", "be",
         "from", "its", "it", "this", "that", "new", "fort", "worth", "texas", "tx", "says", "say", "said", "will", "over", "into", "up"}


def title_key(title: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9']+", (title or "").lower())
    return frozenset(w for w in words if len(w) > 2 and w not in _STOP)


TEAM_ALIASES = {"longhorns": "texas", "horns": "texas", "razorbacks": "arkansas", "hogs": "arkansas", "horned frogs": "tcu", "frogs": "tcu",
                "utes": "utah", "mavs": "mavericks", "aggies": "texas a&m", "red raiders": "texas tech", "mustangs": "smu",
                "mean green": "unt", "north texas": "unt", "sooners": "oklahoma", "bears": "baylor", "cougars": "houston",
                "fighting irish": "notre dame", "wildcats": "kansas state", "cyclones": "iowa state", "jayhawks": "kansas"}
_TEAM_STOP = {"no", "the", "a", "on", "in", "at", "senior", "day", "night", "week", "game", "series", "season", "home", "finale",
              "big", "sec", "nfl", "nba", "mlb", "nhl", "mls", "college", "football", "playoff", "playoffs", "title", "after", "as",
              # places and people are not teams (Nov 22: "Fort" + "Worth" made a van crash and a house fire "the same game"
              # as a shooting, and both were dropped)
              "fort", "worth", "tarrant", "county", "city", "police", "north", "south", "east", "west", "downtown", "man", "woman",
              "minors", "teen", "officials", "firefighters", "residents", "family"}
_SCORE_RE = re.compile(r"\b\d{1,3}-\d{1,3}\b")
_RESULT_RE = re.compile(r"\b(?:falls? to|fell to|tops?|topped|beats?|edges?|edged|routs?|routed|blows? out|blew out|wins? over|"
                        r"loss to|loses to|lost to|comes? up short|came up short|seals?|sealed|holds? on|held on|knocks? off|"
                        r"outduels?|takes? down|dominates?|dominated|crush(?:es|ed)?|cruises? past|rolls? past|rall(?:y|ies|ied) past|"
                        r"stuns?|stunned|upsets?|shuts? out|blanks?|outlasts?)\b", re.I)


def _sports_result(title: str) -> bool:
    """A game result carries a score, a team nickname or a result verb; a crash, a fire or a shooting carries none."""
    from .images.subject import TEAM_WORDS
    low = f" {(title or '').lower()} "
    return bool(_SCORE_RE.search(title or "") or _RESULT_RE.search(title or "")) or \
        any(f" {w} " in low or f" {w}'" in low or f" {w}," in low for w in TEAM_WORDS) or \
        any(re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w])", low) for a in TEAM_ALIASES if a not in _PLAIN_ALIASES)


_PLAIN_ALIASES = {"north texas", "bears", "cougars", "wildcats", "horns", "hogs", "mustangs"}   # place names and plain words first


def _game_keys(title: str) -> set[str]:
    t = " " + (title or "").lower().replace("’", "'") + " "
    keys: set[str] = set()
    for alias in sorted(TEAM_ALIASES, key=len, reverse=True):
        if re.search(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", t):
            keys.add(TEAM_ALIASES[alias])
            t = re.sub(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", " ", t)
    for word in re.findall(r"\b[A-Z][\w&]+(?:\s+[A-Z][\w&]+)?", title or ""):
        for w in word.lower().split():
            if w not in _TEAM_STOP and len(w) > 2:
                keys.add(TEAM_ALIASES.get(w, w))
    return keys


SPORTS_EVENT_TERMS = {"super bowl", "world series", "nba finals", "stanley cup final", "world cup final", "college football playoff",
                      "march madness", "final four", "halftime show", "heisman trophy", "nfl draft", "nba draft"}
_HYPOTHETICAL_RE = re.compile(r"\?|\b(contenders?|hopes?|hopeful|chances|odds|could|would|might|favou?rites?|dark horse|path to|"
                              r"projections?|predictions?|picks?|bubble|scenarios?|race)\b", re.I)


def same_game(a: str, b: str) -> bool:
    """'Arch Manning steps up as Longhorns blow out Arkansas' and 'No. 5 Texas avoids letdown, routs Arkansas 45-3' are one
    game (Nov 22: the second was drafted the morning after the first went out): two results that name the same two teams."""
    from .images.subject import happened
    def _result(t: str) -> bool:
        return happened(t) or bool(_SCORE_RE.search(t or "") or _RESULT_RE.search(t or ""))
    if not (_result(a) and _result(b)):
        return False                                      # a preview and a result are two stories
    if not (_sports_result(a) and _sports_result(b)):
        return False                                      # only games are games
    shared = _game_keys(a) & _game_keys(b)
    return len(shared) >= 2


def same_story(a: str, b: str, threshold: float = 0.6) -> bool:
    """Two headlines about the same event (an outlet's and a station's): the shorter one's content words are mostly
    contained in the other's, and at least four of them match."""
    a, b = _digits_to_words(a), _digits_to_words(b)          # "3 years" and "three years" are the same words
    ka, kb = {_stem(w) for w in title_key(a)}, {_stem(w) for w in title_key(b)}
    if len(ka) < 3 or len(kb) < 3:
        return False
    shared = len(ka & kb)
    return shared >= 4 and shared / min(len(ka), len(kb)) >= threshold


_PERSONNEL_RE = re.compile(r"\b(?:fires|fired|firing|relieved of|dismiss(?:es|ed|al)?|part(?:s|ed)? ways|parting ways|"
                           r"change in leadership|leadership change|coaching change|out as|ousts?|ousted|let go|"
                           r"resign(?:s|ed|ation)?|steps? down|stepping down)\b", re.I)
_GUNFIRE_RE = re.compile(r"\b(?:shots? (?:were |was |being )?fired|fired (?:shots?|rounds?|at|into|upon|on|a gun|a weapon)|"
                         r"gunfire|opened fire|fire[sd]? (?:upon|on) )", re.I)
_ROLE_RE = re.compile(r"\b(?:coach|coordinator|manager|president|chief|director|ceo|superintendent|chancellor|principal|commissioner|"
                      r"chair(?:man|woman)?|pastor|executive|officer|athletic director|ad|gm|head coach|staff|employee)\b", re.I)
_HIRE_RE = re.compile(r"\b(?:names?|named|hires?|hired|tabs?|promotes?|promoted|picks?|selects?|introduces?|interim|replacement|successor)\b", re.I)
_FULL_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})\b")


def same_personnel_news(title: str, summary: str, posted_title: str) -> bool:
    """'TCU Football Announces Change in Leadership' after 'TCU fires Sonny Dykes ...' is the same firing in the school's
    own words (Nov 22): when a post in the last two days reported a person's firing or resignation, a story whose title or
    lead reports a departure and names that person is the same news. A hire ('TCU names X interim coach') is new news."""
    posted = _GUNFIRE_RE.sub(" ", posted_title or "")
    if not _PERSONNEL_RE.search(posted):
        return False
    if _HIRE_RE.search(title or "") and not _HIRE_RE.search(posted_title or ""):
        return False
    text = _GUNFIRE_RE.sub(" ", f"{title or ''} {(summary or '')[:500]}")
    if not _PERSONNEL_RE.search(text) or not (_ROLE_RE.search(text) or _ROLE_RE.search(posted)):
        return False                     # Nov 22: "catches fire in Fort Worth" was read as the firing of a "Fort Worth"
    from .images.subject import _is_place, looks_like_person
    names = [n for n in _FULL_NAME_RE.findall(posted) if looks_like_person(n) and not _is_place(n)]
    return any(n in text for n in names)


_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def _digits_to_words(text: str) -> str:
    return re.sub(r"\b(10|[1-9])\b", lambda m: _WORDS[m.group(1)], text or "")


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


_TITLE_CRIME_RE = re.compile(r"\b(?:convicted|sentenced|arrested|(?<!cardiac )arrests?|charged with|accused of|indicted|pleads? guilty|found guilty|"
                             r"wanted|murder|homicide|shooting|stabbing|robbery|burglar\w*|ponzi|fraud|assault|kidnapp\w*|manhunt|suspect|"
                             r"solicit\w* (?:a |an )?(?:minor|child|teen|\d{1,2}-year-old|sex|prostitution)|solicitation of a minor)\b", re.I)
# Nov 22: "North Texas traffic stop leads to arrest of armed man accused of soliciting 15-year-old on Snapchat" was filed as traffic


_NOT_CRIME_RE = re.compile(r"\bcardiac arrests?\b|\bheart attacks?\b"
                           r"|\b(?:texas |state )?bar (?:foundation|association|exam|of texas)\b|\bstate bar\b", re.I)
# ("Texas Bar Foundation" is lawyers, not a bar: Nov 22 a young lawyers' grant was filed as food)


def infer_category(story: Story) -> str:
    if _TITLE_CRIME_RE.search(story.title or "") and story.category_hint != "sports":
        return "crime"                      # "Arlington pastor convicted for Ponzi scheme" is crime, whatever a channel's boilerplate says
    text = _NOT_CRIME_RE.sub(" ", story.text())          # "Runner in cardiac arrest saved by nurses" is not a crime story
    title = _NOT_CRIME_RE.sub(" ", story.title.lower())
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


DEFERRED_MAX_AGE_HOURS = 36.0    # a story a daily cap held back may still run the next day while it is this fresh


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
        if shopping_guide(story.title, story.url):
            dropped.append((story, "shopping guide, not news"))
            continue
        if betting_promo(story.title, story.summary or ""):
            dropped.append((story, "sports betting picks or promo, not news"))
            continue
        if game_notes(story.title):
            dropped.append((story, "a team's game notes or quotes sheet, not a story"))
            continue
        if story.source_kind == "rss" and not story.official and press_release(story.title, story.summary or ""):
            dropped.append((story, "an organization's press release, not news"))
            continue
        if story.source_kind == "rss" and rankings_list(story.title):
            dropped.append((story, "a national rankings list with no local team in it"))
            continue
        if story.source_kind in ("rss", "video") and in_game_update(story.title):
            dropped.append((story, "an in-game score update: the final is the post"))
            continue
        if story.source_kind == "rss" and archive_replay(story.title):
            dropped.append((story, "an archive broadcast to watch on the station's site, not news"))
            continue
        if story.source_kind == "rss" and personnel_move(story.title):
            dropped.append((story, "a hire announcement, not news"))
            continue
        twin = state.recent_title_like(story.title, now, hours=48, match=lambda x, y: same_story(x, y) or same_game(x, y)
                                       or same_personnel_news(x, story.summary or "", y))
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
        if not is_fresh(story, now, max_age) and not (state.deferred(story.id) and is_fresh(story, now, DEFERRED_MAX_AGE_HOURS)):
            dropped.append((story, f"older than {max_age:.0f}h"))      # a cap-held story gets a second day (State.defer)
            continue
        term = blocked(story, blocklist)
        if term:
            dropped.append((story, f"blocklist: {term}"))
            continue
        if story.source_kind in ("rss", "video") and not story.official and len(story.title.split()) < 4:
            dropped.append((story, "title too short to be a story"))         # "Notes and News", column stubs
            continue
        if stale_dated_title(story.title, now.astimezone(settings.tz)):
            dropped.append((story, "dated for a day that has passed"))       # Tuesday's forecast must not sit in the pool all week
            continue
        if story.source_kind == "event" and not story.image_url:
            dropped.append((story, "event listing without its own picture"))  # an original post needs the listing's own picture
            continue
        if story.source_kind == "rss" and column_label(story.title):
            dropped.append((story, "a column"))
            continue
        if expert_commentary(story.title):
            dropped.append((story, "an expert's commentary, not news"))
            continue
        if story.source_kind == "rss" and digest_title(story.title):
            dropped.append((story, "a digest, not a story"))
            continue
        if story.source_kind == "rss" and other_metro_forecast(story.source, story.title, story.url):
            dropped.append((story, "another metro's forecast"))
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
                if hit and hit in SPORTS_EVENT_TERMS and _HYPOTHETICAL_RE.search(title):
                    hit = None                    # "building a World Series contender?": a feature that names the event, not the event
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
            if tier[0] == "texas" and cat not in ("sports", "politics", "business") and other_metro_title(story.title) \
                    and not any(w in story.text() for w in STATEWIDE_WORDS):
                dropped.append((story, "another metro's local story"))         # a body found in a downtown Houston elevator shaft is Houston's news
                continue
            if tier[0] == "texas" and other_region(story.title) and not any(w in story.text() for w in STATEWIDE_WORDS):
                dropped.append((story, "another region's story"))              # fall foliage in South Central Texas is KENS 5's weather blog
                continue
            if tier[0] == "texas" and other_metro_local(story.title) and not any(w in story.text() for w in STATEWIDE_WORDS):
                dropped.append((story, "another city's government"))             # Austin's mayor pro tem is Austin's news
                continue
            if tier[0] == "dfw" and cat == "crime" and another_citys_blotter(story.title):
                dropped.append((story, "another city's police blotter"))     # a Dallas shooting with no death and no arrest is Dallas's blotter
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
