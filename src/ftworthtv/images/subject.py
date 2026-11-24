"""The photo must show what the post is about.

A photo that merely rhymes with the story (an exchange building for a company's IPO, a downtown street for a list of
festivals, a chapel for a football game) is wrong, and readers notice at once. This module decides, from the headline,
what a photo would have to depict, and the pipeline obeys it three times: when the photo is chosen, when the card is
written to disk (the subject is saved next to the image), and right before publishing, when the saved subject is checked
against the headline again and the post is held if it does not fit.

The rule: if the headline names a specific subject (a team, a company, a school district, a person, a venue), the photo
must be of that subject or of its home ground; a generic beat photo (a skyline, a school bus, an exchange) is allowed only
for an institution it genuinely depicts (buses for a school district) or for a story with no named subject at all. When
nothing verified exists, the card goes out with no photo rather than the wrong one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .library import FORT_WORTH_ONLY, OTHER_CITIES, SPORTS_VARIANTS, TOPIC_RULES, topic_excluded, venue_fits

# topics that depict one specific subject; everything else in TOPIC_RULES is a beat (police, storm, highway, skyline ...)
ENTITY_TOPICS = {
    "dickies-arena", "will-rogers", "att-stadium", "globe-life-field", "stars-ice", "aac", "toyota-stadium", "texas-motor-speedway",
    "tcu-football", "tcu", "uta", "nrg-stadium", "daikin-park", "toyota-center", "frost-bank-center", "ut-austin", "texas-am",
    "texas-tech", "baylor", "smu", "unt", "keller-isd", "northwest-isd", "transit", "courthouse", "sundance-square", "stockyards",
    "kimbell", "modern", "bass-hall", "zoo", "botanic-garden", "water-gardens", "convention-center", "dfw-airport", "alliance",
    "trinity-river", "heb", "bucees", "whataburger", "capitol", "city-hall", "anthropic", "lottery",
}
# an institution named in the headline may be shown by the beat photo that depicts it
INSTITUTION_FALLBACK = {
    "isd": ["school-bus", "schools"], "school": ["school-bus", "schools"], "schools": ["school-bus", "schools"],
    "police": ["police"], "sheriff": ["police"], "fire": ["fire"], "council": ["city-hall"], "county": ["courthouse"],
    "court": ["courthouse"], "hospital": ["hospital"], "health": ["hospital"], "metro": ["transit"], "txdot": ["highway"],
    "ercot": ["power"], "oncor": ["power"],
    # consumer products: the category photo depicts the subject matter (a controller for a game, a phone for a handset)
    "xbox": ["gaming"], "playstation": ["gaming"], "ps5": ["gaming"], "nintendo": ["gaming"], "switch": ["gaming"], "steam": ["gaming"],
    "iphone": ["smartphone"], "galaxy": ["smartphone"], "pixel": ["smartphone"],
    "house": ["capitol"], "senate": ["capitol"], "legislature": ["capitol"], "lawmakers": ["capitol"],
    "netflix": ["streaming"], "hbo": ["streaming"], "disney+": ["streaming"], "hulu": ["streaming"],
}
ATTRIBUTION = ("says", "said", "tells", "told", "warns", "warned", "announces", "announced", "reports", "reported", "confirms")
PLACES = ("fort worth", "tarrant county", "tarrant", "texas", "north texas", "dfw", "dallas-fort worth", "metroplex", "arlington",
          "keller", "southlake", "mansfield", "grand prairie", "burleson", "haslet", "north richland hills", "hurst", "euless",
          "bedford", "grapevine", "weatherford", "benbrook", "white settlement", "saginaw", "crowley", "azle", "colleyville",
          "watauga", "forest hill", "river oaks", "lake worth", "aledo", "roanoke", "trophy club", "westlake", "denton county",
          "parker county", "johnson county", "dallas county", "u.s.", "america", "united states",
          "south central texas", "central texas", "north central texas", "hill country", "coastal bend", "rio grande valley", "east texas",
          "west texas", "south texas", "southeast texas", "panhandle", "texas panhandle", "gulf coast", "big bend", "permian basin",
          "brazos valley", "deep east texas", "the valley", "the metroplex",
          "arkansas", "oklahoma", "louisiana", "new mexico", "kansas", "missouri", "california", "florida", "georgia", "alabama",
          "tennessee", "mississippi", "colorado", "arizona", "nevada", "new york", "ohio", "michigan", "illinois", "utah", "oregon",
          "washington", "nebraska", "iowa", "kentucky", "carolina", "south carolina", "north carolina", "virginia", "indiana",
          "wisconsin", "minnesota", "pennsylvania", "maryland", "massachusetts", "hawaii", "alaska", "idaho", "montana", "wyoming",
          "dakota", "north dakota", "south dakota", "vermont", "maine", "connecticut", "delaware", "new jersey", "rhode island",
          "west virginia", "new hampshire", "mexico", "canada") + OTHER_CITIES
# capitalised words that start headlines without naming anything
STOP = {"no", "the", "a", "an", "in", "on", "at", "for", "with", "after", "before", "as", "and", "but", "or", "to", "from", "by",
        "of", "over", "under", "near", "amid", "despite", "here", "what", "when", "how", "why", "who", "this", "these", "those",
        "it", "its", "breaking", "developing", "update", "live", "watch", "video", "photos", "new", "one", "two", "three", "four",
        "five", "six", "ten", "several", "thousands", "hundreds", "dozens", "police", "city", "county", "state", "man", "woman",
        "teen", "boy", "girl", "family", "judge", "jury", "voters", "report", "study", "officials", "residents", "drivers",
        "cold", "warming", "heavy", "rain", "snow", "ice", "largest", "biggest", "first", "last", "local", "national", "week",
        "weekend", "today", "tonight", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
        "thanksgiving", "christmas", "halloween", "good", "morning", "happy", "big", "major", "massive", "more", "most", "less",
        "another", "some", "many", "our", "your", "their", "his", "her", "we", "you", "they", "is", "are", "was", "were", "will",
        "can", "could", "should", "would", "has", "have", "had", "not", "downtown", "weather", "traffic", "crime", "sports", "business", "news", "things", "best", "worst", "free", "crash",
        "fire", "shooting", "storm", "storms", "tornado", "hail", "flood", "freeze", "heat", "power", "outage", "gas", "home",
        "homes", "house", "school", "schools", "students", "teachers", "parents", "kids", "children", "people", "person",
        "suspect", "wanted", "arrest", "arrested", "deadly", "fatal", "injured", "dead", "killed", "democrats", "democrat",
        "republicans", "republican", "texans", "fort worthians", "residents", "voters", "lawmakers",
        "mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
        "sep", "sept", "oct", "nov", "dec", "pm", "am", "live"}
ACRONYM_STOP = {"ipo", "ceo", "cfo", "gop", "tv", "us", "usa", "am", "pm", "ai", "isd", "nws", "dps", "fbi", "nfl", "nba", "mlb",
                "nhl", "mls", "ncaa", "pd", "id", "dna", "gta", "ps5", "hq", "atm", "gps", "tx", "i-30", "i-20", "i-35w", "i-820"}

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9.&'’-]*")


@dataclass
class SubjectPlan:
    primary: str | None                     # the first named subject in the headline, if any
    entities: list[str] = field(default_factory=list)
    entity_topics: list[str] = field(default_factory=list)   # library topics that depict a named subject
    fallback_topics: list[str] = field(default_factory=list) # beat topics acceptable for an institution in the headline
    mode: str = "beat"                      # entity | institution | search | beat

    @property
    def search_names(self) -> list[str]:
        return [e for e in self.entities if not _is_place(e)]


def _clean(tok: str) -> str:
    return re.sub(r"(?:'s|’s|'|’)$", "", tok).strip(".,:;!?\"'’“”()")


def _is_place(entity: str) -> bool:
    low = entity.lower()
    return low in PLACES or low.endswith(" county")


def _elsewhere(entity: str) -> bool:
    low = entity.lower()
    return any(c in low for c in OTHER_CITIES) and "fort worth" not in low


_KNOWN: set[str] = {p for phrases, topic in TOPIC_RULES if topic in ENTITY_TOPICS for p in phrases if p.strip()}


def _known_subject(low: str) -> bool:
    """'Cowboys ...' at the start of a headline names the team even when nothing else repeats it."""
    return any(low == p.strip() or (len(low) > 3 and (low in p or p in low)) for p in _KNOWN)


def _capitalised(tok: str) -> bool:
    return bool(tok) and tok[0].isupper()


# capitalised adjectives of politics and place are never a photo subject: "some Congressional seats" found an unnamed
# congressman's official portrait for a story about Ted Cruz (Nov 22, render 108)
ADJECTIVES = {"congressional", "republican", "republicans", "democrat", "democrats", "democratic", "gop", "federal", "statewide",
              "legislative", "presidential", "gubernatorial", "conservative", "liberal", "progressive", "bipartisan", "partisan",
              "american", "midterm", "midterms", "election", "elections", "primary", "runoff", "senate", "senators", "lawmakers",
              # nationalities describe a subject, they never are one ("Molly Meldrum, Australian Music Broadcaster")
              "australian", "british", "canadian", "mexican", "english", "irish", "scottish", "welsh", "french", "german", "italian",
              "spanish", "japanese", "korean", "chinese", "indian", "russian", "ukrainian", "israeli", "brazilian", "european"}
COMMON_NOUNS = {"theater", "theatre", "theaters", "performances", "performance", "market", "markets", "festival", "festivals", "concert",
                "concerts", "weekend", "holiday", "holidays", "parade", "show", "shows", "game", "games", "lights", "music", "food", "restaurant",
                "restaurants", "school", "schools", "police", "fire", "weather", "storm", "storms", "traffic", "shooting", "crash", "council",
                "city", "county", "court", "judge", "zoo", "park", "parks", "lake", "river", "airport", "stadium", "arena", "museum", "library",
                "church", "hospital", "bridge", "road", "highway", "street", "mall", "hotel", "bar", "club", "band", "team", "coach", "player",
                "fans", "kids", "students", "teachers", "voters", "residents", "families", "workers", "update", "updates", "video", "photos",
                "watch", "live", "breaking", "exclusive", "report", "news", "forecast", "birthday", "b-day", "christmas", "thanksgiving",
                "college", "football", "basketball", "baseball", "softball", "soccer", "hockey", "volleyball", "grades", "week", "stats",
                "notes", "season", "playoffs", "conference", "championship", "box office", "franchise", "sequel", "trailer",
                # apps are where a crime happened, not what a photo can show (Nov 22: "...soliciting 15-year-old on Snapchat" drew Snap Spectacles)
                "snapchat", "instagram", "tiktok", "facebook", "youtube", "discord", "roblox", "whatsapp", "telegram", "reddit",
                "twitter", "kik", "grindr", "tinder", "app", "apps"}


HONORS = ("hall of fame", "ring of fame", "walk of fame", "hall of honor", "ring of honor", "honor roll")
_DEATH_RE = re.compile(r"\b(dies|died|dead at|passes away|passed away|obituary|remembered|mourns?|funeral|memorial service)\b", re.I)

_QUOTED_RE = re.compile(r"[‘“\"]([^’”\"]{3,80})[’”\"]|(?<![\w])'([^']{3,80})'(?![\w])")


# names that begin with a number word, which the run builder would otherwise strip as "Two Fort Worth men" (Nov 22:
# "'Holiday in the Park' kicks off at Six Flags Over Texas" searched for "Flags Over Texas")
# adjectives and numbers that open names when they sit mid-headline ("at Big Bear's Smokehouse", "at First Baptist")
NAME_LEADERS = {"big", "six", "five", "four", "three", "two", "one", "ten", "first", "good", "happy", "new", "major", "best",
                "free", "last", "local", "national", "little", "grand", "great", "old"}
NUMBER_NAMES = ("six flags", "five guys", "four seasons", "three rivers", "one world", "two rivers", "seven seas", "ten mile",
                "one main", "first baptist", "first united", "first presbyterian", "first methodist")

# Title Case headlines (Variety, Deadline, IGN, team and city releases) capitalise every word, so a run of capitals is no
# longer a name: Nov 23, "Tyson Fury Reveals Schizophrenia Diagnosis in Netflix Documentary" read as one name, and the
# "Netflix" in it put a TV remote on a story about a boxer. The story text, written in sentence case, says which words are names.
_MINOR = {"a", "an", "the", "and", "or", "but", "nor", "of", "in", "on", "at", "to", "for", "by", "with", "from", "as", "vs",
          "vs.", "via", "per", "into", "onto", "off", "up", "out", "over", "is", "are", "be"}
# without story text, these words end a name in a Title Case headline
HEADLINE_VERBS = {
    "reveals", "revealed", "confirms", "confirmed", "announces", "announced", "says", "said", "talks", "joins", "joined", "sign",
    "signs", "signed", "wins", "won", "dies", "died", "drops", "dropped", "releases", "released", "shares", "shared", "opens",
    "opened", "teases", "teased", "sets", "gets", "got", "lands", "landed", "makes", "takes", "leaves", "exits", "returns",
    "returned", "launches", "launched", "debuts", "debuted", "slams", "slammed", "responds", "addresses", "denies", "denied",
    "files", "filed", "sues", "sued", "settles", "settled", "celebrates", "honors", "honored", "unveils", "unveiled", "books",
    "booked", "cancels", "canceled", "cancelled", "renews", "renewed", "hires", "hired", "fires", "fired", "names", "named",
    "taps", "tapped", "picks", "picked", "plays", "played", "performs", "performed", "tops", "topped", "hits", "breaks",
    "explains", "details", "recalls", "remembers", "admits", "apologizes", "calls", "called", "criticizes", "defends", "praises",
    "thanks", "welcomes", "mourns", "pays", "gives", "wants", "plans", "hosts", "hosted", "headlines", "leads", "nabs", "scores",
    "scored", "earns", "earned", "receives", "received", "accepts", "rejects", "rejected", "splits", "marries", "weds", "falls",
    "fell", "beats", "defeats", "defeated", "loses", "lost", "edges", "routs", "clinches", "clinched", "advances", "approves",
    "approved", "votes", "voted", "passes", "passed", "delays", "delayed", "postpones", "postponed", "expands", "closes",
    "closed", "reopens", "reopened", "arrested", "charged", "sentenced", "indicted", "accused", "killed", "injured",
    "hospitalized", "plows", "slays", "soars", "surges", "sinks", "tumbles", "rises", "jumps", "climbs", "nears", "reaches",
    "eyes", "mulls", "weighs", "seeks", "faces", "inks", "extends", "agrees", "trades", "traded", "waives", "waived", "cuts",
    "activates", "promotes", "brings", "adds", "added", "enters", "retires", "retired", "resigns", "resigned", "sparks", "draws",
    "raises", "raised", "hikes", "hiked", "lowers", "lowered", "increases", "increased", "slashes", "slashed", "ends", "ended",
    "begins", "starts", "started", "unveil", "reveal", "announce", "confirm", "set", "gets", "goes", "comes", "becomes",
    "has", "have", "had", "was", "were", "will", "could", "would", "may", "might", "can", "should", "his", "her", "their", "its",
    "our", "your", "my", "he", "she", "they", "we", "you", "it", "this", "that", "these", "those", "after", "before", "amid",
    "despite", "during", "about", "against", "without", "than", "when", "why", "how", "what", "who"}


def _title_case(tokens: list[str]) -> bool:
    words = [t for t in tokens if t != "|" and len(_clean(t)) >= 2 and _clean(t).lower() not in _MINOR]
    return len(words) >= 4 and sum(1 for t in words if _capitalised(t)) >= 0.9 * len(words)


def _known_spans(tokens: list[str]) -> set[int]:
    """Positions of tokens that spell a known place or library subject ("Utah", "Wichita Falls", "Dickies Arena"): those are
    names however the story text writes them."""
    lows = [_clean(t).lower() for t in tokens]
    known = set(PLACES) | {p.strip() for p in _KNOWN}
    keep: set[int] = set()
    for start in range(len(tokens)):
        for size in (4, 3, 2, 1):
            span = lows[start:start + size]
            if len(span) == size and "|" not in span and " ".join(span) in known:
                keep.update(range(start, start + size))
                break
    return keep


def _sentence_case(tokens: list[str], title: str, body: str) -> tuple[list[str], set[str]]:
    """A Title Case headline rewritten the way the story text writes it: words the text never capitalises are lowered, so
    they end a run. Acronyms, places and library subjects stay ("TCU Falls to Utah" -> "TCU", "Utah"). With no text to go
    by, a headline verb ends the name and what follows it is dropped: the object of a Title Case headline is more often
    "Schizophrenia Diagnosis" than a name. Returns the tokens and the words the text writes as names."""
    text = (body or "").replace(title or "", " ")           # a summary that repeats the headline proves nothing
    words = _TOKEN.findall(text)
    shouting = sum(1 for t in tokens if t != "|" and _clean(t).isupper()) >= 0.8 * max(1, sum(1 for t in tokens if t != "|"))
    known = _known_spans(tokens)
    out: list[str] = []
    if len(words) >= 8 and any(ch.isupper() for ch in text):    # a lowercased text says nothing about capitals
        caps, lower = set(), set()
        for w in words:
            (caps if w[0].isupper() else lower).add(_clean(w).lower())
        mid = {_clean(m.group(1)).lower() for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][A-Za-z0-9&'’.-]+)", text)}
        proper = mid | (caps - lower)
        for k, tok in enumerate(tokens):
            word = _clean(tok)
            keep = tok == "|" or not _capitalised(tok) or k in known or word.lower() in proper or (
                not shouting and len(word) >= 2 and word.isupper())
            out.append(tok if keep else tok.lower())
        return out, proper
    after_verb = False
    for k, tok in enumerate(tokens):
        low = _clean(tok).lower()
        if tok == "|":
            after_verb = False
            out.append(tok)
            continue
        verb = (low in HEADLINE_VERBS or low in _MINOR) and k not in known and k > 0 and tokens[k - 1] != "|"
        after_verb = after_verb or verb
        out.append(tok.lower() if (verb or after_verb) and k not in known else tok)
    return out, set()


def entities(title: str, body: str = "") -> list[str]:
    """Named subjects in a headline: runs of capitalised words, kept when they are more than one word, possessive, an
    acronym, or appear capitalised again mid-sentence in the body (so 'Largest enrollment drop' names nothing, while
    'Anthropic's IPO' and 'Northwest ISD' do). Places are returned too; callers decide what to do with them."""
    tokens: list[str] = []
    headline = title or ""
    quoted = [(a or b).strip() for a, b in _QUOTED_RE.findall(title or "") if len((a or b).strip().split()) >= 2]
    if quoted:                       # "'Hunger Games: Sunrise on the Reaping' Slays $120M": the work's title is one subject,
        title = _QUOTED_RE.sub(" | ", title or "")     # never its words (Nov 22: "Sunrise" found a sunrise over a mosque)
    for segment in re.split(r"[,;:|()\[\]\u2013\u2014]|\s-\s", title or ""):   # "Dickies Arena, Sun, Nov 22" is three segments
        seg = _TOKEN.findall(segment)
        if seg:
            tokens += seg + ["|"]
    body_mid = set()
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][A-Za-z0-9&'’.-]+)", body or ""):
        body_mid.add(_clean(m.group(1)).lower())
    if _title_case(tokens):
        tokens, proper = _sentence_case(tokens, headline, body)
        body_mid |= proper                    # "Netflix Raises Prices": a name the text writes as one may open the headline
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "|" or not _capitalised(tok) or _clean(tok).lower() in STOP and (i == 0 or tokens[i - 1] == "|") and not tok.endswith(("'s", "’s")):
            i += 1
            continue
        run = [tok]
        j = i + 1
        while j < len(tokens) and tokens[j] != "|" and (_capitalised(tokens[j]) or tokens[j].lower() in ("of", "&", "and") and j + 1 < len(tokens) and _capitalised(tokens[j + 1])):
            run.append(tokens[j])
            j += 1
        while run and run[-1].lower() in ("of", "&", "and"):
            run.pop()
        if j < len(tokens) and tokens[j].lower() in INSTITUTION_FALLBACK:    # "Fort Worth police", "Tarrant County jail"
            run.append(tokens[j])
            j += 1
        if (j < len(tokens) and _clean(tokens[j]).lower() in ATTRIBUTION
                and (j + 1 >= len(tokens) or tokens[j + 1] == "|")):            # "..., Morath says": a source, not the subject;
            i = max(j, i + 1)                                                 # "Hailee Steinfeld confirms she's in" is the subject
            continue
        words = [_clean(w) for w in run]
        words = [w for w in words if w]
        seg_start = i == 0 or tokens[i - 1] == "|"
        if (words and words[0].lower() in STOP and len(words) > 1 and not " ".join(words).lower().startswith(NUMBER_NAMES)
                and (seg_start or words[0].lower() not in NAME_LEADERS)):
            words = words[1:]                              # "Big crash on I-35W" -> no "Big"; "at Big Bear's Smokehouse" keeps it
        phrase = " ".join(words)
        low = phrase.lower()
        possessive = any(w.endswith(("'s", "’s")) for w in run)
        acronym = len(words) == 1 and words[0].isupper() and len(words[0]) >= 2 and low not in ACRONYM_STOP
        if re.match(r"^(prop|proposition|measure|amendment|item|district|precinct|zone|lot|phase|section)\b\.? ?[a-z0-9]{0,4}$", low):
            i = max(j, i + 1)                              # "Prop J", "District 61", "Phase 2": a label, never a picture subject
            continue
        if len(low.replace(" ", "")) < 2:
            i = max(j, i + 1)                              # "Indiana gets 'D'": a letter grade is never a subject
            continue
        if any(h in low for h in HONORS):
            i = max(j, i + 1)                              # "Hall of Fame broadcaster Tom Jackson": an honor, not a subject (Nov 22:
            continue                                       # "Hall of Fame" found another man at a hall of fame induction)
        keep = bool(words) and low not in STOP and low not in ACRONYM_STOP and low not in COMMON_NOUNS and low not in ADJECTIVES and (
            len(words) > 1 or possessive or acronym or low in body_mid or _known_subject(low) or not seg_start and low not in STOP)
        # a lone capitalised word that opens a segment ("Made in Tarrant: Gobble up barbecue ...") is capitalised for the
        # colon, not because it names anything (Nov 22: "Gobble" was searched for a barbecue restaurant story)
        if keep and phrase not in out:
            out.append(phrase)
        i = max(j, i + 1)
    return out


def entity_topics_for(names: list[str], category: str, title: str | None = None, body: str = "") -> list[str]:
    """Library topics that depict the named subjects, specific sports grounds first for sports stories.
    A team's name reaches its stadium only for a game there (library.venue_fits): Nov 21, "Dallas Cowboys mark 30 years
    of giving back with Salvation Army" (meals served in Dallas and Fort Worth) drew AT&T Stadium during a Wisconsin bowl game."""
    out: list[str] = []
    for name in names:
        low = " " + name.lower() + " "
        nickname = low.strip() in TEAM_FULL_NAMES      # "Mavericks" alone is not "uta mavericks": only a phrase inside the name counts
        whole = re.compile(r"(?<![\w&])" + re.escape(low.strip()) + r"(?![\w&])") if low.strip() else None
        for phrases, topic in TOPIC_RULES:
            # a name inside a longer phrase counts only as whole words: "D" (a letter grade) sits inside "dickies arena"
            if topic not in ENTITY_TOPICS or not any(p.strip() and (p in low or (not nickname and whole and whole.search(p))) for p in phrases):
                continue
            if _elsewhere(name) and topic in FORT_WORTH_ONLY:        # Dallas City Hall is not Fort Worth City Hall
                continue
            if title is not None and not venue_fits(topic, f"{title} {body}", title):
                continue
            if topic_excluded(topic, f"{name} {title or ''} {body}"):
                continue                                   # "Baylor University Medical Center" is a Dallas hospital, not the Waco campus
            if category == "sports" and topic in SPORTS_VARIANTS and SPORTS_VARIANTS[topic] not in out:
                out.append(SPORTS_VARIANTS[topic])
            if topic not in out:
                out.append(topic)
    return out


_TITLED_RE = re.compile(r"^(?:U\.S\. )?(?:Sen\.|Senator|Rep\.|Representative|Gov\.|Governor|Lt\. Gov\.|Mayor|President|Judge|"
                        r"Commissioner|Councilmember|Councilwoman|Councilman|Chief|Coach|Dr\.|Sheriff|Superintendent|Pastor|Officer)\s+"
                        r"([A-Z][\w'’-]+)$")


def resolve_titled(name: str, body: str) -> str | None:
    """'Senator Cruz' -> 'Ted Cruz' from the story's own text; None when the text never gives the first name (a bare
    surname finds strangers, and no file is named 'Senator Cruz')."""
    m = _TITLED_RE.match(name.strip())
    if not m:
        return name
    surname = m.group(1)
    for first in re.findall(r"\b([A-Z][a-z]+(?: [A-Z]\.)?) " + re.escape(surname) + r"\b", body or ""):
        if not _TITLED_RE.match(f"{first} {surname}") and first.lower() not in STOP and first.lower() not in ADJECTIVES:
            return f"{first} {surname}"
    return None


_LIGHT_SHOW_RE = re.compile(r"\b(?:christmas in the garden|light trail|lights? (?:show|display|festival|trail|walk|drive)|holiday lights|"
                            r"christmas lights|light installations?|luminarias?|illuminat\w+|lantern festival|winter wonderland|"
                            r"parade of lights|trail of lights|festival of lights|zoo lights|enchant)\b", re.I)
LIGHT_WORDS = "light|lights|christmas|holiday|lantern|lanterns|luminaria|illumination|illuminations|night"


def light_show(title: str) -> bool:
    """'Christmas in the Garden returns to Fort Worth Botanic Garden': a holiday light show is seen at night; a daytime
    photo of the venue is a stand-in (Nov 23)."""
    return bool(_LIGHT_SHOW_RE.search(title or ""))


def _institution_words(name: str) -> list[str]:
    return [w for w in name.lower().replace("-", " ").split() if w in INSTITUTION_FALLBACK]


def plan_subject(title: str, body: str, category: str) -> SubjectPlan:
    names = [n for n in (resolve_titled(x, body) for x in entities(title, body)) if n]
    subjects = [n for n in names if not _is_place(n)]
    if _DEATH_RE.search(title or "") and any(looks_like_person(n) for n in subjects):
        subjects = [n for n in subjects if looks_like_person(n)]   # a death is about the person: no team, venue or honor photo
    topics = entity_topics_for(subjects, category, title, body)
    if light_show(title):
        topics = []                  # the garden by day is not the light trail (Nov 23: Christmas in the Garden, Oct 2019 arbors)
    plan = SubjectPlan(primary=subjects[0] if subjects else None, entities=names, entity_topics=topics)
    if topics:
        plan.mode = "entity"
        return plan
    if not subjects:
        plan.mode = "beat"
        return plan
    fallback: list[str] = []
    pool = subjects
    if looks_like_person(subjects[0]) and not _institution_words(subjects[0]):
        # a person's story: a platform or agency named later is where it happened, not who it is about (Nov 23: "Tyson Fury
        # reveals schizophrenia diagnosis in Netflix documentary" went out with a TV remote from the streaming topic)
        pool = []
    for name in pool:
        for word in _institution_words(name):
            fallback += [t for t in INSTITUTION_FALLBACK[word] if t not in fallback]
    plan.fallback_topics = fallback
    plan.mode = "institution" if fallback else "search"
    return plan


WEATHER_KINDS = ("nws_alert", "nws_forecast")


def subject_fits(title: str, body: str, category: str, subject: str | None, kind: str = "") -> tuple[bool, str]:
    """The pre-publish check: the subject a photo was chosen for must still be what the headline is about."""
    if not subject:
        return False, "no subject was recorded for the photo"
    plan = plan_subject(title, body, category)
    if kind in WEATHER_KINDS or category == "weather" and plan.mode == "beat":
        plan.mode = "beat"                       # weather pictures follow the conditions (images/subject.py: weather_topics)
        low = subject.lower()
        _, _, topic = low.partition(":")
        named = {t for _, topics in WEATHER_TOPICS for t in topics}
        if low.startswith("beat:") and topic in named and topic not in weather_topics(f"{title} {body}"):
            return False, f"a {topic} photo does not show these conditions"   # Nov 23: a freeze drew the 2021 snowstorm
    low = subject.lower()
    kind, _, value = low.partition(":")
    if kind == "entity":
        return (value in title.lower(), f"headline no longer names {value!r}") if value else (False, "empty entity")
    if kind == "topic":
        ok = value in plan.entity_topics or value in plan.fallback_topics
        return ok, "" if ok else f"topic {value!r} does not depict {plan.primary!r}"
    if kind == "beat":
        ok = plan.mode == "beat" or value in plan.fallback_topics
        return ok, "" if ok else f"a beat photo ({value}) cannot stand in for {plan.primary!r}"
    if kind == "own":
        return True, ""
    return False, f"unknown subject record {subject!r}"


WEATHER_TOPICS = (
    # snow and ice come before storms ("Ice Storm Warning" is not a thunderstorm) and before a dry freeze
    (("ice storm", "sleet", "freezing rain", "freezing drizzle", "winter storm", "winter weather", "snow", "wintry"), ["ice", "skyline"]),
    (("tornado", "severe", "thunderstorm", "hail", "storms", "storm", "lightning", "flash flood", "flood"), ["storm"]),
    # Nov 23: a Freeze Warning (frost, lows near 27) drew the February 2021 snowstorm: a dry freeze is not snow
    (("freeze", "freezing", "frost", "wind chill", "sub-freezing"), ["frost", "clouds", "skyline"]),
    (("heat advisory", "excessive heat", "triple digit", "100 degrees", "hot ", "heat"), ["heat", "skyline"]),
    (("rain", "showers", "drizzle", "wet"), ["rain", "storm", "skyline"]),
    (("partly cloudy", "partly sunny", "mostly sunny"), ["sunshine", "skyline"]),
    # Nov 22: "mostly cloudy, high near 61" drew a blue-sky skyline; the gray courthouse photo was filed under sunshine
    (("fog", "cloudy", "overcast", "gray", "clouds"), ["clouds", "skyline"]),
    (("sunny", "clear", "pleasant", "mild", "warm", "nice"), ["sunshine", "skyline", "sundance-square", "downtown"]),
)


RADAR_EVENTS = ("tornado", "thunderstorm", "flood", "winter storm", "winter weather", "ice storm", "snow", "sleet", "freezing rain",
                "blizzard", "hail", "rain", "storm", "tropical", "hurricane", "squall")


def radar_fits(event: str) -> bool:
    """A radar map shows rain, storms and snow. A freeze, heat, wind or fog alert has nothing on it: Nov 23, a Freeze Warning
    for Tarrant and 20 other counties drafted with an empty radar map under a tornado and thunderstorm legend."""
    low = (event or "").lower()
    return any(w in low for w in RADAR_EVENTS)


def weather_topics(text: str) -> list[str]:
    """Library topics for a forecast or weather story, by the conditions it describes: a sunny 65-degree day is shown
    with a bright skyline, never with a supercell."""
    low = (text or "").lower()
    for words, topics in WEATHER_TOPICS:
        if any(w in low for w in words):
            return topics
    return ["skyline", "downtown"]


VENUE_WORDS = ("arena", "stadium", "field", "center", "centre", "hall", "theater", "theatre", "coliseum", "ballpark", "speedway",
               "amphitheater", "amphitheatre", "pavilion", "convention", "museum", "zoo", "garden", "park", "plaza", "square")
PERFORMANCE_WORDS = ("concert", "live", "performing", "performs", "tour", "festival", "show", "gig", "on stage", "onstage", "k-pop",
                     "kpop", "band", "singer", "rapper", "dj ", "fans", "crowd", "halftime", "vs", "game", "match")


ORG_WORDS = ("isd", "inc", "llc", "corp", "company", "university", "college", "school", "district", "department", "police", "county",
             "city", "council", "foundation", "church", "hospital", "bank", "airlines", "group", "association", "club", "team", "fc",
             "cowboys", "rangers", "mavericks", "stars", "frogs", "mavs", "wings", "texans", "astros", "rockets", "spurs", "tcu", "uta",
             "smu", "unt", "baylor", "tech", "aggies", "longhorns") + VENUE_WORDS


TEAM_WORDS = ("cowboys", "rangers", "mavericks", "stars", "frogs", "mavs", "wings", "texans", "astros", "rockets", "spurs", "aggies",
              "longhorns", "mustangs", "mean green", "red raiders", "bears", "cougars", "clippers", "timbers", "fc", "team")

# a nickname alone names many things (OS X Mavericks, hair clippers, the UTA Mavericks): sports searches use the full name
TEAM_FULL_NAMES = {"mavericks": "Dallas Mavericks", "mavs": "Dallas Mavericks", "cowboys": "Dallas Cowboys", "stars": "Dallas Stars",
                   "rangers": "Texas Rangers", "wings": "Dallas Wings", "texans": "Houston Texans", "astros": "Houston Astros",
                   "rockets": "Houston Rockets", "spurs": "San Antonio Spurs", "horned frogs": "TCU Horned Frogs", "frogs": "TCU Horned Frogs",
                   "longhorns": "Texas Longhorns", "aggies": "Texas A&M Aggies", "mean green": "North Texas Mean Green",
                   "mustangs": "SMU Mustangs", "red raiders": "Texas Tech Red Raiders"}


def photo_age_bar(label: str, stamp, years: int = 3) -> str:
    """A team or a person changes: a photo older than `years` (or undated) is not a picture of them today. Buildings, venues
    and institutions keep their file photos. Returns the earliest acceptable 'taken' date (ISO) or '' for no bar.
    Team names used to count as institutions (they sit in ORG_WORDS so "Dallas Cowboys" is not read as a person): a 2010
    Tony Romo wallpaper passed for a 2026 Cowboys story."""
    if not label.startswith("entity:"):
        return ""
    name = label.split(":", 1)[1]
    low = f" {name.lower()} "
    team = any(f" {w} " in low for w in TEAM_WORDS)
    if is_venue(name) or (not team and any(w in name.lower().split() for w in ORG_WORDS)):
        return ""
    from datetime import timedelta
    return (stamp - timedelta(days=365 * years)).date().isoformat()


def looks_like_person(name: str) -> bool:
    """Two or three capitalised words with no organisation or venue word: Ty Myers, Cooper Flagg, Bo French."""
    words = name.split()
    low = name.lower()
    return 2 <= len(words) <= 3 and not any(w in low.split() or low.endswith(" " + w) for w in ORG_WORDS) and not any(ch.isdigit() for ch in name)


def is_venue(name: str) -> bool:
    low = name.lower()
    return any(w in low.split() or low.endswith(" " + w) for w in VENUE_WORDS)


HAPPENED_WORDS = ("carted off", "carted", "injured", "injury", "hurt in", "scores ", "scored", " beat ", " beats ", " wins ", " won ", " loses ",
                  " lost ", "defeats", "defeated", "rallies", "rallied", "clinches", "clinched", "stuns", "stunned", "upsets", "suffers", "tears ",
                  " tore ", "ruled out", "ejected", "hospitalized", "sets record", "snaps ", " rout", "blowout", "comeback", "walk-off",
                  "overtime", "final:", "recap", "takeaways", "highlights", "crash", "collision", "wreck", " shot ", "shooting", "stabbed",
                  "collapsed", "caught fire", "burned", "burns ", "house fire", "apartment fire", "structure fire", "home fire",
                  "grass fire", "brush fire", "wildfire", "blaze", "flames", "fire breaks out", "fire destroys", "fire damages",
                  "battle fire", "battle large", "battling", "explosion", "flooded", "flooding", "tornado", "hail ", "evacuated",
                  # Nov 23: KVUE's "Mexico demands SpaceX clean up suspected rocket debris washing ashore near Texas" drew a
                  # SpaceX hangar at Kennedy Space Center
                  " debris", "washing ashore", "washed ashore", "washes ashore", "washing up", "washed up", "washes up",
                  "rescued", "pulled from", " dies ", " died ", "killed", " dead ", "arrested", "charged with", "indicted", "sentenced",
                  " fired", "resigns", "resigned", "steps down", "walks out", "protest", "ceremony", "ribbon", "reopens", "debut",
                  "convicted", "found guilty", "pleads guilty", "pleaded guilty", "acquitted", "verdict", "sentenced to", "raided",
                  # game results (Nov 22: "TCU Falls to Utah in Home Finale" went out with an empty Amon G. Carter Stadium from 2017)
                  " falls to ", " fall to ", " falls in ", " fell to ", " drops ", " dropped ", " edges ", " edged ", " tops ", " topped ",
                  " routs ", " routed ", " blanks ", " blanked ", "shut out", "shuts out", "came up short", "comes up short", "holds off",
                  "held off", "survives", "outlasts", "outlasted", "upended", "upends", "pushes past", "pulls away", "eliminated",
                  " sweeps ", " swept ", " advance", "falls short", "fell short",
                  # a plural team takes the base verb: "Mavericks top the Clippers", "Stars edge Blues", "Rangers drop series finale"
                  " top the ", " edge ", " drop ", "come up short", " blank ", " sweep ", " outlast ", "blow out", "blows out", "blew out",
                  " roll past", " rolls past", " cruise past", " cruises past", " win over ", " victory over ", " seals ", " sealed ",
                  " beating ", " clinching ", " loss to ", " loss at ", " losses to ", "muscles past", "slips past", "pulls past",
                  "holds on", "hangs on", "knocks off", "outduels", "takes down", "falls at ", " fall at ",
                  # personnel moves (Nov 22: "TCU fires Sonny Dykes" drew an empty Amon G. Carter Stadium)
                  " fires ", "part ways", "parts ways", " dismiss ", "dismisses", "dismissed", " let go", "relieved of", "ousts", "ousted",
                  # Nov 23: "Texas Tech moves closer ... with win at Baylor" drew Jones AT&T Stadium (2013), and "TCU interim HC
                  # Andy Avalos introduced ahead of regular-season finale" drew an empty Amon G. Carter Stadium
                  " win at ", " win against ", "with win", "with a win", " loss at ", " loss against ", " road win", " home win",
                  " introduced", " introduces", "named interim", "names interim", " hires ", " hired ", "promoted to", "takes over as")


def happened(title: str, kind: str = "rss") -> bool:
    """A story about something that already happened and was seen (a play, a crash, a fire, a ceremony, an arrest):
    its picture must be of that happening, or the outlet's own photo in a link preview; a file photo of the stadium or
    the highway is a stand-in, and the page's owner does not want stand-ins. Official sources (police bulletins, weather,
    events, the calendar, viewer clips) bring their own pictures and are not affected."""
    if kind not in ("rss", "video"):
        return False
    low = f" {(title or '').lower()} "
    hits = [w for w in HAPPENED_WORDS if w in low]
    if not hits:
        return bool(_NAMED_TO_ROLE_RE.search(low))   # "Texas A&M names Thornton interim athletic director" drew Kyle Field (Nov 23)
    if all(w in PERSONNEL_WORDS for w in hits) and not _ROLE_RE.search(low):
        return False                  # "Fort Worth introduces new recycling carts" is a program, not a person taking a job
    hits = [w for w in hits if w not in PERSONNEL_WORDS] or hits
    if all(w in SPORTS_ONLY_RESULT_WORDS for w in hits) and not _SPORTS_CUE_RE.search(low) and \
            not any(f" {t} " in low or f" {t}'" in low for t in TEAM_WORDS if t not in _PLAIN_TEAM_WORDS):
        return False                  # "Gas prices drop ahead of Thanksgiving": a price is not a play (Nov 22)
    return True


_NAMED_TO_ROLE_RE = re.compile(r"\b(?:names?|named|appoints?|appointed|taps|tapped|tabs|tabbed)\b[^.]{0,40}?\b(?:interim |acting |new )?"
                               r"(?:head coach|coach|athletic director|coordinator|police chief|fire chief|chief|superintendent|"
                               r"president|ceo|director|manager|chancellor|provost|dean|principal|commissioner)\b")
# a job changing hands is a happening only for a person in a role: "TCU interim HC Andy Avalos introduced", "Fort Worth hires
# new police chief"; "Fort Worth introduces new recycling carts" is a program
PERSONNEL_WORDS = {" introduced", " introduces", "named interim", "names interim", " hires ", " hired ", "promoted to", "takes over as"}
_ROLE_RE = re.compile(r"\b(?:coach|hc|coordinator|chief|superintendent|manager|ceo|president|director|athletic director|ad|"
                      r"quarterback|qb|pastor|principal|commissioner|chancellor|provost|dean)\b")


# result verbs that mean a game only when the headline is about sports: "Gas prices drop", "Fort Worth wins grant",
# "Texas tops list" are not things that happened in front of a camera
SPORTS_ONLY_RESULT_WORDS = {" beat ", " beats ", " wins ", " won ", " loses ", " lost ", " falls to ", " fall to ", " falls in ",
                            " fell to ", " drops ", " dropped ", " edges ", " edged ", " tops ", " topped ", " top the ", " edge ",
                            " drop ", " blank ", " sweep ", " outlast ", " win at ", " win against ", "with win", "with a win",
                            " loss at ", " loss against ", " road win", " home win"}
_PLAIN_TEAM_WORDS = {"texans", "stars", "bears", "cougars", "mustangs", "wings", "team", "fc"}   # "fewer Texans are hitting the road"
_SPORTS_CUE_RE = re.compile(r"\b(?:tcu|smu|unt|uta|baylor|texas tech|texas a&m|byu|ucf|lsu|usc|ucla|notre dame|ohio state|penn state|"
                            r"home finale|senior day|shootout|power play|hat trick|home runs?|homers?|series|"
                            r"game|games|season|playoffs?|coach|quarterback|qb|touchdowns?|tds?|innings?|overtime|halftime|"
                            r"match|tournament|title|championship|bowl|league|conference|nfl|nba|mlb|nhl|mls|ncaa|big 12|sec|"
                            r"no\. \d+|\d{1,3}-\d{1,3}|vs\.?|football|basketball|baseball|soccer|hockey|volleyball|softball)\b")


GENERIC_EVENT_WORDS = ("parade", "festival", "market", "fair", "show", "lights", "run", "race", "marathon", "gala", "expo", "fest",
                       "jubilee", "carnival", "rodeo", "powwow", "pow-wow", "tour", "walk", "ride")


def is_generic_event(name: str) -> bool:
    """'Parade of Lights', 'Christmas Market', 'Turkey Trot': names that many towns use, so a file carrying the name alone may
    show another town's event (Lake Mead has a Parade of Lights too)."""
    return any(w in name.lower().split() for w in GENERIC_EVENT_WORDS)


ANIMAL_WORDS = {"hippo": "hippo|hippopotamus|hippos", "giraffe": "giraffe|giraffes", "elephant": "elephant|elephants", "gorilla": "gorilla|gorillas",
                "tiger": "tiger|tigers", "lion": "lion|lions", "panda": "panda|pandas", "rhino": "rhino|rhinoceros|rhinos", "otter": "otter|otters",
                "penguin": "penguin|penguins", "zebra": "zebra|zebras", "flamingo": "flamingo|flamingos", "koala": "koala|koalas",
                "cheetah": "cheetah|cheetahs", "jaguar": "jaguar|jaguars", "bear": "bear|bears", "wolf": "wolf|wolves", "sloth": "sloth|sloths",
                "okapi": "okapi", "lemur": "lemur|lemurs", "alligator": "alligator|alligators", "longhorn": "longhorn|longhorns", "bison": "bison"}


def animal_in(title: str) -> str:
    """'San Antonio Zoo mourns Fiona, Timothy the hippo's sweetheart' -> 'hippo|hippopotamus|hippos': a zoo story's picture
    must show the animal the headline is about, not an inspection of an ocelot in the same zoo."""
    words = re.findall(r"[a-z]+", (title or "").lower())
    for w in words:
        if w in ANIMAL_WORDS:
            return ANIMAL_WORDS[w]
        if w.endswith("s") and w[:-1] in ANIMAL_WORDS:
            return ANIMAL_WORDS[w[:-1]]
    return ""


BRAND_POSSESSIVE_VERBS = {"closes", "opens", "announces", "says", "plans", "brings", "adds", "cuts", "debuts", "expands", "launches", "files", "sues",
                          "names", "hires", "is", "are", "will", "has", "to", "set", "sets", "shuts", "shutters", "comes", "coming", "opening", "closing",
                          "recalls", "offers", "drops", "raises", "lays", "eyes", "unveils", "wants", "gets", "returns", "arrives", "lands"}


# a school or a place named in a sports headline is the team: "Notre Dame" found the Paris cathedral (Nov 21, render 107)
SPORT_CONTEXT = ("football|basketball|baseball|softball|soccer|hockey|volleyball|athletics|stadium|arena|ballpark|field|court|team|"
                 "players|player|quarterback|coach|fighting irish|mustangs|horned frogs|longhorns|aggies|bears|cougars|mean green|"
                 "red raiders|mavericks|cowboys|rangers|wings|texans|astros|rockets|spurs|stars")
# a sculpture, a plaque or a mural of an organisation is not its news: a Salvation Army memorial relief for a meal service
ART_WORDS = ("sculpture", "statue", "relief", "plaque", "memorial", "monument", "bust", "mural", "painting", "drawing", "engraving",
             "stained glass", "headstone", "grave")


_GENERIC_CONTEXT = {"winners", "winner", "after", "before", "about", "their", "there", "these", "those", "where", "which", "while",
                    "years", "first", "since", "under", "other", "today", "night", "season", "video", "photos", "watch", "update",
                    "report", "could", "would", "should", "still", "again", "every", "never", "always", "people"}


def _context_words(title: str, name: str) -> list[str]:
    """The headline's other distinctive words ("awards", "artist", "jelly"), singular and plural, that a photo of a bare
    acronym must also carry: CMA is the Country Music Association and a Volvo car platform."""
    out: list[str] = []
    for w in re.findall(r"[a-z]+", (title or "").lower()):
        if len(w) < 5 or w == name.lower() or w in STOP or w in _GENERIC_CONTEXT or w in PLACES:
            continue
        for form in (w, w[:-1] if w.endswith("s") else f"{w}s"):
            if form not in out:
                out.append(form)
    return out


def provider_queries(plan: SubjectPlan, title: str, category: str, *, people_allowed: bool = False, city: str = "") -> list[tuple[tuple, str]]:
    """(query tuple, subject label) pairs for the search providers, one named subject at a time.

    A venue is searched for as a building (its Commons category, then "exterior"/"building"), never as somebody else's
    show inside it: a K-pop night at Dickies Arena is not a picture of Sunday's basketball showcase. Any other subject
    (a company, a team, a person) must appear in the file name or title, newest uploads first, and photos of concerts or
    games are skipped unless the story itself is that concert or game."""
    low_title = (title or "").lower()
    performer_story = category in ("events", "culture") or any(w in low_title for w in ("concert", "tour", "live", "festival", "show"))
    out: list[tuple[tuple, str]] = []
    for name in plan.search_names[:3]:
        if category == "sports" and len(name.split()) <= 2 and name.lower() in TEAM_FULL_NAMES:
            name = TEAM_FULL_NAMES[name.lower()]        # "Mavericks" -> "Dallas Mavericks", never OS X Mavericks
        elif category == "sports" and len(name.split()) == 1 and not name.isupper():
            continue                                   # "Clippers", "Timbers": a bare nickname finds hair clippers and lumber
        words = (" ".join(name.lower().split()),)      # the whole name, in order: "Ty Myers" is not "Ty Cobb at Fort Myers"
        if len(name.split()) == 1:
            m = re.search(re.escape(name) + r"(?:'s|’s)\s+(\w+)", title or "", re.I)
            if m and m.group(1).lower() in BRAND_POSSESSIVE_VERBS:
                words = (f"{name.lower()}'s|{name.lower()}’s|{name.lower()}s",)   # "Portillo's closes": the chain, never a Coronel Pedro Portillo
        if city and is_generic_event(name) and city.lower() not in name.lower():
            words = words + (city.lower(),)             # a generic event name needs the city too: Lake Mead has a Parade of Lights
        animal = animal_in(title)
        if animal:
            words = words + (animal,)                   # a zoo story's picture shows the animal, not an inspection of another one
        if light_show(title):
            words = words + (LIGHT_WORDS,)              # a holiday light show takes a picture of the lights, never the venue by day
        if len(name.split()) == 1 and name.isupper() and len(name) <= 5 and not _known_subject(name.lower()):
            context = _context_words(title, name)
            if not context:
                continue                               # a bare acronym with nothing to check it against
            words = words + ("|".join(context),)       # Nov 23: "CMA" (the awards) found a Volvo XC40 built on Volvo's CMA platform
        label = f"entity:{name.lower()}"
        if looks_like_person(name) and not people_allowed:
            continue                                   # a stranger with the same name is the worst mistake a page can make
        if is_venue(name) and not animal:              # a zoo with an animal in the headline is searched for the animal, not the gate
            out += [((f"category:{name}", PERFORMANCE_WORDS, words), label),
                    ((f"{name} exterior", PERFORMANCE_WORDS, words), label),
                    ((f"{name} building", PERFORMANCE_WORDS, words), label),
                    ((f"fresh:{name}", PERFORMANCE_WORDS, words), label),
                    ((name, PERFORMANCE_WORDS, words), label)]
        else:
            avoid = () if performer_story else PERFORMANCE_WORDS
            avoid = avoid + tuple(w for w in ART_WORDS if w not in low_title)
            if not animal:
                avoid = avoid + ("inaturalist",)      # a species record: a "Texas Two-step Flasher" firefly for a lottery game (Nov 23)
            if category == "sports" and name not in TEAM_FULL_NAMES.values():
                words = words + (SPORT_CONTEXT,)          # "Notre Dame football", never Notre-Dame de Paris
            out += [((f"fresh:{name}", avoid, words), label), ((name, avoid, words), label)]
    return out


EVENT_WORDS = ("game", "concert", "tour", "festival", "parade", "ceremony", "opening", "ribbon", "rally", "protest", "march", "vigil",
               "funeral", "graduation", "fair", "rodeo", "race", "marathon", "tournament", "playoff", "championship", "showdown",
               "showcase", "bell", "ipo", "launch", "storm", "tornado", "flood", "fire", "crash", "wreck", "shooting")


def wants_recent_picture(title: str, category: str, kind: str = "") -> bool:
    """A story about something that happened wants a picture from that happening, not a file photo of the place."""
    low = (title or "").lower()
    return kind in ("event", "event_roundup", "nws_alert") or category in ("events", "sports", "breaking") or any(w in low for w in EVENT_WORDS)
