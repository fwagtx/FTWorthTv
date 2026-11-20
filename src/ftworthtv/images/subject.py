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

from .library import FORT_WORTH_ONLY, OTHER_CITIES, SPORTS_VARIANTS, TOPIC_RULES

# topics that depict one specific subject; everything else in TOPIC_RULES is a beat (police, storm, highway, skyline ...)
ENTITY_TOPICS = {
    "dickies-arena", "will-rogers", "att-stadium", "globe-life-field", "stars-ice", "aac", "toyota-stadium", "texas-motor-speedway",
    "tcu-football", "tcu", "uta", "nrg-stadium", "daikin-park", "toyota-center", "frost-bank-center", "ut-austin", "texas-am",
    "texas-tech", "baylor", "smu", "unt", "keller-isd", "northwest-isd", "transit", "courthouse", "sundance-square", "stockyards",
    "kimbell", "modern", "bass-hall", "zoo", "botanic-garden", "water-gardens", "convention-center", "dfw-airport", "alliance",
    "trinity-river", "heb", "bucees", "whataburger", "capitol", "city-hall", "anthropic",
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
    "netflix": ["streaming"], "hbo": ["streaming"], "disney+": ["streaming"], "hulu": ["streaming"],
}
ATTRIBUTION = ("says", "said", "tells", "told", "warns", "warned", "announces", "announced", "reports", "reported", "confirms")
PLACES = ("fort worth", "tarrant county", "tarrant", "texas", "north texas", "dfw", "dallas-fort worth", "metroplex", "arlington",
          "keller", "southlake", "mansfield", "grand prairie", "burleson", "haslet", "north richland hills", "hurst", "euless",
          "bedford", "grapevine", "weatherford", "benbrook", "white settlement", "saginaw", "crowley", "azle", "colleyville",
          "watauga", "forest hill", "river oaks", "lake worth", "aledo", "roanoke", "trophy club", "westlake", "denton county",
          "parker county", "johnson county", "dallas county", "u.s.", "america", "united states") + OTHER_CITIES
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
        "suspect", "wanted", "arrest", "arrested", "deadly", "fatal", "injured", "dead", "killed"}
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


def entities(title: str, body: str = "") -> list[str]:
    """Named subjects in a headline: runs of capitalised words, kept when they are more than one word, possessive, an
    acronym, or appear capitalised again mid-sentence in the body (so 'Largest enrollment drop' names nothing, while
    'Anthropic's IPO' and 'Northwest ISD' do). Places are returned too; callers decide what to do with them."""
    tokens = _TOKEN.findall(title or "")
    body_mid = set()
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][A-Za-z0-9&'’.-]+)", body or ""):
        body_mid.add(_clean(m.group(1)).lower())
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not _capitalised(tok) or _clean(tok).lower() in STOP and i == 0 and not tok.endswith(("'s", "’s")):
            i += 1
            continue
        run = [tok]
        j = i + 1
        while j < len(tokens) and (_capitalised(tokens[j]) or tokens[j].lower() in ("of", "&", "and") and j + 1 < len(tokens) and _capitalised(tokens[j + 1])):
            run.append(tokens[j])
            j += 1
        while run and run[-1].lower() in ("of", "&", "and"):
            run.pop()
        if j < len(tokens) and tokens[j].lower() in INSTITUTION_FALLBACK:    # "Fort Worth police", "Tarrant County jail"
            run.append(tokens[j])
            j += 1
        if j < len(tokens) and _clean(tokens[j]).lower() in ATTRIBUTION:     # "..., Morath says": a source, not the subject
            i = max(j, i + 1)
            continue
        words = [_clean(w) for w in run]
        words = [w for w in words if w]
        if words and words[0].lower() in STOP and len(words) > 1:
            words = words[1:]
        phrase = " ".join(words)
        low = phrase.lower()
        possessive = any(w.endswith(("'s", "’s")) for w in run)
        acronym = len(words) == 1 and words[0].isupper() and len(words[0]) >= 2 and low not in ACRONYM_STOP
        keep = bool(words) and low not in STOP and low not in ACRONYM_STOP and (
            len(words) > 1 or possessive or acronym or low in body_mid or _known_subject(low) or i > 0 and low not in STOP)
        if keep and phrase not in out:
            out.append(phrase)
        i = max(j, i + 1)
    return out


def entity_topics_for(names: list[str], category: str) -> list[str]:
    """Library topics that depict the named subjects, specific sports grounds first for sports stories."""
    out: list[str] = []
    for name in names:
        low = " " + name.lower() + " "
        for phrases, topic in TOPIC_RULES:
            if topic not in ENTITY_TOPICS or not any(p.strip() and (p in low or low.strip() in p) for p in phrases):
                continue
            if _elsewhere(name) and topic in FORT_WORTH_ONLY:        # Dallas City Hall is not Fort Worth City Hall
                continue
            if category == "sports" and topic in SPORTS_VARIANTS and SPORTS_VARIANTS[topic] not in out:
                out.append(SPORTS_VARIANTS[topic])
            if topic not in out:
                out.append(topic)
    return out


def plan_subject(title: str, body: str, category: str) -> SubjectPlan:
    names = entities(title, body)
    subjects = [n for n in names if not _is_place(n)]
    topics = entity_topics_for(subjects, category)
    plan = SubjectPlan(primary=subjects[0] if subjects else None, entities=names, entity_topics=topics)
    if topics:
        plan.mode = "entity"
        return plan
    if not subjects:
        plan.mode = "beat"
        return plan
    fallback: list[str] = []
    for name in subjects:
        for word in name.lower().replace("-", " ").split():
            fallback += [t for t in INSTITUTION_FALLBACK.get(word, []) if t not in fallback]
    plan.fallback_topics = fallback
    plan.mode = "institution" if fallback else "search"
    return plan


def subject_fits(title: str, body: str, category: str, subject: str | None) -> tuple[bool, str]:
    """The pre-publish check: the subject a photo was chosen for must still be what the headline is about."""
    if not subject:
        return False, "no subject was recorded for the photo"
    plan = plan_subject(title, body, category)
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
