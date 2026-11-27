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
                "wind chills", "frost", "first freeze", "chilly", "highs in", "lows in", "drizzle", "showers",
                # Nov 26: CBS News Texas's "North Texas faces freezing Thanksgiving morning before weekend warmup" was filed as
                # community (its "Thanksgiving" outscored a forecast that named no listed weather word) and drew a smoked turkey
                "freezing", "warmup", "warm-up", "warming trend", "cool-down", "gusty winds"],
    "traffic": ["crash", "crashes", "wreck", "wrecks", "i-35w", "35w", "i-30", "i-20", "loop 820", "highway", "interstate", "interstates",
                "lanes closed", "road closure",
                # Nov 27, render 295: "Northbound I-35 closed in Denton due to 'hazard' damaging tires, police say" was crime
                "i-35", "i-35e", "i-45", "i-820", "northbound", "southbound", "eastbound", "westbound", "tollway", "frontage road",
                "traffic", "pileup", "18-wheeler", "trinity metro", "texrail", "dfw airport delays"],
    "crime": ["police", "shooting", "shot", "arrested", "arrest", "stabbing", "robbery", "homicide", "murder", "suspect", "steal", "stole",
              "stolen", "theft", "thieves", "bandit", "burglar", "carjack", "wanted", "sentenced", "indicted",
              "fwpd", "deputies", "sheriff", "charged with", "manhunt", "burglary", "carjack",
              # Nov 27, render 311: CBS Texas's "Pregnant prisoner escapes in corrections vehicle ..." was filed as "other"
              "inmate", "inmates", "prisoner", "escaped prisoner", "escapee", "jailbreak", "on the run"],
    "sports": ["tcu", "horned frogs", "frogs", "cowboys", "rangers", "mavericks", "stars", "fc dallas", "texas motor speedway",
               "longhorns", "aggies", "razorbacks", "sooners", "senior day", "sec championship", "big 12 championship", "touchdown",
               "quarterback", "halftime", "kickoff", "playoff", "head coach",
               "nascar", "indycar", "rodeo", "stock show", "panther city", "pga", "colonial", "golf", "football", "basketball", "baseball",
               # Nov 23: "Miller won't return as Astros' pitching coach in '27" read as "other", so the other-metro team rule
               # (sports only) let it through with the Astros' ballpark as its picture
               "astros", "mlb", "nfl", "nba", "nhl", "pitching coach", "pitcher", "bullpen", "inning", "home run",
               "offensive coordinator", "defensive coordinator"],
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
                  "church", "celebration", "enrollment", "isd", "superintendent", "teachers",
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


# Nov 26, render 277: Billboard's "Goo Goo Dolls' Halftime Show at the Chiefs vs. Bills Thanksgiving Game: Watch Online for Free"
# (a /product-recommendations/ page) is a streaming-trial pitch, not news: it reads like an ad
_AFFILIATE_RE = re.compile(r"\bwatch (?:[\w'’.-]+ ){0,4}(?:online |live )?(?:for )?free\b|\bstream (?:[\w'’.-]+ ){0,4}(?:online |live )?for free\b|"
                           r"\bwithout cable\b|\bfree (?:live ?)?stream(?:ing)?\b|\bfree trial\b", re.I)
_AFFILIATE_PATHS = ("/gift-guide", "/style/", "/product-recommendations/", "/shopping/", "/deals/", "/commerce/")


def shopping_guide(title: str, url: str = "") -> bool:
    """'The Top Texas Gifts of 2026', 'A Guide to the Best Black Friday Streaming Deals', '... Watch Online for Free':
    a shopping guide or an affiliate pitch, not news."""
    t = title or ""
    if _SHOPPING_RE.search(t) or _SALES_RE.search(t) or _DEALS_RE.search(t) or _AFFILIATE_RE.search(t):
        return True
    return any(seg in (url or "").lower() for seg in _AFFILIATE_PATHS)


_BETTING_RE = re.compile(r"\b(best bets?|best picks|odds,? (?:and )?(?:picks?|predictions?|lines?|spreads?)|(?:picks?|predictions?),? (?:picks?,? )?(?:and )?odds|"
                         r"betting (?:odds|picks|apps?|promos?|lines?|tips|guide)|"
                         r"sportsbooks?|promo codes?|bonus codes?|bonus bets?|player props?|(?:same-game )?parlay picks|same-game parlays?|"
                         r"expert picks|computer picks|model picks|against the spread|upset alerts?|upset picks|locks? of the week|"
                         r"(?:week \d+ )?(?:nfl|nba|mlb|nhl|college football|college basketball|cfb|bowl)(?: week \d+)? picks|"
                         # Nov 25, CBS Sports: "Cowboys vs. Eagles Thanksgiving prediction: ..." and "One bold prediction for each NFL
                         # Thanksgiving game ...": a pundit's guess with a menu of food puns is not news
                         r"bold predictions?|predictions? for (?:each|every|all)|(?:game|thanksgiving|week \d+|matchup|bowl|playoff) predictions?|"
                         # Nov 26, render 269: CBS Sports' "NFL DFS, Thanksgiving Day: Top daily Fantasy picks, lineups for ..." as a
                         # sports text card: daily-fantasy advice is a betting column
                         r"dfs|daily fantasy|fantasy (?:picks|lineups?|rankings|sleepers|start|advice)|start[,']?\s*(?:'em|em),? sit|"
                         r"waiver wire)\b",
                         re.I)


# Nov 23, Fort Worth Weekly: "Game Show Sets Have Found a Second Life on Interactive Live Streams" ("Some streams let adults
# wager on the action") is a paid gambling post on a local site: it names no place, so it is no one's local news
_GAMBLING_RE = re.compile(r"\b(wager(?:s|ed|ing)?|gambl(?:e|ing|ers?)|casinos?|slots?(?: machines?| games?)|sweepstakes|"
                          r"real[- ]money|live dealers?|roulette|blackjack|poker sites?|crash games?|plinko|igaming)\b", re.I)


def gambling_advertorial(title: str, summary: str = "") -> bool:
    """A gambling pitch that never names a Texas place. 'Texas lawmakers weigh casino gambling' names Texas and stays news."""
    text = f"{title or ''} {summary or ''}"
    return bool(_GAMBLING_RE.search(text)) and not any(w in _plain(text) for w in PLACE_WORDS + ("tarrant", "metroplex"))


# a magazine feature is not a national moment, even about a watchlist subject (Nov 23: Billboard's "'It's Not Just a Song on
# the Radio': How Music Became A Main Character In 'Grand Theft Auto VI'", a cover story four days after the launch)
# Nov 24, ESPN: "From a camcorder to a Super Bowl mantra, inside Mike Macdonald's love for game film": "inside" after a comma
_FEATURE_TITLE_RE = re.compile(r"(?:^|[:—–]\s*|,\s+)(?:how(?! to\b)|why|inside|behind the|the making of|the story of|meet the|"
                               r"in conversation)\b|\b(?:q&a|cover story|oral history|interview)\b|"
                               r"\bI (?:wish|think|played|love|loved|hate|tried|spent|can't|don't|need|want)\b|"
                               r"\b(?:goes|went|going) viral\b|"   # Nov 23: a streamer's viral GTA 6 clip is not a moment
                               # Nov 24: CBS Sports' "One year after 11-0 start, Texas A&M enters rivalry week as a cautionary tale"
                               r"\bcautionary tale\b|\bwhat went wrong\b|\bpost-?mortem\b|"
                               # Nov 24: Variety's "'To Me, My X-Men': James Marsden Says It Was 'Important' for Cyclops ...": a
                               # quote, a colon and someone saying something is an interview
                               r"^[‘'\"“][^’'\"”]{3,80}[’'\"”]\s*:\s.*\bsays\b|"
                               # Nov 23: IGN's "GTA 6 Players Are Upset Its New Train Can Actually Be Stopped": a fan reaction
                               r"\b(?:players|fans|gamers|viewers|users|subscribers|swifties)\s+(?:are|were|seem|get|got)?\s*"
                               r"(?:upset|angry|furious|livid|mad|divided|split|losing it|freaking out|obsessed|baffled|confused|"
                               r"think|thought|discover(?:ed)?|found|notice[ds]?|spot(?:ted)?|realize[ds]?|convinced|debating|"
                               r"can't stop|cannot stop|have (?:found|discovered|noticed|spotted))\b|"
                               # Nov 27, render 306: IGN's "Denis Villeneuve Was 'Deeply Disappointed' by Disney's Decision to
                               # Release Avengers: Doomsday on the Same Day as Dune: Part Three" (from a Time interview): someone's
                               # feelings about a decision are an interview's color, not the moment
                               r"\b(?:was|is|were|are|felt|feels|got|admits(?: being)?|says (?:he|she|they) (?:was|is|were))\s+"
                               r"[‘'\"“]?(?:deeply |very |really |so |extremely |a bit |a little |left )?(?:disappointed|upset|"
                               r"frustrated|angry|furious|hurt|heartbroken|devastated|annoyed|irritated|livid|baffled|gutted)"
                               r"[’'\"”]?\s+(?:by|at|with|over|about|that)\b", re.I)
_FEATURE_URL_RE = re.compile(r"/(?:features?|lists?|galler(?:y|ies)|longform|long-reads?|interviews?|cover-stor(?:y|ies)|in-depth)/|-cover-\d|"
                             # Nov 25, The Hollywood Reporter: /music/music-features/gta-vi-carly-rae-jepsen-...-interview-1236763127/
                             r"/[a-z]+-features?/|-interview-\d", re.I)


# an awards campaign is the trade press's beat, not a moment (Nov 23: Variety's "Marvel's 'Avengers: Doomsday' Won't Screen for
# BAFTA, Golden Globes and Other Early Awards Groups" took the national slot on "marvel" and "avengers")
_AWARDS_TRADE_RE = re.compile(r"\b(?:won't|will not|wont|to|doesn't|skips?|skipping|skipped)\s+screen\b|"
                              r"\bawards?[- ](?:groups?|bodies|voters?|voting|season|campaigns?|push|strategy|screenings?|"
                              r"contenders?|race|circuit|consideration|chances|hopefuls?|predictions?|calendar|qualifying)\b|"
                              r"\bfor your consideration\b|\bfyc\b|\boscars? (?:race|campaign|buzz|contenders?|hopefuls?|predictions?|"
                              r"chances|push|eligib\w*|shortlist\w*)\b", re.I)


def awards_trade(title: str) -> bool:
    return bool(_AWARDS_TRADE_RE.search(_plain(title)))


# the business of making entertainment is the trades' beat, not a national moment: Nov 24, Variety's "Netflix Closes $380
# Million Acquisition of Radford Studio Center" (a Studio City soundstage lot) went to a draft with a TV remote control
_INDUSTRY_TRADE_RE = re.compile(r"\b(?:closes?|completes?|finalizes?|seals?)\b.{0,40}\b(?:acquisition|purchase|sale|buyout)\b|"
                                r"\bstudio (?:center|lot|campus|complex)\b|\bsoundstages?\b|\b(?:first-look|overall|production|"
                                r"distribution|licensing|rights|output|carriage) (?:deal|pact|agreement)\b|\bbox office (?:preview|tracking)\b|"
                                # Nov 24, Deadline: "'Inter Alia' Starring Rosamund Pike Sells Out; ... – Broadway Box Office"
                                r"\bbroadway (?:box office|grosses)\b|"
                                # Nov 25, The Hollywood Reporter: "'Avengers: Doomsday' Eyes $270M Opening as 'Dune: Part Three' Also
                                # Heads for Big Start" (tracking services' projections, a month before release)
                                r"\beyes \$[\d.]+\s?[mb](?:illion)?\b.{0,25}\bopening\b|\btracking (?:for|services?|ahead)\b|"
                                r"\bopening(?:-| )weekend (?:projections?|tracking|forecasts?)\b|box-office-tracking",
                                re.I)


def industry_trade(title: str, url: str = "") -> bool:
    return bool(_INDUSTRY_TRADE_RE.search(title or "") or _INDUSTRY_TRADE_RE.search(url or ""))


# a statewide magazine's culture, food and travel sections are features, not news: Nov 24, Texas Monthly's "Shana Feste's Road
# to 'Heartland' Began and Ended in Texas" (texasmonthly.com/culture/) drafted as a Texas story
_MAGAZINE_SECTION_RE = re.compile(r"texasmonthly\.com/(?:culture|arts-entertainment|food|travel|being-texan|the-culture|"
                                  r"style|music|books|television|movies)/", re.I)


_TEXAS_STOP_RE = re.compile(r"\b(?:texas|arlington|dallas|fort worth|houston|austin|san antonio|el paso|frisco|irving|grand prairie|"
                            r"at&t stadium|dickies arena|american airlines center|globe life|toyota music factory)\b", re.I)


# a station's video page in its article feed is a clip the page cannot show, usually a segment of a story already covered:
# Nov 24, CBS Texas's "AT&T Stadium lights up kettle red" (cbsnews.com/texas/video/) came the morning after the lighting post
_VIDEO_PAGE_RE = re.compile(r"https?://(?:www\.)?(?:cbsnews\.com/[a-z-]+/video/|fox4news\.com/video/|nbcdfw\.com/(?:video|watch)/|"
                            r"wfaa\.com/video/|kxan\.com/video/|khou\.com/video/|kvue\.com/video/|kens5\.com/video/)", re.I)


def station_video_page(url: str) -> bool:
    return bool(_VIDEO_PAGE_RE.search(url or ""))


def magazine_section(url: str) -> bool:
    return bool(_MAGAZINE_SECTION_RE.search(url or ""))


_TEASER_RE = re.compile(r"\b(?:teasers?|trailers?|first look|sneak peek|sneak preview|promo|clip shows|footage shows)\b", re.I)


def national_feature(title: str, url: str = "") -> bool:
    return bool(_FEATURE_TITLE_RE.search(title or "") or _FEATURE_URL_RE.search(url or ""))


# teams that share our teams' nicknames: Nov 25, CBS Sports' "Oklahoma State rewards Eric Morris with contract extension after
# Cowboys' dramatic turnaround" counted as local news (and drew a Dallas Cowboys photo)
_OTHER_NICKNAME_TEAMS = {"cowboys": ("oklahoma state", "okla. state", "stillwater", "pokes", "wyoming cowboys", "mcneese"),
                         "rangers": ("new york rangers", "ny rangers", "madison square garden", "glasgow rangers", "rangers fc"),
                         "mavericks": ("omaha mavericks", "minnesota state", "colorado mesa")}
_OUR_TEAM_MARKERS = {"cowboys": ("dallas cowboys", "dallas", "at&t stadium", "arlington", "frisco", "jerry jones", "prescott"),
                     "rangers": ("texas rangers", "globe life", "arlington"),
                     "mavericks": ("dallas mavericks", "dallas", "american airlines center", "uta", "arlington")}


# Nov 25: Fort Worth Weekly's "Ate Days of Thanksgiving Leftovers" was a salsa brand's recipes ("Mrs. Renfro's, the worldwide salsa
# sensation with local ties, says ...")
_RECIPE_RE = re.compile(r"\b(?:recipes?|leftovers|how to make|make-ahead|meal prep)\b", re.I)


def other_teams_nickname(text: str) -> str:
    """Another team named like one of ours, with nothing in the story about ours: the other team's marker, or ''."""
    low = f" {(text or '').lower()} "
    for nick, others in _OTHER_NICKNAME_TEAMS.items():
        if not re.search(rf"\b{nick}\b", low):
            continue
        hit = next((o for o in others if o in low), "")
        if hit and not any(re.search(rf"\b{re.escape(m)}\b", low) for m in _OUR_TEAM_MARKERS[nick]):
            return hit
    return ""


def betting_promo(title: str, summary: str = "") -> bool:
    """'Cowboys vs. Eagles odds, picks, best bets', 'Get almost $4,000 in bonuses from betting apps': a sportsbook pitch
    carries a team name, so the DFW tier would keep it; it is an ad, not news."""
    return bool(_BETTING_RE.search(title or "") or _BETTING_RE.search((summary or "")[:300]))


_GAME_NOTES_RE = re.compile(r"^(?:(?:post|pre)-?game|game|weekly|match|series|week \d+)\s+(?:notes|quotes|notebook|stats)\b|"
                           r"^(?:notes|quotes)\s*(?:&|and)\s*(?:notes|quotes)\b|^box score\b|\bpostgame (?:notes|quotes)\b|"
                           r"^(?:game|match) (?:info|central|day central)\b|\bdepth chart\b|\bweekly release\b|"
                           r"^stats?\s*:|^by the numbers\b|"   # Nov 22: KXAN's stats explainer
                           # Nov 24: WFAA's "Texas high school football: Playoff matchups, schedule" is a listing
                           r":\s*(?:playoff\s+|bowl\s+|game\s+)?(?:matchups?|pairings|brackets?)(?:,?\s*(?:and\s+)?(?:schedules?|times|tv))?\s*$|"
                           # Nov 24: WFAA's "How to watch the NFL's Thanksgiving Day games", a day after the schedule post
                           r"^how to (?:watch|stream|listen)\b|\bwhere to (?:watch|stream)\b|\bwhat channel\b|\btv schedule\b", re.I)
_GRADES_RE = re.compile(r"\bgrades\s*:|\breport cards?\b", re.I)          # CBS's grades column, but only for a game: a school's
                                                                          # A-F grades or report card are education news


def game_notes(title: str) -> bool:
    """'Postgame Notes - vs. Utah', 'Notes & Quotes', 'Box Score', 'Weekly Release': a team's stat sheet for a game the page
    has already posted (Nov 22: TCU's postgame notes came an hour after the recap and opened "TEAM NOTES TCU has now scored
    in 432 consecutive games")."""
    t = (title or "").strip()
    if _GAME_NOTES_RE.search(t):
        return True
    sports = re.search(r"\bvs\.?\s|\b(?:college football|football|basketball|baseball|hockey|soccer|nfl|nba|mlb|nhl|mls|ncaa|"
                       r"week \d+|win|loss|game|season)\b", t, re.I)
    return bool(_GRADES_RE.search(t)) and (_sports_result(t) or bool(sports))


_COLUMN_RE = re.compile(r"^(?:[A-Z][a-z]+ on [A-Z][a-z]+|Opinion|Column|Commentary|Editorial|Letters?(?: to the [Ee]ditor)?|Analysis|Perspective|"
                        r"Guest column|Op-Ed|Essay|Review|Where I Live|My Fort Worth|Diary|Notebook|Letter from [A-Z][a-z]+|First Person|Voices)\s*[:|—–-]\s")


_EXPERT_RE = re.compile(r"\b(?:experts?|ethicists?|analysts?|professors?|economists?|attorneys?|lawyers?|historians?|psychologists?|"
                        r"doctors?|scientists?|strategists?|insiders?)\s+(?:weighs?|weighed)\s+in\b", re.I)


_ARCHIVE_RE = re.compile(r"^(?:watch|replay|rewind)\b[^.]{0,160}?\b(?:as it happened|archived? (?:footage|coverage|video|broadcast)|"
                         r"original (?:broadcast|coverage)|full (?:broadcast|newscast))\b|^(?:from the archives?|flashback|throwback)\b", re.I)


_RANKINGS_RE = re.compile(r"\b(?:top 25|top-25|power rankings?|coaches poll|ap poll|cfp rankings?|playoff rankings?|"
                          r"college (?:football|basketball) rankings?|bracketology|"
                          # Nov 26, render 274: CBS Sports' "Week 13 College Football Playoff impact games: USC-UCLA, Alabama-Auburn
                          # hold major implications", a national slate with a 2018 media-day photo
                          r"(?:playoff )?impact games|games to watch|must-watch games|games with (?:playoff |major |bowl )?implications)\b", re.I)
_LOCAL_TEAMS_RE = re.compile(r"\b(?:tcu|horned frogs|frogs|cowboys|mavericks|mavs|rangers|stars|fc dallas|wings|smu|mean green|unt|"
                             r"ut arlington|uta|mavericks)\b", re.I)


_COLUMN_ROUNDUP_RE = re.compile(
                         # Nov 25, ESPN: "Rams and Cowboys top Week 12 uniforms" ("what each NFL team is wearing"), a league roundup
                         r"\bweek \d+ uniforms\b|\buniforms? (?:tracker|roundup|rankings?|power rankings)\b|"
                         # Nov 27, render 310: ESPN's "Houston's all-black threads top best uniforms of college football Week 13"
                         r"\b(?:best|worst|coolest|ugliest|sharpest|favorite)\s+(?:[\w'-]+\s+){0,2}uniforms\b|\btop\s+(?:\d+\s+)?uniforms\b|"
                         r"\buniforms of (?:college football |the nfl |the nba |the )?week\b|"
                         r"\bwhat each (?:nfl |nba |college )?team is wearing\b|"
                         # Nov 26, render 264: the Arlington Report's weekly "Out and About in Arlington: ..." events column
                         r"^out and about\b|^weekend worthy\b|"
                         # Nov 26, render 268: ESPN's "With World Cup qualification at stake, the USWNT has no excuses"
                         r"\b(?:has|have) no excuses?\b|\bno more excuses\b|"
                         # Nov 25, render 257: CBS Sports' "NFL on Thanksgiving halftime shows: Ranking the 10 most memorable
                         # performances", a writer's list of past shows (drafted with the downtown skyline)
                         r"(?:^|[:;—–]\s*)ranking (?:the|every|all|each)\b|"
                         # Nov 27, render 304: CBS Sports' "A premature, unauthorized, tiered ranking of every possible Dallas
                         # Cowboys coach -- should Jerry Jones need it"
                         r"\branking of (?:every|all|each|the)\b|\btiered ranking\b|\btier list\b|\bshould [\w .'’-]{2,30} need it\b|"
                         r"\b\d+\s+(?:most\s+)?(?:memorable|iconic|greatest|unforgettable|legendary|underrated|overrated)\b|"
                         # Nov 25: CultureMap's "Get holly jolly at these 2026 holiday pop-up bars around Fort Worth": a guide's list
                         r"\b(?:at|to|try|visit|check out|hit|from) these\b(?:\s+[\w'’-]+){0,5}?\s+(?:bars|restaurants|spots|places|patios|"
                         r"brunches|shops|cafes|breweries|displays|markets|events)\b|"
                         # Nov 25: Fort Worth Weekly's "Film Shorts // November 25 – December 1, 2026" (capsule reviews of the week's
                         # movies) drew the Stockyards' cattle pens; a weekly listings page is a column, not news
                         r"^(?:film shorts|night & day|night and day|music listings|film listings|stage listings|art listings)\b|"
                         r"\s//\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d|"
                         # Nov 26, render 290: "'Happy Thanksgiving America': Jason Kelce leads reactions to Eagles' win over
                         # Cowboys": other people's posts about a game the page already reported
                         r"\b(?:leads?|tops) reactions\b|\b(?:social media|twitter|the internet|nfl world|fans|x) reacts?\b|"
                         r"\breactions? to (?:the )?[\w'’ .-]{0,40}?(?:win|loss|victory|defeat|collapse|comeback|meltdown|upset)\b|"
                         r"\b(?:winners and losers|takeaways|overreactions|what we learned|things we learned|observations from|"
                         r"instant analysis|hot takes?|mailbag|studs and duds|stock up,? stock down|"
                         r"grades for (?:every|each|all) (?:team|player|game)|week \d+ grades)\b|"   # Nov 22: CBS's "NFL Week 11 grades for every team"
                         # Nov 24: NBC 5's "Perfect offense, tolerable defense give Cowboys something to build on; will they?"
                         r"[;:,]\s*(?:but\s+)?(?:will|can|could|should|would|do|does|did|is|are)\s+(?:they|he|she|it|we|you)\b[^?]{0,30}\?\s*$|"
                         # Nov 24: CBS Sports' "Arch Manning may be ready to leave Texas. Is he ready to start in the NFL?"
                         r"[.!]\s+(?:is|are|will|can|could|should|would|does|do)\s+(?:he|she|they|it|this|that)\b[^?]{0,60}\?\s*$", re.I)


_GAME_PRESSER_RE = re.compile(r"\b(?:post-?game|pre-?game)\b", re.I)
_PRESSER_RE = re.compile(r"\b(?:press conference|presser|media availability|media session)\b", re.I)


_HIGHLIGHT_REEL_RE = re.compile(r"\b(?:best plays|top plays|week \d+ highlights|full highlights|game highlights|every (?:catch|touchdown|td|snap|sack)|"
                                r"mic'?d up|all-22|film room|condensed game)\b", re.I)


_CIVIC_NAMING_RE = re.compile(r"\b(?:streets?|roads?|avenues?|parks?|schools?|plazas?|library|libraries|buildings?|bridges?)\b[^.]{0,40}"
                              r"\b(?:dedicated|renamed|named after|named for)\b|\b(?:dedicat\w+|renam\w+)\b[^.]{0,40}"
                              r"\b(?:streets?|roads?|parks?|schools?|plazas?|library|bridges?)\b", re.I)
_NON_TARRANT_PLACES = ("dallas", "fair park", "plano", "frisco", "garland", "irving", "mckinney", "denton", "richardson", "mesquite",
                       "carrollton", "lewisville", "allen", "rowlett", "desoto", "duncanville", "cedar hill", "lancaster", "addison")
_TARRANT_PLACES = ("fort worth", "tarrant", "arlington", "grand prairie", "mansfield", "keller", "southlake", "grapevine", "colleyville",
                   "euless", "bedford", "hurst", "north richland hills", "haltom city", "benbrook", "crowley", "saginaw", "azle",
                   "white settlement", "watauga", "richland hills", "forest hill", "kennedale", "burleson", "weatherford")


def other_city_civic(title: str) -> bool:
    """'Fair Park streets dedicated in honor of 2 leaders from African American Museum in Dallas': another city's street
    names, park names and dedications are that city's civic news, not Fort Worth's (Nov 23, CBS News Texas)."""
    low = (title or "").lower()
    return bool(_CIVIC_NAMING_RE.search(title or "")) and any(p in low for p in _NON_TARRANT_PLACES) \
        and not any(p in low for p in _TARRANT_PLACES)


_NAME_RUN_RE = re.compile(r"\b([A-Z][\w&.'’-]+(?:\s+(?:of\s+)?[A-Z][\w&.'’-]+)+)\b")


def _subject_names(text: str) -> set[str]:
    from .images.subject import TEAM_WORDS
    names = set()
    for m in _NAME_RUN_RE.findall(text or ""):
        n = re.sub(r"^(?:the|dallas|fort worth|texas)\s+", "", m.lower())    # "Dallas Cowboys" is the Cowboys
        if len(n) > 3:
            names.add(n)
    low = f" {(text or '').lower()} "
    names.update(t for t in TEAM_WORDS if f" {t} " in low or f" {t}." in low or f" {t}," in low)
    return names


def same_subjects(text: str, posted_title: str) -> bool:
    """WFAA's 'Salvation Army kicks off Thanksgiving campaign at AT&T Stadium ... partnership with the Cowboys' came the
    morning after 'Dallas Cowboys mark 30 years of giving back with Salvation Army' went out (Nov 23): a video naming the
    same two subjects as a recent post is that post again."""
    return len(_subject_names(text) & _subject_names(posted_title)) >= 2


def highlight_reel(title: str) -> bool:
    """'George Pickens' Best Plays from 102-yard game | Week 11 Highlights': a team channel's highlight reel is a link
    to a clip, not Fort Worth news, and the sports cap carried two of them to the next morning (Nov 22)."""
    return bool(_HIGHLIGHT_REEL_RE.search(title or ""))


def routine_presser(title: str) -> bool:
    """'Jerry Jones: Postgame #TENvsDAL', 'Dak Prescott: Postgame Week 11': a team channel's press conference after a game
    the page has already reported is not news, and a cap would carry it to the next morning (Nov 22). A police chief's
    press conference about a shooting is news: only a sports presser is routine."""
    t = title or ""
    if _GAME_PRESSER_RE.search(t):
        return True
    if not _PRESSER_RE.search(t):
        return False
    from .images.subject import TEAM_WORDS, _PLAIN_TEAM_WORDS, _SPORTS_CUE_RE
    low = f" {_PRESSER_RE.sub(' ', t).lower()} "            # "press conference" is not a sports "conference"
    return bool(_SPORTS_CUE_RE.search(low)) or any(f" {w} " in low for w in TEAM_WORDS if w not in _PLAIN_TEAM_WORDS)


_SCENARIO_RE = re.compile(r"\b(?:scenarios?|what needs to happen|how [\w .'&-]{1,30} can (?:reach|make|join|clinch|get|win)|path to|"
                          r"playoff picture|bowl projections?|projected|projections?|bracketology|mock draft)\b|"
                          # Nov 24, ESPN: "To stay alive in NFC East, Cowboys need first back-to-back wins in a year"
                          r"^to (?:stay alive|stay in|keep pace|keep up|make the playoffs|reach the playoffs|win the|clinch|catch)\b|"
                          r"\bneeds? (?:first|to win|to beat|to string|a win|wins|help|a run|a miracle)\b|"
                          # Nov 27, render 298: the Cowboys channel's "Predicting the Cowboys' Tough Final Stretch | Special Edition"
                          r"\bpredict(?:ing|ions?)\b|\bremaining schedule\b|\bschedule breakdown\b|"
                          # Nov 27, render 300: CBS Sports' "2027 NFL Draft: Remaining games that will determine the draft order"
                          r"\bremaining games\b|\bdraft order\b|\bdraft position\b", re.I)


_OTHER_METRO_TEAM_RE = re.compile(r"\b(?:rockets|spurs|astros|texans|dynamo|houston dash|austin fc|san antonio fc)\b", re.I)
_DFW_TEAM_RE = re.compile(r"\b(?:cowboys|mavericks|mavs|rangers|stars|fc dallas|wings|tcu|horned frogs|frogs|smu|mustangs|unt|mean green|"
                          r"uta|baylor|texas tech|longhorns|aggies|dallas)\b", re.I)


def other_metro_team(title: str) -> bool:
    """'How a season without their admiral showed the Rockets what they were missing': another metro's team feature is
    that city's sports news (Nov 23, ESPN). A game against a DFW team stays."""
    return bool(_OTHER_METRO_TEAM_RE.search(title or "")) and not _DFW_TEAM_RE.search(title or "")


# Nov 27, render 299: NBC 5 carried AP's automated "Dallas Mavericks visit Phoenix Suns Friday in NBA Cup group stage" ("BOTTOM
# LINE: The Dallas Mavericks travel to play the Dallas Mavericks ...", records against winning teams): a stats sheet, not news
_AUTO_PREVIEW_RE = re.compile(r"\bBOTTOM LINE:|\bLAST TIME OUT:|\bTOP PERFORMERS:|\bINJURIES:|"
                              r"\bLINE:\s*[^;]{2,60}?[+-]\d{3}\b|\bover/under is\b", re.I)


def automated_preview(summary: str) -> bool:
    return bool(_AUTO_PREVIEW_RE.search(summary or ""))


def hypothetical_sports(title: str) -> bool:
    """'SEC Championship Game scenarios: How Texas can join Georgia in Atlanta': what might happen is not news, and the
    sports cap carried it into the next morning (Nov 23, KXAN)."""
    return bool(_SCENARIO_RE.search(title or ""))


def roundup_column(title: str) -> bool:
    """'NFL Week 11 winners and losers: Cowboys offense makes history ...', '3 takeaways from ...': a writer's verdict on
    games the page has already reported, not news (Nov 22, CBS Sports)."""
    return bool(_COLUMN_ROUNDUP_RE.search(title or ""))


# Nov 26, render 263: CBS News Texas's "Why do the Detroit Lions and Dallas Cowboys play every year on Thanksgiving? The history"
# (CBS Detroit's 1934 Portsmouth Spartans story) as a sports text card: the history of a tradition is a feature, not news
_EVERGREEN_RE = re.compile(r"[?:.]\s*(?:the|its|a brief|a short) history\b|^(?:the )?history of\b|"
                           r"\bwhy do(?:es)?\b[^?]{3,80}\bevery (?:year|thanksgiving|christmas|holiday|season)\b", re.I)


def evergreen_explainer(title: str) -> bool:
    return bool(_EVERGREEN_RE.search(title or ""))


def rankings_list(title: str) -> bool:
    """'Coaches Poll top 25: Texas, Tennessee climb; UCLA, Indiana tumble': a national ranking is a list, and two sentences
    from the middle of it ('Previously slotted at No. 13, Iowa remained there...') are not a post (Nov 22, render 123).
    A ranking that names a local team is that team's news and stays."""
    t = title or ""
    return bool(_RANKINGS_RE.search(t)) and not _LOCAL_TEAMS_RE.search(t)


_PRESS_RELEASE_RE = re.compile(r"\b(?:is|are|was|were) (?:pleased|proud|thrilled|excited|delighted|honored|happy) to "
                               r"(?:announce|share|welcome|introduce|unveil)\b", re.I)


# Nov 26, render 266: KENS 5's "Here, everything's better: H-E-B offers holiday savings to help fill the family table" (H-E-B's
# own slogan over its coupons and a $35 feast) was drafted as community news: a store's promotion reads like an ad
_RETAIL_PROMO_RE = re.compile(r"\bhere,? everything[’']?s better\b|"
                              r"\b(?:h-e-b|heb|walmart|target|kroger|costco|tom thumb|albertsons|aldi|sprouts|whataburger|buc-ee[’']?s|"
                              r"amazon|best buy|home depot|lowe[’']?s)\b[^.]{0,40}\b(?:offers?|announces?|rolls? out|launches?|unveils?)\b"
                              r"[^.]{0,30}\b(?:savings|deals|discounts?|coupons?|sales?|freebies|bundles?|meal deals?)\b", re.I)


def retail_promotion(title: str) -> bool:
    return bool(_RETAIL_PROMO_RE.search(title or ""))


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


_HOLIDAYS = r"thanksgiving|christmas|new year'?s|fourth of july|july 4(?:th)?|independence day|halloween|labor day|memorial day"
# the event is dated to a holiday's eve, or to the holiday itself or after it; "days before Thanksgiving" is true today
_HOLIDAY_EVE_RE = re.compile(rf"\b(?:the night before|the eve of)\s+({_HOLIDAYS})\b|\b({_HOLIDAYS})\s+eve\b", re.I)
_HOLIDAY_ON_RE = re.compile(rf"\b(?:on|after|during|over|the day after)\s+({_HOLIDAYS})\b|\b({_HOLIDAYS})\s+(?:day|morning|night|weekend)\b", re.I)
_PAST_HARM_RE = re.compile(r"\b(?:were|was) (?:killed|shot|found|hurt|injured)\b|\b(?:killed|died|dies|stabbed|murdered|drowned|crashed)\b|"
                           r"\b(?:fatally shot|shot and killed|(?:man|woman|teen|boy|girl|person|people|officer|deputy|\d+) shot)\b", re.I)
_DATED_PAST_RE = re.compile(r"\b(?:years? (?:ago|after|later|since)|anniversary|last year|a year after|since 20\d\d|in 20\d\d)\b", re.I)


def _holiday_date(name: str, year: int) -> datetime | None:
    from datetime import date, timedelta
    n = name.lower().replace("’", "'")
    if n == "thanksgiving":
        first = date(year, 11, 1)
        d = first + timedelta(days=(3 - first.weekday()) % 7 + 21)          # fourth Thursday of November
    elif n == "christmas":
        d = date(year, 12, 25)
    elif n.startswith("new year"):
        d = date(year + 1, 1, 1)
    elif n in ("fourth of july", "july 4", "july 4th", "independence day"):
        d = date(year, 7, 4)
    elif n == "halloween":
        d = date(year, 10, 31)
    elif n == "labor day":
        first = date(year, 9, 1)
        d = first + timedelta(days=(0 - first.weekday()) % 7)               # first Monday of September
    elif n == "memorial day":
        last = date(year, 5, 31)
        d = last - timedelta(days=last.weekday())                           # last Monday of May
    else:
        return None
    return datetime(d.year, d.month, d.day)


def holiday_not_yet(title: str, summary: str, published: datetime | None) -> bool:
    """'Crash report details how Fort Worth CEO, two children were killed the night before Thanksgiving', dated Nov 23 2026
    (Thanksgiving is Nov 26): a death dated to a holiday that has not come yet this year happened in an earlier year. KENS 5's
    feed brought back its Nov 2023 story with a new date (Nov 23). Dated follow-ups ("a year after ...") are news."""
    from datetime import timedelta
    if published is None:
        return False
    text = f"{title or ''}. {summary or ''}"
    if _DATED_PAST_RE.search(text):
        return False
    now = published.replace(tzinfo=None)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not _PAST_HARM_RE.search(sentence):
            continue
        for regex, offset in ((_HOLIDAY_EVE_RE, 1), (_HOLIDAY_ON_RE, 0)):
            for m in regex.finditer(sentence):
                day = _holiday_date(m.group(1) or m.group(2), now.year)
                if day is None:
                    continue
                event = day - timedelta(days=offset)
                if now < event and (event - now).days <= 45:
                    return True
    return False


# Nov 23, Fort Worth Weekly: "Simple Ways To Enjoy The End Of A North Texas Summer" ("several weeks of triple digits to
# negotiate") dated the week of Thanksgiving: a piece about the season we are not in is evergreen filler or an old story
_SUMMER_NOW_RE = re.compile(r"\b(?:end of (?:a |the |this )?(?:\w+ ){0,2}summer|last (?:days|weeks) of summer|beat the(?: \w+)? heat|"
                            r"summer heat|survive (?:the )?(?:\w+ )?summer|weeks of triple digits)\b", re.I)
_WINTER_NOW_RE = re.compile(r"\b(?:end of (?:a |the |this )?(?:\w+ ){0,2}winter|survive (?:the )?(?:\w+ )?winter|"
                            r"stay warm this winter|winter weather tips)\b", re.I)


def out_of_season(title: str, summary: str, published: datetime | None) -> bool:
    """A summer-is-here piece from November to March, or a winter-is-here piece from June to August."""
    if published is None:
        return False
    text = f"{title or ''} {(summary or '')[:400]}"
    month = published.month
    return bool(month in (11, 12, 1, 2, 3) and _SUMMER_NOW_RE.search(text) or month in (6, 7, 8) and _WINTER_NOW_RE.search(text))


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_RESULT_WORD = r"(?:win|won|wins|beat|beats|victory|loss|lost|defeat|defeated|fell|rout|routed|edged|upset|blowout)"
_RESULT_DAY_RE = re.compile(rf"\b{_RESULT_WORD}\b[^.!?]{{0,80}}?\b(?:on |last )?({'|'.join(_WEEKDAYS)})\b|"
                            rf"\b({'|'.join(_WEEKDAYS)})(?: night| afternoon)?(?:'s|’s)\s+[^.!?]{{0,30}}?\b{_RESULT_WORD}\b", re.I)


def stale_result(title: str, summary: str, now_local) -> bool:
    """A game result dated two or more days back: Nov 23 (a Monday), NBC 5's "No. 11 Texas Tech moves closer to another Big 12
    title game with win at Baylor" said "after Tech's 20-10 win over Baylor on Saturday". The next game's day ("visits Texas
    Tech on Thursday") has no result word beside it and does not count."""
    for m in _RESULT_DAY_RE.finditer(f"{title or ''}. {summary or ''}"):
        day = (m.group(1) or m.group(2)).lower()
        if (now_local.weekday() - _WEEKDAYS.index(day)) % 7 >= 2:
            return True
    return False


def expert_commentary(title: str) -> bool:
    """'Medical ethicist weighs in on North Texas transplant case': an outside expert's opinion of a story, not the story
    (Nov 22: two outlets' versions reached review an hour apart)."""
    return bool(_EXPERT_RE.search(title or ""))


# Nov 26, render 284: the Fort Worth Report's "'Club Kid' Review: From dance beats to heartbeats, Jordan Firstman's vibrant and
# touching debut feature" reached the photo step: a critic's review of a named work is the critic's opinion, not news
_WORK_REVIEW_RE = re.compile(r"^(?:[‘'\"“][^’'\"”]{1,80}[’'\"”]\s+|(?:Movie|Film|Album|Book|Theater|Theatre|Concert|Restaurant|TV|"
                             r"Show|Stage|Music|Dining)\s+)[Rr]eview\s*[:|—–-]\s")


def column_label(title: str) -> bool:
    """"Bob on Business: Biz in the front, party in the back ...", "Opinion: ...": a column speaks in its writer's voice, which is
    not a caption we can post as news. So does a critic's review of a film, a show or a restaurant."""
    t = (title or "").strip()
    return bool(_COLUMN_RE.match(t) or _WORK_REVIEW_RE.match(t))


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


# Nov 26, render 264: FOX 4's "Top Dallas Police spokesperson reinstated after public integrity investigation" (a crime text
# card): another DFW city's officials, hires, leaves and votes are that city's news. A crime there is still a crime story.
_DFW_CIVIC_RE = re.compile(r"\b(?:mayor|mayor pro tem|city council|council ?(?:member|man|woman)|city manager|police chief|fire chief|"
                           r"spokes(?:person|man|woman)|public integrity|reinstated|placed on (?:administrative )?leave|isd board|"
                           r"school board|trustees|county judge|commissioners court|city hall|zoning|city budget|tax rate|bond election)\b",
                           re.I)


def another_dfw_citys_government(title: str) -> bool:
    low = (title or "").lower()
    if any(w in low for w in ("fort worth", "tarrant", "dfw", "north texas", "arlington", "keller", "southlake", "mansfield")):
        return False
    places = set(OTHER_METROS) | set(_NON_TARRANT_PLACES)
    return bool(_DFW_CIVIC_RE.search(low)) and any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in places)


def another_citys_community_feature(title: str) -> bool:
    """Nov 27, render 309: WFAA's "Forced to flee their countries, Dallas gave them a place at the table this Thanksgiving" (a
    Dallas couple's ministry dinner, from the station's life/heartwarming section) was drafted as regional news with a stock
    Thanksgiving plate. Another DFW city's community feature (its nonprofit's dinner, its shelter's feast, its neighbor's good
    deed) is that city's story; a story the whole region shares names the region or one of our cities."""
    low = (title or "").lower()
    if any(w in low for w in _OUR_TITLE_PLACES) or any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in _TARRANT_PLACES):
        return False
    return any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in _NON_TARRANT_PLACES)


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
                         r"one person (?:shot|injured|hurt)|1 (?:shot|injured|hurt)|burglar|car break-ins?|shoplift|"
                         # Nov 27, render 297: WFAA's "Man attempts to set fire to Dallas Family Dollar, DFR says" (put out quickly,
                         # no one hurt) was drafted a day later: an attempted arson at another city's store is that city's blotter
                         r"attempts? to set (?:a )?fire|set(?:s|ting)? (?:a )?fires? (?:to|at|in|inside)|arson\w*|vandal\w*|graffiti|"
                         r"smash-and-grab|break-ins?|broke into|catalytic converters?|porch pirates?|package thie(?:f|ves))\b", re.I)


# Nov 25 (a Wednesday): WFAA's "North Texas man dead following shooting Sunday, Garland police say": another DFW city's shooting
# from three days back is that city's news, not this page's
_DAY_IN_TITLE_RE = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)


# Nov 26, render 263: FOX 4's "Trackdown: Help find Dallas rapper BFG Baandz's killer" (a shooting "earlier this year") was
# drafted for a Fort Worth page; a cold case in another DFW city is that city's appeal, not this page's news
_OLD_CRIME_RE = re.compile(r"\b(?:earlier this year|last year|last month|months ago|years ago|cold case|unsolved)\b|^trackdown\b", re.I)
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_IN_MONTH_RE = re.compile(r"\bin (" + "|".join(_MONTHS) + r")\b", re.I)


def another_citys_old_crime(title: str, now_local, summary: str = "") -> str:
    """When another DFW city's crime happened, if that was two or more days ago: the weekday in the headline, or the time the
    story gives ("earlier this year", "in June", a Trackdown cold case). '' otherwise."""
    low = (title or "").lower()
    if any(w in low for w in TARRANT_SIDE_WORDS):
        return ""
    m = _DAY_IN_TITLE_RE.search(title or "")
    if m and (now_local.weekday() - _WEEKDAYS.index(m.group(1).lower())) % 7 >= 2:
        return m.group(1).capitalize()
    text = f"{title or ''} {summary or ''}"
    old = _OLD_CRIME_RE.search(text)
    if old:
        return "a Trackdown cold case" if old.group(0).lower() == "trackdown" else old.group(0).lower()
    month = _IN_MONTH_RE.search(text)
    if month and _MONTHS.index(month.group(1).lower()) + 1 != now_local.month:
        return f"in {month.group(1).capitalize()}"
    return ""


# Nov 27, render 311: NBC 5's "'Everything is under control' after fire at Aerospace facility: Weatherford fire chief" came
# through the feed on Friday; its lead said the city "lifted a shelter-in-place order on Wednesday morning after a two alarm
# fire". A fire, a crash or a shooting two days gone is not breaking news; a follow-up (a name, a charge, a cause) is new news.
_HAPPEN_WORD = (r"(?:fires?|blaze|alarm|explosion|crash(?:ed)?|wreck|collision|shooting|shot|stabbing|stabbed|killed|died|dead|"
                r"arrested|escaped|evacuat\w*|shelter-in-place|lifted|broke out|burned|collapsed|flooded|rescued)")
_HAPPEN_DAY_RE = re.compile(rf"\b{_HAPPEN_WORD}\b[^.!?]{{0,80}}?\b(?:on |last |early |late )?({'|'.join(_WEEKDAYS)})\b|"
                            rf"\b({'|'.join(_WEEKDAYS)})(?: morning| night| afternoon| evening)?(?:'s|’s)?\s+[^.!?]{{0,40}}?\b{_HAPPEN_WORD}\b",
                            re.I)
_FUTURE_RE = re.compile(r"\b(?:will|set to|scheduled|slated|planned|plans? to|expected to|upcoming|next)\b", re.I)
_HAPPEN_FOLLOW_UP_RE = re.compile(r"\b(?:identif\w+|names?|named|charged?|charges|arrests?|arrested|sentenced|indicted|cause|update[sd]?|"
                           r"new details|lawsuit|sues|investigation (?:finds|reveals)|memorial|vigil|funeral|reopens?|reopened)\b", re.I)


def stale_happening(title: str, summary: str, now_local) -> str:
    """The weekday a fire, crash or shooting happened, when the headline and the lead put it two or more days back and the
    headline reports no follow-up. '' otherwise."""
    if _HAPPEN_FOLLOW_UP_RE.search(title or ""):
        return ""
    lead = " ".join(re.split(r"(?<=[.!?])\s+", (summary or "").strip())[:2])
    for sentence in re.split(r"(?<=[.!?])\s+", f"{title or ''}. {lead}"):
        if _FUTURE_RE.search(sentence):
            continue
        for m in _HAPPEN_DAY_RE.finditer(sentence):
            day = (m.group(1) or m.group(2)).lower()
            if (now_local.weekday() - _WEEKDAYS.index(day)) % 7 >= 2:
                return day.capitalize()
    return ""


# Nov 27, render 311: CBS Texas's "Pregnant prisoner escapes in corrections vehicle after officers stop at Whataburger in New
# Mexico" passed as Texas news on "Whataburger": a story the headline sets in another state is that state's news
OTHER_STATES = ("new mexico", "oklahoma", "louisiana", "arkansas", "arizona", "colorado", "kansas", "missouri", "nebraska", "nevada",
                "utah", "california", "florida", "georgia", "tennessee", "alabama", "mississippi", "kentucky", "ohio", "michigan",
                "illinois", "indiana", "wisconsin", "minnesota", "iowa", "new york", "new jersey", "pennsylvania", "virginia",
                "north carolina", "south carolina", "oregon", "idaho", "montana", "wyoming", "south dakota", "north dakota", "maryland",
                "massachusetts", "connecticut", "maine", "vermont", "new hampshire", "rhode island", "delaware", "west virginia",
                "alaska", "hawaii", "mexico")
_IN_OTHER_STATE_RE = re.compile(r"\b(?:in|near|outside|across) (?:the state of |rural |southern |northern |eastern |western |central )?"
                                r"(?:" + "|".join(re.escape(st) for st in OTHER_STATES) + r")\b(?! city)", re.I)


_TEXAS_BRANDS = ("h-e-b", "buc-ee", "whataburger")      # a Texas brand's store in another state is still that state's story


def another_states_story(title: str) -> bool:
    low = (title or "").lower()
    if any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in PLACE_WORDS if w not in _TEXAS_BRANDS):
        return False
    return bool(_IN_OTHER_STATE_RE.search(low))


TARRANT_SIDE_WORDS = ("fort worth", "tarrant", "arlington", "keller", "southlake", "mansfield", "haltom", "hurst", "euless", "bedford",
                      "grapevine", "north richland", "benbrook", "burleson", "crowley", "white settlement", "saginaw", "watauga",
                      "azle", "weatherford")


_BIG_FIRE_RE = re.compile(r"\b(?:\d-alarm|two-alarm|three-alarm|four-alarm|five-alarm|massive|apartment complex|dozens|"
                          r"evacuat\w*|wildfire|grass fire|brush fire|acres)\b", re.I)


def another_citys_house_fire(title: str) -> bool:
    """'Dallas family escapes devastating Thanksgiving Day fire': one home's fire in another DFW city, with no one killed, is that
    city's news (Nov 27, render 301); a death, a multi-alarm or a wildfire stays regional news."""
    low = (title or "").lower()
    if any(w in low for w in TARRANT_SIDE_WORDS) or not fire_incident(title):
        return False
    places = set(OTHER_METROS) | set(_NON_TARRANT_PLACES)
    if not any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in places):
        return False
    if _BIG_FIRE_RE.search(title or ""):
        return False
    return not any(w in low for w in ("dead", "dies", "died", "killed", "kills", "deadly", "death", "fatal"))


def another_citys_blotter(title: str) -> bool:
    """'Juvenile shot in vehicle in stable condition, Dallas police say no arrests made yet': a single shooting with no death
    and no arrest in another DFW city is that city's police blotter, not Fort Worth news."""
    low = (title or "").lower()
    if any(w in low for w in ("fort worth", "tarrant", "arlington", "keller", "southlake", "mansfield", "haltom", "hurst", "euless", "bedford",
                              "grapevine", "north richland", "benbrook", "burleson", "crowley", "white settlement", "saginaw", "watauga", "azle", "weatherford")):
        return False
    return bool(_BLOTTER_RE.search(low)) and not any(w in low for w in ("dead", "dies", "died", "killed", "kills", "deadly", "death", "fatal",
                                                                        "murder", "homicide", "manhunt", "amber alert"))


# roads and places a Fort Worth driver uses: a closure on one of them is this page's traffic news
FORT_WORTH_SIDE_TRAFFIC = ("fort worth", "tarrant", "arlington", "grand prairie", "keller", "southlake", "mansfield", "haltom", "hurst",
                           "euless", "bedford", "grapevine", "north richland", "benbrook", "burleson", "crowley", "white settlement",
                           "saginaw", "watauga", "azle", "weatherford", "colleyville", "i-30", "interstate 30", "i-20", "interstate 20",
                           "i-35w", "35w", "i-820", "loop 820", "sh 360", "highway 360", "state highway 360", "sh 183", "highway 183",
                           "airport freeway", "sh 121", "highway 121", "sh 114", "highway 114", "chisholm trail", "dfw airport",
                           "trinity railway express", "trinity metro", "tex rail", "texrail")


def another_citys_traffic(title: str) -> bool:
    """'Northbound Dallas North Tollway to close overnight at Northwest Highway' (Nov 23): a closure on Dallas's own roads is
    Dallas's traffic; a Fort Worth-side road or a road between the two cities (I-30, I-20, SH 360, SH 183, DFW Airport) stays."""
    low = (title or "").lower()
    return not any(w in low for w in FORT_WORTH_SIDE_TRAFFIC)


OTHER_METRO_AGENCIES = ("hpd", "apd", "sapd", "harris county", "travis county", "bexar county", "el paso county", "houston isd", "austin isd")


def other_metro_url(url: str) -> bool:
    """A station that files a story under its own city ("kxan.com/news/local/austin/...") calls it that city's local news:
    Nov 24, KXAN's "Save Muny deal sparks concerns about future of Austin research lab" (a golf course deal) passed as Texas
    sports, the one beat the other-metro headline check leaves alone."""
    low = (url or "").lower()
    if any(f"/local/{m.replace(' ', '-')}/" in low for m in OTHER_METROS):
        return True
    # Nov 27, render 304: KXAN's "State Theatre to host free Texas vs. Texas A&M rivalry watch party" (kxan.com/things-to-do/):
    # another metro station's things-to-do section lists that city's events
    return any(st in low for st in OTHER_METRO_STATIONS) and bool(re.search(r"/(?:things-to-do|events|entertainment/events)/", low))


# Nov 26, render 283: KXAN's "Rabid dog found in San Marcos as Texas rabies cases top 2025 totals" passed for "Texas" in its
# second clause: the headline's own story (its first clause) is set in another metro, and the state's count is the context
_CLAUSE_SPLIT_RE = re.compile(r"\s+(?:as|while|amid|after|but|with)\s+|[;:—–]\s*|,\s+")
_OUR_TITLE_PLACES = ("fort worth", "tarrant", "dfw", "north texas", "arlington", "keller", "southlake", "mansfield")


def other_metro_title(title: str) -> bool:
    """'HPD: Teens find man\'s body in elevator shaft of abandoned downtown Houston building': a headline set in another metro,
    with none of our places in it, is that metro's local story whatever its beat."""
    low = (title or "").lower()
    first = _CLAUSE_SPLIT_RE.split(low, maxsplit=1)[0]
    if (not any(w in first for w in _OUR_TITLE_PLACES + ("texas",))
            and re.search(r"\bin (?:downtown |north |south |east |west |northwest |northeast |southwest |southeast )?(?:"
                          + "|".join(re.escape(m) for m in OTHER_METROS) + r")\b", first)):
        return True                         # "Rabid dog found in San Marcos as Texas rabies cases top 2025 totals"
    if any(w in low for w in _OUR_TITLE_PLACES + ("texas",)):
        return False
    return any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS + OTHER_METRO_AGENCIES)


_METRO_EVENT_RE = re.compile(r"\b(?:rodeo|livestock show|stock show|state fair|county fair|festival|parade|concert series|"
                             r"lineup|line-up|performers|headliners?)\b", re.I)


def other_metro_event(title: str) -> bool:
    """'Parker McCollum, Lyle Lovett revealed as final performers announced for 2027 San Antonio Rodeo' (Nov 24, KENS 5): another
    metro's rodeo or festival is that city's calendar, whatever beat its keywords file it under (rodeo read as sports)."""
    return other_metro_title(title) and bool(_METRO_EVENT_RE.search(title or ""))


def other_metro_roundup(title: str) -> bool:
    """'Austin weekend: Theater performances, Bastrop B-day', 'Things to do in Houston this weekend': another city's events
    calendar, however good the weekend is there."""
    low = (title or "").lower()
    return bool(_ROUNDUP_RE.search(low)) and any(re.search(r"\b" + re.escape(m) + r"\b", low) for m in OTHER_METROS) and "fort worth" not in low and "tarrant" not in low


STATEWIDE_WORDS = ("amber alert", "manhunt", "statewide", "across texas", "texas dps", "border patrol", "cartel", "human smuggling",
                   "ercot", "texas rangers investigat")      # a highway's name alone is not statewide news: a crash on San Antonio's I-35 is San Antonio's

# Nov 27, render 305: KENS 5's "Suspect arrested after alleged shooting, pursuit involving DPS trooper in downtown San Antonio"
# passed as statewide news for "A Texas DPS trooper" in its summary. An agency's name says who answered the call, not how far
# the news reaches: DPS troopers, Border Patrol agents and the Texas Rangers work every city in the state, so a story its
# headline or first line sets in another metro stays that metro's news. Only a word about the story's reach carries it.
_STATEWIDE_REACH = ("amber alert", "manhunt", "statewide", "across texas", "ercot")
_IN_OTHER_METRO_RE = re.compile(r"\bin (?:downtown |north |south |east |west |northwest |northeast |southwest |southeast )?(?:"
                                + "|".join(re.escape(m) for m in OTHER_METROS) + r")\b")


def set_in_other_metro(title: str, summary: str = "") -> bool:
    """The headline, or the summary's first sentence, puts the story in another Texas metro and never in ours."""
    lead = re.split(r"(?<=[.!?])\s+", (summary or "").strip(), maxsplit=1)[0]
    text = f"{title or ''} {lead}".lower()
    if any(w in text for w in _OUR_TITLE_PLACES):
        return False
    return other_metro_title(title) or bool(_IN_OTHER_METRO_RE.search(text))


def statewide(story) -> bool:
    """News the whole state follows: an Amber Alert, a manhunt, the grid. An agency's name counts only for a story no other
    metro claims."""
    text = story.text()
    if any(w in text for w in _STATEWIDE_REACH):
        return True
    return any(w in text for w in STATEWIDE_WORDS) and not set_in_other_metro(story.title, story.summary or "")


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
                        r"stuns?|stunned|upsets?|shuts? out|blanks?|outlasts?|ends? in|ended in|scorigami|final score|"
                        # Nov 27, render 298: ESPN's "Joe Milton has huge game as Eagles shock Cowboys on Thanksgiving"
                        r"shocks?|shocked|stuns?|rallies past|rally past|comes? back to beat|came back to beat|survives?|survived|"
                        r"escapes?|escaped|outlasts?|outscores?|outscored|downs|downed)\b", re.I)


def _sports_result(title: str) -> bool:
    """A game result carries a score, a team nickname or a result verb; a crash, a fire or a shooting carries none."""
    from .images.subject import TEAM_WORDS
    low = f" {(title or '').lower()} "
    sporty = re.sub(r"\b(?:ends? in|ended in|final score)\b", " ", title or "", flags=re.I)   # a standoff "ends in" an arrest too
    return bool(_SCORE_RE.search(title or "") or _RESULT_RE.search(sporty)) or \
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


# one subject, several spellings: two outlets carry the same moment whichever spelling each uses
WATCHLIST_ALIASES = {"grand theft auto vi": "gta 6", "grand theft auto 6": "gta 6", "gta vi": "gta 6",
                     "the oscars": "oscars", "oscar winners": "oscars", "academy awards": "oscars",
                     "grammy winners": "grammys", "macy's parade": "thanksgiving day parade"}


def watch_term(term: str) -> str:
    return WATCHLIST_ALIASES.get(term, term)


def watch_title(title: str) -> str:
    """The plain headline with every watchlist spelling folded to one ("Grand Theft Auto VI" and "GTA 6" read alike)."""
    t = _plain(title)
    for alias in sorted(WATCHLIST_ALIASES, key=len, reverse=True):
        t = re.sub(r"\b" + re.escape(alias) + r"\b", WATCHLIST_ALIASES[alias], t)
    return t


def watchlist_hit(watchlist: list[str], title: str) -> str | None:
    """The watchlist subject a headline names, as a whole phrase: "GTA Vice City" is not "GTA VI"."""
    t = _plain(title)
    return next((w for w in watchlist if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t)), None)


SPORTS_EVENT_TERMS = {"super bowl", "world series", "nba finals", "stanley cup final", "world cup final", "college football playoff",
                      "march madness", "final four", "halftime show", "heisman trophy", "nfl draft", "nba draft"}
_HYPOTHETICAL_RE = re.compile(r"\?|\b(contenders?|hopes?|hopeful|chances|odds|could|would|might|favou?rites?|dark horse|path to|"
                              r"projections?|predictions?|picks?|bubble|scenarios?|race)\b", re.I)

# a streaming service is a national moment when it is the story (a price hike, an outage, a password crackdown), never because
# a story airs there: Nov 23, "Tyson Fury Reveals Schizophrenia Diagnosis in Netflix Documentary" (Variety and Deadline) took
# the day's national slot, and "Netflix" in two unrelated headlines counted as two outlets carrying one moment
# Nov 27, render 316: The Verge's and IGN's "Yooka-Laylee's free upgrade is skipping Xbox" took the national slot on "xbox": a
# console or a phone is the moment only when the headline is about it (a price hike, an outage, a launch), not a game's port
PLATFORM_TERMS = ("netflix", "disney+", "hbo max", "hulu", "peacock", "paramount+", "prime video", "apple tv",
                  "xbox", "playstation", "nintendo", "iphone")


_MOMENT_GENERIC = {"season", "series", "official", "final", "first", "trailer", "teaser", "show", "film", "movie", "release",
                   "date", "episode", "premiere", "finale", "watch", "review", "update", "announces", "reveals", "revealed", "gets",
                   "more", "after", "with", "from", "into", "about", "this", "that", "what", "when", "year", "years", "their",
                   "will", "have", "been", "just", "over", "here", "says", "back", "big", "news", "week", "today", "night"}


def _moment_words(title: str, term: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9+]+", _plain(title).replace("'s", "")):
        if len(w) < 4 or w in term.split() or w in _MOMENT_GENERIC:
            continue
        for end in ("ing", "ed", "s"):
            if len(w) > len(end) + 3 and w.endswith(end):
                w = w[:-len(end)]
                break
        out.add(w)
    return out


def shared_subject(a: str, b: str, term: str) -> bool:
    """Two headlines that carry a big-moment term are one moment only when they share a subject besides the term:
    "Netflix raises prices again" and "Netflix's price hike hits subscribers" share "price"; a 'Lil Kev' trailer and an
    Avengers trailer share nothing but "trailer"."""
    return bool(_moment_words(a, term) & _moment_words(b, term))


def term_is_subject(term: str, title: str) -> bool:
    """A big-moment term counts for a headline unless it is a platform the headline only mentions in passing."""
    if term not in PLATFORM_TERMS:
        return True
    lead = re.sub(r"^[\s'\"‘’“”]+", "", _plain(title))
    return lead.startswith(term)


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


_NOT_NAMES = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march", "april",
              "may", "june", "july", "august", "september", "october", "november", "december", "thanksgiving", "christmas",
              "halloween", "easter", "texas", "north", "the", "a", "an", "new", "breaking", "update", "watch", "video", "photos"}


def same_event(title: str, summary: str, posted_title: str) -> bool:
    """Nov 23: FOX 4's "Dallas Cowboys raffle off Thanksgiving game tickets for blood drive donors" five hours after "Dallas
    Cowboys partner with Carter BloodCare to host blood drive ahead of Thanksgiving": the headlines share five words, just
    under same_story's bar, and the new story's lead names the partner the first headline named. Headlines that share four
    content words are one event when every name the earlier headline carried beyond them is in the new headline or lead."""
    ka = {_stem(w) for w in title_key(_digits_to_words(title))}
    kb = {_stem(w) for w in title_key(_digits_to_words(posted_title))}
    shared = ka & kb
    if len(shared) < 4:
        return False
    names = []
    for n in re.findall(r"\b[A-Z][A-Za-z&'’.-]*(?:\s+[A-Z][A-Za-z&'’.-]*)*", posted_title or ""):
        words = [w for w in re.findall(r"[a-z0-9']+", n.lower()) if w not in _NOT_NAMES and len(w) > 2]
        if words and not all(_stem(w) in shared for w in words):
            names.append(" ".join(words))
    if not names:
        return False                       # nothing but the shared words: "Fort Worth forecast for Tuesday" is another day's forecast
    lead = " ".join(re.findall(r"[a-z0-9']+", f"{title or ''} {(summary or '')[:700]}".lower()))
    return all(f" {n} " in f" {lead} " for n in names)


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


# Nov 27, render 309: WFAA's "Jerry Jones says he still believes in Brian Schottenheimer despite mounting meltdowns by Cowboys"
# was drafted six hours after ESPN's "Cowboys' Jones backing Schottenheimer despite 'damning setbacks'" went out: an owner's vote
# of confidence in his coach is one piece of news, whoever reports it and however they word the backing
_CONFIDENCE_RE = re.compile(r"\b(?:backs|backing|backed|believes? in|still believes|supports?|supporting|stands? by|standing by|"
                            r"sticks? with|sticking with|confidence in|vote of confidence|committed to|commits to|"
                            r"not (?:firing|going to fire|making a change)|job (?:is )?safe|right (?:coach|man|guy|person) for)\b", re.I)
_CAP_WORD_RE = re.compile(r"\b([A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?)\b")
_NOT_SURNAMES = {"cowboys", "rangers", "mavericks", "mavs", "stars", "texans", "frogs", "horned", "longhorns", "aggies", "texas",
                 "dallas", "fort", "worth", "arlington", "says", "said", "still", "despite", "after", "amid", "with", "backing",
                 "backs", "believes", "supports", "stands", "sticks", "coach", "owner", "head", "general", "manager", "jerry's"}


def same_vote_of_confidence(title: str, summary: str, posted_title: str) -> bool:
    """A post in the last two days said someone backs someone (an owner his coach); a story that says the same about the
    same two people is the same news."""
    if not _CONFIDENCE_RE.search(posted_title or "") or not _CONFIDENCE_RE.search(f"{title or ''} {(summary or '')[:300]}"):
        return False

    def names(text: str) -> set[str]:
        return {w.lower().removesuffix("'s") for w in _CAP_WORD_RE.findall(text or "") if len(w) >= 4} - _NOT_SURNAMES
    return len(names(title) & names(posted_title)) >= 2


# a numbered seat is one race: Nov 25, the Fort Worth Report's "Texas Supreme Court mulls candidate's eligibility in House 93 race"
# came the morning after FOX 4's "Texas House District 93 winner remains unknown amid eligibility dispute" went out. Until there
# is a decision (a ruling, a winner certified or sworn in, a concession), it is the same news.
_SEAT_RE = re.compile(r"\b(?:(?:texas\s+)?(?:house|senate)\s+(?:district\s+)?|(?:hd|sd)\s*-?\s*|district\s+|precinct\s+|place\s+|"
                      r"ward\s+|seat\s+)(\d{1,3})\b", re.I)
_CONTEST_RE = re.compile(r"\b(?:eligib\w*|recount|runoff|race|election|results?|winner|dispute|challenged?|challenges|contest(?:ed|s)?|"
                         r"ballots?|votes?|candidates?)\b", re.I)
_DECISION_RE = re.compile(r"\b(?:rules?|ruled|ruling|decides?|decided|decision|orders?|ordered|declares?|declared|certif\w*|sworn|"
                          r"swears|concedes?|conceded|wins|won|dismiss\w*|rejects?|rejected|upholds?|upheld|overturns?|overturned|"
                          r"disqualif\w*|ineligible|eligible to serve)\b", re.I)


def _seat_keys(text: str) -> set[tuple[str, str]]:
    keys = set()
    for m in _SEAT_RE.finditer(text or ""):
        word = m.group(0).lower()
        kind = "senate" if ("senate" in word or word.startswith("sd")) else "house" if ("house" in word or word.startswith("hd")) else "seat"
        keys.add((kind, m.group(1)))
    return keys


# Nov 25: WFAA's "What is Weatherford Aerospace?" came an hour after "Residents told to shelter in place as crews respond to a fire
# at Weatherford Aerospace" went out, and its lead only restated the fire
_EXPLAINER_RE = re.compile(r"^[\"'“‘]?(?:what is|what are|who is|who are|what we know|what to know|here's what|here’s what|"
                           r"everything (?:we know|to know)|what happened)\b", re.I)
_PROPER_RUN_RE = re.compile(r"\b([A-Z][A-Za-z&'’.-]+(?:\s+[A-Z][A-Za-z&'’.-]+)+)\b")


# Nov 25: WFAA's YouTube "A fire was reported at Weatherford Aerospace on West 3rd Street in Weatherford, officials said" came two
# hours after "Residents told to shelter in place as crews respond to a fire at Weatherford Aerospace" went out
_INCIDENT_RE = re.compile(r"\b(fire|fires|blaze|explosion|blast|shooting|stabbing|crash|wreck|standoff|flood|flooding|collapse|"
                          r"chemical leak|gas leak|hazmat|evacuation|shelter in place|shelter-in-place)\b", re.I)


_FOLLOW_UP_RE = re.compile(r"\b(cause|caused|rebuild|rebuilds|reopen|reopens|reopened|killed|dead|dies|died|death|injured|hurt|"
                           r"arrest|arrested|charged|identified|lawsuit|sues|sued|investigation finds|fined|cited|layoffs?|"
                           r"lifted|all clear|contained|under control|extinguished)\b", re.I)


def same_incident(title: str, summary: str, posted_title: str) -> bool:
    """Two headlines about one incident at one named place: they share a multi-word proper name and an incident word, and
    the newer one reports nothing the first did not (a cause, a death, an arrest, the all-clear is news)."""
    a, b = _INCIDENT_RE.findall(title or ""), _INCIDENT_RE.findall(posted_title or "")
    if not a or not b:
        return False
    new_facts = {w.lower() for w in _FOLLOW_UP_RE.findall(title or "")} - {w.lower() for w in _FOLLOW_UP_RE.findall(posted_title or "")}
    if new_facts:
        return False
    names = [n.lower() for n in _PROPER_RUN_RE.findall(title or "") if n.split()[0].lower() not in ("a", "an", "the", "what", "who")]
    names = [n for n in names if n not in ("fort worth", "north texas", "tarrant county", "dallas county")]
    return any(n in (posted_title or "").lower() for n in names)


# Nov 26, render 265: FOX 4's "Fort Worth country singer found not guilty after murder trial" a day after CBS's "Fort Worth
# recording artist acquitted of murder in 2025 shooting death of man": one verdict, told twice
_VERDICT_CLASSES = (("acquittal", re.compile(r"\b(?:acquitted|acquittal|found not guilty|not guilty)\b", re.I)),
                    ("conviction", re.compile(r"\b(?:convicted|found guilty|guilty verdict|pleads? guilty|pleaded guilty)\b", re.I)),
                    ("sentence", re.compile(r"\bsentenced\b", re.I)),
                    ("mistrial", re.compile(r"\bmistrial\b", re.I)))
_VERDICT_CRIME_RE = re.compile(r"\b(?:capital murder|murder|manslaughter|assault|robbery|shooting|killing|death|sexual assault|kidnapping)\b", re.I)
_VERDICT_PLACES = ("fort worth", "arlington", "tarrant", "keller", "mansfield", "grapevine", "dallas", "denton", "plano", "parker county",
                   "johnson county", "weatherford", "burleson")
_VERDICT_PEOPLE = (("singer", "artist", "rapper", "musician"), ("officer", "deputy", "cop", "trooper"), ("teacher", "coach", "principal"),
                   ("pastor", "priest", "minister"), ("doctor", "nurse"), ("mayor", "councilman", "councilwoman", "council member"))


def same_verdict(title: str, summary: str, posted_title: str) -> bool:
    """Two headlines about one verdict: the same outcome for the same crime in the same place, about the same kind of person
    (or an acquittal or mistrial, which are rare enough that two in two days are one)."""
    def classes(t: str) -> set[str]:
        return {name for name, rx in _VERDICT_CLASSES if rx.search(t or "")}
    a, b = classes(title), classes(posted_title)
    shared = a & b
    if not shared:
        return False
    la, lb = (title or "").lower(), (posted_title or "").lower()
    if not {m.lower() for m in _VERDICT_CRIME_RE.findall(la)} & {m.lower() for m in _VERDICT_CRIME_RE.findall(lb)}:
        return False
    if not {p for p in _VERDICT_PLACES if p in la} & {p for p in _VERDICT_PLACES if p in lb}:
        return False
    if shared & {"acquittal", "mistrial"}:
        return True
    return any(any(w in la for w in group) and any(w in lb for w in group) for group in _VERDICT_PEOPLE)


# Nov 26, render 266: FOX 4's "Fort Worth shooting leaves three men hospitalized after fight" after NBC 5's "Investigation
# underway after 3 injured in Fort Worth shooting" went out: one shooting, the same three victims, told twice
_COUNT_WORDS = {"two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
_VICTIM_COUNT_RE = re.compile(r"\b(\d{1,2}|two|three|four|five|six|seven|eight|nine|ten)\s+(?:people\s+|men\s+|women\s+|teens?\s+|"
                              r"children\s+|kids\s+|victims\s+|adults\s+)?(?:injured|hurt|dead|killed|wounded|hospitalized|shot|stabbed|"
                              r"people|men|women|teens|victims)\b", re.I)
_COUNT_INCIDENT_RE = re.compile(r"\b(shooting|shot|stabbing|stabbed|crash|wreck|collision|fire)\b", re.I)
_COUNT_CITIES = ("fort worth", "arlington", "keller", "mansfield", "grapevine", "euless", "bedford", "hurst", "haltom city", "north richland hills",
                 "burleson", "weatherford", "dallas", "denton", "irving", "garland", "plano")


def same_count_incident(title: str, summary: str, posted_title: str) -> bool:
    def facts(t: str):
        low = (t or "").lower()
        counts = {_COUNT_WORDS.get(m.lower(), m) for m in _VICTIM_COUNT_RE.findall(low)}
        kinds = {"shooting" if k in ("shot", "shooting") else "stabbing" if k.startswith("stab") else "crash" if k in ("crash", "wreck", "collision")
                 else k for k in (m.lower() for m in _COUNT_INCIDENT_RE.findall(low))}
        return counts, kinds, {c for c in _COUNT_CITIES if c in low}
    ca, ka, pa = facts(title)
    cb, kb, pb = facts(posted_title)
    return bool(ca & cb and ka & kb and pa & pb)


# Nov 26, render 282: WFAA's 5 p.m. "Neighbors kick in door to rescue elderly couple as Thanksgiving fire burns North Texas homes"
# ("A fire that started at a home business in the back of a house spread to a neighboring home early Thanksgiving morning in
# Fort Worth") was the 7:33 a.m. post's "Home workshop sparks early morning fire on Thanksgiving in Fort Worth" told again
_FIRE_GENERIC = {"fire", "fires", "blaze", "spark", "sparks", "sparked", "crew", "crews", "firefighter", "firefighters", "respond",
                 "responds", "responded", "responding", "department", "officials", "said", "says", "after", "amid", "with", "from",
                 "into", "near", "their", "this", "that", "fort", "worth", "north", "texas", "county", "tarrant"}
_FIRE_PLACES = ("fort worth", "arlington", "north richland hills", "richland hills", "haltom city", "hurst", "euless", "bedford",
                "keller", "southlake", "grapevine", "mansfield", "burleson", "crowley", "benbrook", "white settlement", "saginaw",
                "lake worth", "azle", "watauga", "colleyville", "grand prairie", "weatherford", "cleburne", "denton", "dallas")


# Nov 27, render 293: NBC 5's "Fort Worth firefighters battle 27 fires in just over 24 hours" (the family that lost two pets)
# was the run of fires our Nov 26 1:10 p.m. post had covered ("2 pets die, 1 rescued as Fort Worth firefighters respond to
# multiple fires amid cold weather"): two roundups of a city's fires within the duplicate window are one story
_FIRE_ROUNDUP_RE = re.compile(r"\b(?:multiple|several|numerous|many|dozens of|a string of|a series of|a rash of|a spate of|"
                              r"\d+)\s+(?:house\s+|structure\s+|grass\s+)?fires\b", re.I)


def same_fire(title: str, summary: str, posted_title: str) -> bool:
    """A later story about the fire a post already covered: both are fires in the same city, and most of the posted headline's
    own words (the home, the workshop, the hour) are in the new story. A death, a cause or an arrest is news (_FOLLOW_UP_RE)."""
    if not fire_incident(posted_title) or not (fire_incident(title) or re.search(r"\bfires?\b", title or "", re.I)):
        return False
    if _FIRE_NOT_INCIDENT_RE.search(title or ""):
        return False
    new_facts = {w.lower() for w in _FOLLOW_UP_RE.findall(title or "")} - {w.lower() for w in _FOLLOW_UP_RE.findall(posted_title or "")}
    if new_facts:
        return False
    text = f"{title or ''} {summary or ''}".lower()
    posted = (posted_title or "").lower()
    places = [c for c in _FIRE_PLACES if re.search(r"\b" + re.escape(c) + r"\b", posted)]
    if not places or not any(re.search(r"\b" + re.escape(c) + r"\b", text) for c in places):
        return False
    if _FIRE_ROUNDUP_RE.search(title or "") and _FIRE_ROUNDUP_RE.search(posted_title or ""):
        return True                         # one city's run of fires, counted again: "multiple fires", then "27 fires"
    words = {w for w in re.findall(r"[a-z]{4,}", posted) if w not in _FIRE_GENERIC}
    for c in places:
        words -= set(c.split())
    if len(words) < 3:
        return False
    shared = {w for w in words if re.search(r"\b" + re.escape(w) + r"(?:s|es)?\b", text)}
    return len(shared) >= 3 and len(shared) >= 0.75 * len(words)


# Nov 27, render 296: FOX 4's 7:34 a.m. video "Fort Worth police searching for hit-and-run suspect" ("asking for the public's
# help identifying a driver") was its 9:22 p.m. story the page had posted ("Fort Worth motorcyclist recovering after
# hit-and-run", police footage of the driver) told again
_HIT_AND_RUN_RE = re.compile(r"\bhit[- ]and[- ]run\b", re.I)


def same_hit_and_run(title: str, summary: str, posted_title: str) -> bool:
    """Two hit-and-run headlines in the same city within the duplicate window are one incident, unless the new one reports
    what the first did not: an arrest, a charge, an identification, a death."""
    if not (_HIT_AND_RUN_RE.search(title or "") and _HIT_AND_RUN_RE.search(posted_title or "")):
        return False
    new_facts = {w.lower() for w in _FOLLOW_UP_RE.findall(title or "")} - {w.lower() for w in _FOLLOW_UP_RE.findall(posted_title or "")}
    if new_facts:
        return False
    low, posted = (title or "").lower(), (posted_title or "").lower()
    return any(re.search(r"\b" + re.escape(c) + r"\b", low) and re.search(r"\b" + re.escape(c) + r"\b", posted) for c in _FIRE_PLACES)


def explainer_of_posted(title: str, summary: str, posted_title: str) -> bool:
    """A 'What is X?' or 'What we know about X' piece about a subject a post already covered is that story again."""
    if not _EXPLAINER_RE.search((title or "").strip()):
        return False
    names = [n.lower() for n in _PROPER_RUN_RE.findall(title or "") if n.split()[0].lower() not in ("what", "who", "here's", "here’s")]
    return any(n in (posted_title or "").lower() for n in names)


def same_seat_news(title: str, summary: str, posted_title: str) -> bool:
    """Two headlines about the same numbered seat's contest, the newer one reporting no decision."""
    a, b = _seat_keys(title), _seat_keys(posted_title)
    if not any(x[1] == y[1] and (x[0] == y[0] or "seat" in (x[0], y[0])) for x in a for y in b):
        return False
    if not (_CONTEST_RE.search(title or "") and _CONTEST_RE.search(posted_title or "")):
        return False
    return not _DECISION_RE.search(title or "")


_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def _digits_to_words(text: str) -> str:
    return re.sub(r"\b(10|[1-9])\b", lambda m: _WORDS[m.group(1)], text or "")


def _stem(word: str) -> str:
    """reopens/reopen, years/year, explosions/explosion: enough for two headlines about one event to meet."""
    for end in ("ies", "es", "s", "ed", "ing"):
        if len(word) > len(end) + 3 and word.endswith(end):
            return word[:-len(end)] + ("y" if end == "ies" else "")
    return word


# Texas places that are also people's names: Nov 24, ESPN's "Cardinals fire DC Rallis; Austin takes over on interim basis" (a
# coach named Austin) counted as a Texas story. These need a place's context to count.
AMBIGUOUS_PLACES = ("austin", "tyler", "irving", "allen", "sherman", "temple", "marshall", "denton", "kyle", "victoria")
_PLACE_CONTEXT_FMT = (r"(?:\b(?:in|at|near|from|of|to|outside|around|across)\s+{p}\b|\b{p}(?:'s|’s)?\s+(?:police|fire|isd|city|area|"
                      r"council|mayor|energy|fc|metro|market|airport|county|residents|school|schools|police department|-based)\b|"
                      r"\b{p},?\s+(?:texas|tx)\b|\b{p}-area\b|\b{p}-based\b)")


def _place_hit(kw: str, text: str) -> bool:
    if kw not in AMBIGUOUS_PLACES:
        return _has_word(kw, text)
    return bool(re.search(_PLACE_CONTEXT_FMT.format(p=re.escape(kw)), text))


def relevance_score(story: Story, keywords: list[str]) -> int:
    title = story.title.lower()
    summary = story.summary.lower()
    score = 0
    for kw in keywords:
        kw = kw.lower()
        if _place_hit(kw, title):
            score += 2
        elif _place_hit(kw, summary):
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


# Nov 26, render 281: "holiday", "christmas" and "thanksgiving" were community words, and a title hit counts double, so on
# Thanksgiving a Fort Worth house fire with a rescue, a holiday-crash study and a restaurant story were all filed as community
# and held by its daily cap: the occasion says when, not what the story is; it decides only when nothing else does
OCCASION_WORDS = ("holiday", "holidays", "christmas", "thanksgiving")


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
                             r"charged in(?=.{0,60}\b(?:scam|fraud|scheme|murder|killing|death|shooting|stabbing|robbery|attack|case|theft|"
                             r"heist|assault|kidnapping|crash)\b)|"
                             r"wanted|murder|homicide|shooting|stabbing|robbery|burglar\w*|ponzi|fraud|assault|kidnapp\w*|manhunt|suspect|"
                             r"solicit\w* (?:a |an )?(?:minor|child|teen|\d{1,2}-year-old|sex|prostitution)|solicitation of a minor|"
                             r"set(?:s|ting)? (?:a )?fires? (?:to|at|in|inside)|arson\w*)\b", re.I)
# Nov 22: "North Texas traffic stop leads to arrest of armed man accused of soliciting 15-year-old on Snapchat" was filed as traffic
# Nov 24: "Georgia prison inmates charged in $1 million jury duty scam targeting North Texans" was filed as "other"
# Nov 26, render 278: "Man attempts to set fire to Dallas Family Dollar, DFR says" was filed as "other": someone setting a fire is crime
# a final score with its result is a game: "Mavrik Bourque ... scores his first goal for Nashville in 3-1 win" read as "other"
_GAME_RESULT_RE = re.compile(r"\b\d{1,3}-\d{1,3} (?:win|wins|loss|losses|victory|defeat|rout|shutout|comeback|upset)\b|"
                             r"\b(?:beat|beats|edges?|routs?|blanks?|downs|tops|outlast|outlasts|stun|stuns)\s+(?:the\s+)?(?-i:[A-Z])[\w.'’-]*"
                             r".{0,30}?\b\d{1,3}-\d{1,3}\b(?!\s*%)|"
                             r"\bscores? (?:his|her|their|a|the) (?:first |second |third |\d+(?:st|nd|rd|th) |game-winning |go-ahead |overtime )?"
                             r"(?:goal|touchdown|hat trick|run)\b|\bhat trick\b", re.I)


_NOT_BREAKING_RE = re.compile(r"\b(?:active shooter|evacuation|lockdown|shelter in place|hazmat|explosion)\b(?=[^.]{0,40}\b(?:training|"
                              r"drills?|exercises?|course|program|preparedness|simulation|grant|funding)\b)|"
                              r"\b(?:training|drills?|exercises?|course|program|preparedness|simulation|grant|funding)\b[^.]{0,40}"
                              r"\b(?:active shooter|evacuation|lockdown|shelter in place|hazmat|explosion)\b", re.I)
# a flood-control project is public works, not weather: Nov 25, the City of Fort Worth's "Work session, special called meeting
# scheduled Dec. 1" (a Texas Water Development Board grant for "Lebow Flood Mitigation") was filed as weather and held by its cap
_NOT_WEATHER_RE = re.compile(r"\bflood(?:plain|way)s?\b|\bflood (?:mitigation|control|insurance|plains?|prevention|protection|"
                             r"risk reduction|infrastructure|bonds?|stud(?:y|ies)|maps?|projects?|channels?)\b"
                             # Nov 26, render 261: the Fort Worth Report's state-bird story ("Others hail the mockingbird") was
                             # drafted with a supercell: to hail someone, or to hail from somewhere, is not weather
                             r"|\ball hail\b|\bhail(?:s|ed|ing)? (?:the|as|from|a|an|it|its|their|his|her|our|this|that|him|them)\b", re.I)
# a council's meeting notice is local government, whatever its agenda lists (cold-weather preparations, a flood grant, a museum)
_MEETING_TITLE_RE = re.compile(r"\b(?:work sessions?|council meetings?|special[- ]called meetings?|city council|commissioners(?:'|’)? court)\b",
                               re.I)


def meeting_notice(title: str | None) -> bool:
    return bool(_MEETING_TITLE_RE.search(title or ""))


# a headline about a fire that happened is a fire story, whatever day it fell on: Nov 26, render 260, WFAA's "Home workshop
# sparks early morning fire on Thanksgiving in Fort Worth" was filed as community (its "Thanksgiving" outscored the fire)
_FIRE_TITLE_RE = re.compile(
    r"(?<!\bon )\b(?:house|home|apartment|duplex|condo|workshop|garage|warehouse|business|building|plant|vehicle|car|truck|grass|brush|"
    r"structure|commercial|church|school|restaurant|early[- ]morning|overnight|deadly|fatal|massive|major|large|\d-alarm|two-alarm|"
    r"three-alarm|four-alarm|thanksgiving|christmas|holiday|devastating|destructive|raging|intense|huge|"
    # Nov 27, render 301: "Dallas family escapes devastating Thanksgiving Day fire" was filed as community with a courthouse
    r"(?:thanksgiving|christmas|new year'?s|holiday) (?:day|eve|night|morning))\s+fires?\b"
    r"|(?<!\bon )\bfires?\s+(?:destroys?|destroyed|damages?|damaged|displaces?|displaced|guts?|gutted|engulfs?|engulfed|kills?|killed|"
    r"injures?|injured|breaks? out|broke out|spreads?|rips? through|tears? through|burns?|burned|burning|scorches?|scorched)\b"
    r"|\b(?:sparks?|sparked|ignites?|ignited|battle|battles|battling|respond(?:s|ed|ing)? to|extinguish(?:es|ed)?|put out|douse[sd]?)\b"
    r"(?:\s+[\w'-]+){0,3}?\s+fires?\b"
    # Nov 27, render 308: NBC 5's "'Everything is under control' after fire at Aerospace facility: Weatherford fire chief"
    # was filed as "other": a fire at a named place is a fire
    r"|(?<!\bon )\bfires?\s+at\s+(?:a\s+|an\s+|the\s+)?(?:[\w'&.-]+\s+){0,3}?(?:facility|plant|home|house|apartment|apartments|"
    r"complex|building|business|warehouse|school|church|restaurant|store|shop|hotel|motel|factory|refinery|site|center|"
    r"yard|mill|barn|garage|depot|hangar|airport|mall|campus|stadium|arena|park)\b", re.I)
_FIRE_NOT_INCIDENT_RE = re.compile(r"\b(?:training|drills?|exercises?|prevention|safety tips?|awareness|grants?|academy|recruits?)\b", re.I)


def fire_incident(title: str | None) -> bool:
    t = title or ""
    return bool(_FIRE_TITLE_RE.search(t)) and not _FIRE_NOT_INCIDENT_RE.search(t)
_NOT_CRIME_RE = re.compile(r"\bcardiac arrests?\b|\bheart attacks?\b"
                           r"|\b(?:texas |state )?bar (?:foundation|association|exam|of texas)\b|\bstate bar\b"
                           r"|\bgrand theft auto\b", re.I)
# ("Texas Bar Foundation" is lawyers, not a bar: Nov 22 a young lawyers' grant was filed as food; "Grand Theft Auto VI" is a
# game, and its "theft" filed The Verge's GTA headlines as crime, which no national moment may be)


# a police scene still under way is breaking news, not the day's crime roundup: Nov 23, FOX 4's "Police, SWAT units responding
# after 1 shot by barricaded suspect in Arlington home" waited behind the crime cap while the standoff went on
_ACTIVE_SCENE_RE = re.compile(r"\b(?:swat|standoff|barricaded|barricade situation|active shooter|shelter[- ]in[- ]place|lockdown|"
                              r"hostage|manhunt)\b", re.I)
_SCENE_OVER_RE = re.compile(r"\b(?:ends?|ended|over|arrested|in custody|surrender(?:s|ed)?|apprehended|captured|charged|identified|"
                            r"lifted|resolved|peacefully)\b", re.I)


def active_scene(title: str) -> bool:
    return bool(_ACTIVE_SCENE_RE.search(title or "")) and not _SCENE_OVER_RE.search(title or "")


def infer_category(story: Story) -> str:
    if _TITLE_CRIME_RE.search(story.title or "") and story.category_hint != "sports":
        return "crime"                      # "Arlington pastor convicted for Ponzi scheme" is crime, whatever a channel's boilerplate says
    if re.search(r"\bmenus?\b", story.title or "", re.I):
        return "food"                       # Nov 25: NBC 5's "Annual Dallas Cowboys Thanksgiving Day game menu revealed" is food, not
                                            # sports: a menu takes a picture of the food, never a text card
    if fire_incident(story.title) and story.category_hint != "sports":
        return "breaking"                   # "Home workshop sparks early morning fire on Thanksgiving in Fort Worth"
    from .images.subject import light_show
    if light_show(story.title):
        return "events"                     # Nov 26, render 288: "Christmas lights bring families to Texas Motor Speedway" was
                                            # filed as sports for the speedway and went to a sports text card: a light show takes
                                            # a picture of the lights, or none
    if _GAME_RESULT_RE.search(story.title or ""):
        return "sports"                     # a final score is a game, whichever sport the keywords miss
    if meeting_notice(story.title) and story.category_hint != "sports":
        return "politics"                   # "Work session, special called meeting scheduled Dec. 1" is the council's business
    text = _NOT_WEATHER_RE.sub(" ", _NOT_CRIME_RE.sub(" ", story.text()))   # "Runner in cardiac arrest saved by nurses" is not a crime story
    title = _NOT_WEATHER_RE.sub(" ", _NOT_CRIME_RE.sub(" ", story.title.lower()))
    # training for an emergency is not the emergency: Nov 25, KVUE's "Texas State's ALERRT Center receives $10M to expand active
    # shooter response training" was filed as breaking news and drafted as a text card
    text, title = _NOT_BREAKING_RE.sub(" ", text), _NOT_BREAKING_RE.sub(" ", title)
    # another region's story is breaking news only when its headline says so: Nov 23, KVUE's "Mexico demands SpaceX clean up
    # suspected rocket debris washing ashore near Texas" was filed as breaking for "explosion" in its lead, a background fact
    title_only_breaking = (story.extra or {}).get("scope") in ("texas", "national") or bool((story.extra or {}).get("national"))
    best, best_hits = None, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        if cat == "breaking" and title_only_breaking and not any(_has_word(w, title) for w in words):
            continue
        hits = sum(1 for w in words if _has_word(w, text))
        # title hits count double
        hits += sum(1 for w in words if _has_word(w, title))
        if hits > best_hits:
            best, best_hits = cat, hits
    if story.category_hint and (best_hits == 0 or story.category_hint in ("weather", "events", "sports", "crime")):
        return story.category_hint if story.category_hint in CATEGORIES else (best or "other")
    if not best and any(_has_word(w, title) for w in OCCASION_WORDS):
        return "community"                  # "Happy Thanksgiving, Fort Worth": the holiday itself
    return best or story.category_hint or "other"


DEFERRED_MAX_AGE_HOURS = 36.0    # a story a daily cap held back may still run the next day while it is this fresh

# Nov 27, render 295: WFAA's 8:55 p.m. "Northbound I-35 closed in Denton due to 'hazard' damaging tires" ("drivers will have to
# exit at Fort Worth Drive as crews clean the roadway") was drafted for 8:02 the next morning: a road closed right now is news
# for a few hours; by the next post slot it has reopened, and a planned closure says when ("this weekend", "until Monday")
CLOSURE_MAX_AGE_HOURS = 4.0
_LIVE_CLOSURE_RE = re.compile(r"\b(?:closed|shut down|blocked|backed up|lanes? (?:closed|blocked)|traffic (?:stopped|backed up))\b", re.I)
_PLANNED_CLOSURE_RE = re.compile(r"\b(?:will (?:be )?clos\w*|to close|closing|for (?:days|weeks|months)|through (?:the weekend|\w+day)|"
                                 r"until (?:further notice|\w+day)|this weekend|next week|construction|long-term|indefinitely|"
                                 r"overnight closures?|nightly)\b", re.I)


def stale_closure(story: Story, now: datetime) -> bool:
    """A road reported closed or blocked hours ago, with no planned duration: by the time the post goes out it has reopened."""
    if story.source_kind not in ("rss", "video") or story.published is None:
        return False
    if not _LIVE_CLOSURE_RE.search(story.title or "") or _PLANNED_CLOSURE_RE.search(story.text()):
        return False
    return story.age_hours(now) > CLOSURE_MAX_AGE_HOURS


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
    skipped_titles = state.recent_skipped_titles(now, hours=72) if hasattr(state, "recent_skipped_titles") else []
    watchlist = [w.lower() for w in (rel.get("watchlist", []) or [])]
    national_terms = [w.lower() for w in (rel.get("national_keywords", []) or [])]
    min_outlets = int(rel.get("national_min_outlets", 2))
    # which national headlines carry each big-moment term right now: one outlet is a story, several carrying the same
    # story is a moment (Nov 23: "trailer" in Deadline's 'Lil Kev' headline counted Variety's Avengers trailer as a second outlet)
    term_titles: dict[str, list[tuple[str, str]]] = {}
    for s in stories:
        if s.extra.get("national"):
            t = _plain(s.title)
            for term in national_terms:
                if term in t and term_is_subject(term, s.title):
                    term_titles.setdefault(term, []).append((s.source, s.title))

    # the same count for watchlist subjects: an outlet's own beat writes about its subject all day (Nov 23: IGN's "GTA 6 Players
    # Are Upset Its New Train Can Actually Be Stopped" took the national slot as a "GTA 6" story); the moment is the story
    # several national outlets carry at once
    watch_titles: dict[str, list[tuple[str, str]]] = {}
    for s in stories:
        if s.extra.get("national"):
            w = watchlist_hit(watchlist, s.title)
            if w:
                watch_titles.setdefault(watch_term(w), []).append((s.source, watch_title(s.title)))

    def outlets_carrying(term: str, story: Story) -> set[str]:
        return {src for src, title in term_titles.get(term, [])
                if src == story.source and title == story.title or shared_subject(title, story.title, term)}

    def outlets_watching(term: str, story: Story) -> set[str]:
        key, mine = watch_term(term), watch_title(story.title)
        return {src for src, title in watch_titles.get(key, [])
                if src == story.source and title == mine or shared_subject(title, mine, key)}
    for story in stories:
        if state.skipped(story.id):
            dropped.append((story, "skipped by the reviewing session"))
            continue
        if shopping_guide(story.title, story.url):
            dropped.append((story, "shopping guide, not news"))
            continue
        if story.source_kind == "rss" and station_video_page(story.url):
            dropped.append((story, "a station's video page: a clip the page cannot show"))
            continue
        if magazine_section(story.url):
            dropped.append((story, "a magazine's culture, food or travel feature, not news"))
            continue
        if story.extra.get("national") and _TEASER_RE.search(story.title or ""):
            # Nov 27, render 302: IGN's "New Avengers: Doomsday Teaser Shows Steve Rogers in Latveria ..."
            dropped.append((story, "a studio's teaser or trailer: promotion, not news"))
            continue
        if story.extra.get("national") and national_feature(story.title, story.url):
            # Nov 24: CBS Sports' "Why the Cowboys and Lions always play on Thanksgiving Day" passed on the Cowboys' name
            dropped.append((story, "a national outlet's magazine feature or explainer, not news"))
            continue
        if betting_promo(story.title, story.summary or ""):
            dropped.append((story, "sports betting picks or promo, not news"))
            continue
        if not story.official and _RECIPE_RE.search(story.title or ""):
            dropped.append((story, "a recipe feature, not news"))          # Fort Worth Weekly's salsa brand's leftovers recipes
            continue
        twin_team = other_teams_nickname(story.text())
        if twin_team:
            dropped.append((story, f"another team with our team's nickname ({twin_team})"))   # the Oklahoma State Cowboys
            continue
        if not story.official and gambling_advertorial(story.title, story.summary or ""):
            dropped.append((story, "a gambling pitch that names no Texas place, not news"))
            continue
        if game_notes(story.title):
            dropped.append((story, "a team's game notes or quotes sheet, not a story"))
            continue
        if story.source_kind in ("rss", "video") and retail_promotion(story.title):
            dropped.append((story, "a store's promotion (reads like an ad)"))
            continue
        if story.source_kind == "rss" and not story.official and press_release(story.title, story.summary or ""):
            dropped.append((story, "an organization's press release, not news"))
            continue
        if story.source_kind == "rss" and other_city_civic(story.title):
            dropped.append((story, "another city's street or park dedication"))
            continue
        if story.source_kind == "video":
            vtwin = state.recent_title_like(story.title, now, hours=48,
                                            match=lambda x, y: same_subjects(f"{x}. {(story.summary or '')[:300]}", y))
            if vtwin:
                dropped.append((story, f"a video of a story already posted: {vtwin[:60]}"))
                continue
        if story.source_kind == "video" and highlight_reel(story.title):
            dropped.append((story, "a team's highlight reel video"))
            continue
        if story.source_kind == "video" and routine_presser(story.title):
            dropped.append((story, "a team's routine press conference video"))
            continue
        if story.source_kind == "rss" and other_metro_team(story.title) and (story.category_hint == "sports" or
                                                                             infer_category(story) == "sports"):
            dropped.append((story, "another metro's team feature"))
            continue
        if story.source_kind == "rss" and automated_preview(story.summary or ""):
            dropped.append((story, "an automated stats preview (BOTTOM LINE), not news"))
            continue
        if story.source_kind in ("rss", "video") and hypothetical_sports(story.title) and (story.category_hint == "sports" or
                                                                                            infer_category(story) == "sports"):
            dropped.append((story, "a what-if sports piece (scenarios, projections), not news"))
            continue
        if story.source_kind == "rss" and roundup_column(story.title):
            dropped.append((story, "a roundup column (winners and losers, takeaways), not news"))
            continue
        if story.source_kind in ("rss", "video") and evergreen_explainer(story.title):
            dropped.append((story, "an evergreen explainer (the history of a tradition), not news"))
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
        if story.source_kind == "rss" and out_of_season(story.title, story.summary or "", story.published):
            dropped.append((story, "a piece about a season we are not in"))
            continue
        if story.source_kind == "rss" and holiday_not_yet(story.title, story.summary or "", story.published):
            dropped.append((story, "an old story: it dates a death to a holiday that has not come yet this year"))
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
        twin = next((t for t in recent_titles if same_story(story.title, t) or same_event(story.title, story.summary or "", t)), None)
        if twin:
            dropped.append((story, f"already posted from another outlet: {twin[:60]}"))
            continue
        # Nov 24: WFAA's "Texas A&M names Dr. John Thornton as Interim Athletic Director", a day after the session skipped ESPN's
        stwin = next((t for t in skipped_titles if same_story(story.title, t) or same_event(story.title, story.summary or "", t)), None)
        if stwin:
            dropped.append((story, f"another outlet's version of a story the session skipped: {stwin[:60]}"))
            continue
        if not is_fresh(story, now, max_age) and not (state.deferred(story.id) and is_fresh(story, now, DEFERRED_MAX_AGE_HOURS)):
            dropped.append((story, f"older than {max_age:.0f}h"))      # a cap-held story gets a second day (State.defer)
            continue
        if stale_closure(story, now):
            dropped.append((story, f"a road closure reported over {CLOSURE_MAX_AGE_HOURS:.0f} hours ago: the road has likely reopened"))
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
                hit = watchlist_hit(watchlist, story.title)
                if hit and hit in SPORTS_EVENT_TERMS and _HYPOTHETICAL_RE.search(title):
                    hit = None                    # "building a World Series contender?": a feature that names the event, not the event
                lone = None
                if hit and hit not in SPORTS_EVENT_TERMS and len(outlets_watching(hit, story)) < min_outlets:
                    lone, hit = hit, None         # one outlet's story about a watchlist subject is that outlet's beat
                if hit is None:
                    hit = next((t for t in national_terms if t in title and term_is_subject(t, story.title)
                                and len(outlets_carrying(t, story)) >= min_outlets), None)
                if hit and infer_category(story) in ("crime", "traffic"):
                    hit = None
                if hit in ("announces tour", "tour dates", "stadium tour") and not _TEXAS_STOP_RE.search(f"{story.title} {story.summary or ''}"):
                    dropped.append((story, "a tour with no Texas stop"))   # Nov 24: U2's 2027 stadium tour, Miami and two LA shows
                    continue
                seen = hit or lone
                if seen and national_feature(story.title, story.url):
                    dropped.append((story, f"a magazine feature about {seen}, not the moment itself"))
                    continue
                if seen and awards_trade(story.title):
                    dropped.append((story, f"awards-season trade news about {seen}, not the moment itself"))
                    continue
                if seen and industry_trade(story.title, story.url):
                    dropped.append((story, f"industry trade news about {seen}, not the moment itself"))
                    continue
                if seen and any(watch_term(seen) in watch_title(t) for t in recent_titles):
                    dropped.append((story, f"national moment already covered: {seen}"))
                    continue
                if lone and hit is None:
                    dropped.append((story, f"one outlet's {lone} story: a national moment is one several national outlets carry"))
                    continue
                if hit:
                    tier = ("national", 0.6)
                    story.extra["national_term"] = hit
            if tier is None:
                why = "national outlet, no watchlist or shared big-moment term" if story.extra.get("national") else f"not local enough (relevance {story.relevance} < {min_rel})"
                dropped.append((story, why))
                continue
            cat = infer_category(story)
            if tier[0] == "texas" and cat in ("crime", "traffic", "food", "events") and not statewide(story):
                dropped.append((story, f"other-metro {cat}, not statewide"))   # a San Antonio DWI verdict or food truck is not Fort Worth news
                continue
            if tier[0] == "texas" and other_metro_url(story.url) and not statewide(story):
                dropped.append((story, "another metro's local story"))         # the outlet filed it under its own city
                continue
            if tier[0] == "texas" and cat not in ("sports", "politics", "business") and other_metro_title(story.title) \
                    and not statewide(story):
                dropped.append((story, "another metro's local story"))         # a body found in a downtown Houston elevator shaft is Houston's news
                continue
            if tier[0] in ("texas", "dfw") and another_states_story(story.title):
                dropped.append((story, "another state's story"))                # a New Mexico prison escape is New Mexico's news
                continue
            if tier[0] == "texas" and other_region(story.title) and not statewide(story):
                dropped.append((story, "another region's story"))              # fall foliage in South Central Texas is KENS 5's weather blog
                continue
            if tier[0] == "texas" and other_metro_local(story.title) and not statewide(story):
                dropped.append((story, "another city's government"))             # Austin's mayor pro tem is Austin's news
                continue
            if tier[0] == "dfw" and another_dfw_citys_government(story.title):
                dropped.append((story, "another city's government"))             # a Dallas spokesperson's leave is Dallas's news
                continue
            if tier[0] == "dfw" and cat in ("community", "other") and another_citys_community_feature(story.title):
                dropped.append((story, "another city's community feature"))   # a Dallas ministry's Thanksgiving dinner is Dallas's
                continue
            if tier[0] == "dfw" and another_citys_house_fire(story.title):
                dropped.append((story, "another city's house fire"))         # a Dallas family's house fire, everyone out, is Dallas news
                continue
            if tier[0] == "dfw" and cat == "crime" and another_citys_blotter(story.title):
                dropped.append((story, "another city's police blotter"))     # a Dallas shooting with no death and no arrest is Dallas's blotter
                continue
            if tier[0] == "dfw" and cat == "crime":
                day = another_citys_old_crime(story.title, now.astimezone(settings.tz), story.summary or "")
                if day:
                    when = f"{day}, days ago" if day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday") else day
                    dropped.append((story, f"another city's crime from {when}"))   # a Garland shooting on Sunday, read on Wednesday
                    continue
            if tier[0] == "dfw" and cat == "traffic" and another_citys_traffic(story.title):
                dropped.append((story, "another city's traffic"))            # a Dallas North Tollway closure is Dallas's traffic
                continue
            if tier[0] in ("texas", "dfw") and other_metro_event(story.title):
                dropped.append((story, "another metro's rodeo, festival or lineup"))
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
        if story.category == "crime" and story.extra.get("scope", "local") == "local" and active_scene(story.title):
            story.category = "breaking"
        if story.category == "sports" and story.source_kind == "rss" and \
                stale_result(story.title, story.summary or "", now.astimezone(settings.tz)):
            dropped.append((story, "a game result two or more days old"))
            continue
        if story.category in ("breaking", "crime", "traffic") and story.source_kind == "rss":
            gone = stale_happening(story.title, story.summary or "", now.astimezone(settings.tz))
            if gone:
                dropped.append((story, f"a {story.category} story from {gone}, days ago"))   # a Wednesday fire read on Friday
                continue
        if story.category in excluded:
            dropped.append((story, f"excluded category: {story.category}"))
            continue
        kept.append(story)
    return kept, dropped


_DATED_TITLE = re.compile(r"\b(?:for|on)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b", re.I)


_AHEAD_OF_HOLIDAY_RE = re.compile(r"\b(?:ahead of|before|leading up to|in the lead-up to|days before)\s+(?:the\s+)?(thanksgiving|christmas|new year'?s)\b",
                                  re.I)


def stale_dated_title(title: str, now_local) -> bool:
    """'Fort Worth forecast for Tuesday, November 17' on a Thursday is not news; a title dated before today is dropped.
    So is a headline set "ahead of" a holiday that has come: Nov 26, render 265, "Dallas food pantry sees increased need ahead
    of Thanksgiving" was drafted for Thanksgiving morning."""
    h = _AHEAD_OF_HOLIDAY_RE.search(title or "")
    if h:
        name, today = h.group(1).lower(), now_local.date()
        # the shared holiday table puts New Year's in the coming January; in January itself the holiday has just come
        when = today.replace(month=1, day=1) if name.startswith("new year") and today.month == 1 else _holiday_date(name, today.year)
        if when is not None and today >= (when.date() if hasattr(when, "date") and callable(when.date) else when):
            return True
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
