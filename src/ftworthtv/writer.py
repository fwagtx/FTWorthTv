"""Caption writer: Claude (structured output, Dallas-Texas-TV voice) with a deterministic template fallback."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from dateutil import parser as dtparse

from .config import Settings
from .models import CATEGORIES, PostCopy, Story
from .textutil import clean_hashtag, collapse_ws, fmt_time, relative_day, smart_headline, truncate

log = logging.getLogger(__name__)

CATEGORY_EMOJI = {"breaking": "🚨", "crime": "🚔", "traffic": "🚧", "weather": "⛈️", "events": "🎟️", "food": "🌮",
                  "sports": "🏈", "culture": "🤠", "community": "💜", "business": "🏗️", "politics": "🏛️", "other": "📍"}
PLACES = ["Arlington", "Keller", "Southlake", "Grapevine", "Colleyville", "Mansfield", "Burleson", "Crowley", "Benbrook",
          "Haltom City", "North Richland Hills", "Hurst", "Euless", "Bedford", "Saginaw", "White Settlement", "Azle", "Weatherford"]
TOPIC_HASHTAGS = {
    "tcu": ["#TCU", "#GoFrogs"], "horned frogs": ["#TCU", "#GoFrogs"], "rodeo": ["#Rodeo", "#Cowtown"], "stock show": ["#FWSSR", "#Cowtown"],
    "stockyards": ["#Stockyards"], "dickies arena": ["#DickiesArena"], "billy bob": ["#BillyBobsTexas"], "sundance square": ["#SundanceSquare"],
    "cowboys": ["#DallasCowboys"], "rangers": ["#TexasRangers"], "mavericks": ["#Mavs"], "stars": ["#TexasHockey"],
    "texas motor speedway": ["#TexasMotorSpeedway"], "i-35w": ["#I35W"], "35w": ["#I35W"], "arlington": ["#Arlington"],
    "near southside": ["#NearSouthside"], "magnolia": ["#MagnoliaAve"], "west 7th": ["#West7th"], "cultural district": ["#CulturalDistrict"],
}
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
URL_RE = re.compile(r"https?://\S+")
HASHTAG_RE = re.compile(r"(?<!\w)#\w+")


# --------------------------------------------------------------------------- prompt
DALLAS_CAPTION_RULES = """    Write it EXACTLY like the Dallas Texas TV page (120 of their posts studied, Nov 2026): a plain news brief in one to
    three short paragraphs, median 250 characters, never over 400. The caption NEVER repeats the card headline; it tells
    the story in fuller form. Two house shapes, pick whichever fits:
      (a) wire style: a lead sentence with the news, then one line of context.
          "Waymo has temporarily suspended driverless freeway rides in Austin and other U.S. markets following safety
           concerns after several of its vehicles entered active crash scenes.\n\nThe company says surface-street rides continue."
      (b) plain local style: short sentences, then a closing "what happens next" line with a date when there is one.
          "Rep. Eddie Morales Jr. of Eagle Pass filed House Bill 410. It would make it illegal for ICE agents in Texas to
           cover their faces.\n\nLawmakers take it up when the session starts Jan. 12."
    Attribute inline, the way they do ("according to ESPN", "a WalletHub study found", "the city says"); never a "via"
    line, never a URL. No emoji at all in the caption (their captions have none). No hashtags, no hook line, no bullets,
    no "📍" line, no follow line, no questions to the audience. Facts only from the source text; never invent a quote.
    For WANTED posts: "<City> police are looking for <name>, wanted for <charge>. Crime Stoppers is offering up to
    <reward> for information leading to an arrest." then a second paragraph with the tip phone.
    The headline (printed on the card) may start with "BREAKING:" for genuinely breaking news, otherwise plain."""
DETAILED_CAPTION_RULES = """    Line 1 = the hook, under 90 characters (this is what shows before "See more").
    Then 1-3 short lines with the key facts (who / what / where / when) taken ONLY from the source text.
    Then a "📍 <City>, TX" line (or the neighborhood: Stockyards, Near Southside, West 7th, Arlington...).
    End with a follow call to action such as "Follow {handle} for more 📲" (vary the wording).
    1-3 emojis total, no hashtags, no URLs, under 500 characters."""


def reference_examples(settings: Settings, limit: int = 12) -> str:
    """Real captions from the reference page (config/caption_examples.json, written by scripts/ingest_reference_posts.py)."""
    path = settings.root / "config" / "caption_examples.json"
    if not path.exists():
        return ""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    lines = []
    for r in rows[:limit]:
        cap = str(r.get("caption", "")).strip().replace("\n\n", " / ").replace("\n", " / ")
        if cap:
            lines.append(f"- [{r.get('category', 'other')}] {cap[:300]}" + (f"  (card: {r['headline']})" if r.get("headline") else ""))
    if not lines:
        return ""
    return "\nREAL CAPTIONS FROM THE REFERENCE PAGE (match this voice and length; never copy them):\n" + "\n".join(lines) + "\n"


def build_system_prompt(settings: Settings) -> str:
    b = settings.brand
    style = (b.get("caption", {}) or {}).get("style", "dallas")
    caption_rules = DALLAS_CAPTION_RULES if style == "dallas" else DETAILED_CAPTION_RULES.replace("{handle}", str(b.get("handle")))
    examples = reference_examples(settings)
    return f"""You write social media posts for "{b.get('page_name')}" ({b.get('handle')}), a Fort Worth, Texas Facebook/Instagram page
built in the style of the big local-entertainment pages (Dallas Texas TV: "The home of DTX entertainment", 600K+ followers).
Tagline: {b.get('tagline')}

VOICE
{b.get('voice', '').strip()}

OUTPUT FIELDS
- skip / skip_reason: skip=true if the story is a bad fit for an upbeat local entertainment & news page: obituaries, graphic harm to
  children, sexual assault, suicide, pure national politics, press-release spam, a paywalled teaser with no facts, or (when scope is
  "local") not actually
  about Fort Worth / Tarrant County / the nearby suburbs. Otherwise skip=false and skip_reason="".
- category: one of {", ".join(CATEGORIES)}.
- headline: the one-line news headline printed on our post card under the page name, <= 110 characters, the way a news tweet
  reads: "New Texas bill filed would ban ICE agents from wearing masks/face coverings", "New Texas leaders say THC rules are a
  top priority for 2027". Sentence case, plain words, no emoji, no hashtags, no trailing period.
- caption: the Facebook caption.
{caption_rules}
- first_comment: exactly this shape:
    Source: <outlet name> <url>
    {{photo_credit}}
    DM us your videos & photos 📲
  (keep the literal placeholder {{photo_credit}}; we fill it in.) For events use "🎟️ Tickets: <url>" as the first line instead.
- hashtags: 5-8 tags mixing #FortWorth #FTW #DFW with topic tags. No spaces inside a tag.
- image_query: 2-5 words describing a concrete, generic, safe scene for a licensed stock photo (no identifiable people, no logos),
  e.g. "Fort Worth skyline night", "Texas highway rain", "concert crowd lights", "barbecue brisket plate", "police lights street night".
  Prefer Fort Worth landmarks when the story is about the city itself.
- location: "City, TX" best guess from the story, default "Fort Worth, TX".

{examples}SCOPE: "local" stories are Fort Worth / Tarrant County / Arlington. "dfw" and "texas" stories are the wider beat the Dallas
page also covers every day: Texas teams (Cowboys, Rangers, Mavericks, Stars, Texans, Astros, Spurs, Longhorns, Aggies, Texas
Tech, TCU, SMU), new Texas bills and the governor, H-E-B, Buc-ee's, Whataburger, gas prices, outages, statewide weather. Keep
them, and write them for a Fort Worth reader (say what it means here when that is natural; never pretend it happened here).
"national" stories are the few moments the whole country talks about (a game launch, a finale, a tour announcement, a jackpot,
the Super Bowl): write them straight and short, with a Fort Worth angle only when the source gives one.

WHAT THIS PAGE POSTS (copied from what the Dallas page does; keep this mix in mind when writing)
- "right now" moments: wrecks and closures on I-35W/I-30/820, storms, lightning, snow, flooding, fights at games, concerts
  ("Kid Cudi joins Kanye at AT&T"), fans taking over the city, funny street scenes ("how does this happen 😂")
- one-liner local news: rankings ("Fort Worth was ranked..."), openings ("Nine new stores are coming to..."), closings,
  big decisions (arenas, taxes), consumer alerts (outages, recalls, free sandbags), statewide bills everyone feels
- sports fan culture: Cowboys/Rangers (Arlington), TCU, Mavs, Stars; the fans and the moments more than the box score
- concerts & nightlife: who played last night, who showed up, Dickies Arena / Billy Bob's / Bass Hall
- weather drama and PSAs; seasonal & cultural beats: Stock Show, Juneteenth, State Fair, Halloween houses, holiday lights
- crime only when the police published it: WANTED bulletins, arrests, homicide investigations

KIND-SPECIFIC RULES
- culture: the title IS the caption (evergreen seasonal/cultural beat); do not add facts.
- nws_alert: hook starts with ⚠️ and names the alert + area; give the end time in Central time; include 1-2 safety lines from the official
  instruction; category weather; no jokes.
- nws_forecast: a "Good morning, Fort Worth" style post with today's high, conditions and tonight's low; category weather.
- event: say when (Tonight / Tomorrow / This Saturday + time) and where; end the facts with "Tickets in the comments 🎟️"; category events (or sports).
- event_roundup: hook "This weekend in Fort Worth 🎟️" then one "• day – event @ venue" line per event (max 6).
- reddit: credit "r/FortWorth" in the hook ("Trending on r/FortWorth 👀").
Never invent facts, names, numbers or quotes. If the source is thin, write less."""


def story_payload(story: Story, settings: Settings, now: datetime) -> dict:
    payload = {
        "kind": story.source_kind,
        "source": story.source,
        "title": story.title,
        "summary": story.summary,
        "url": story.url,
        "published_central": fmt_time(story.published, settings.tz) if story.published else None,
        "category_hint": story.category or story.category_hint,
        "scope": story.extra.get("scope", "local"),       # local | dfw | texas | national
        "now_central": now.astimezone(settings.tz).strftime("%A %Y-%m-%d %I:%M %p"),
    }
    extra = {k: v for k, v in story.extra.items() if k in ("severity", "event", "area", "ends", "instruction", "venue", "when",
                                                            "genre", "price_min", "ticket_url", "events", "high", "low", "short",
                                                            "pop", "wind", "score", "author")}
    if extra.get("ends"):
        try:
            extra["ends_central"] = fmt_time(dtparse.isoparse(extra["ends"]), settings.tz)
        except (ValueError, TypeError):
            pass
    payload["details"] = extra
    return payload


# --------------------------------------------------------------------------- claude
def claude_copy(story: Story, settings: Settings, now: datetime) -> PostCopy | None:
    if not settings.anthropic_api_key or settings.writer not in ("auto", "claude_api"):
        return None
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        log.warning("anthropic SDK not installed; using template writer")
        return None
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=90.0)
    payload = story_payload(story, settings, now)
    try:
        response = client.beta.messages.parse(
            model=settings.model,
            max_tokens=2048,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": build_system_prompt(settings), "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": "Write the post for this story:\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)}],
            output_format=PostCopy,
            output_config={"effort": settings.effort},
        )
    except anthropic.RateLimitError as exc:
        log.warning("claude rate limited (%s); using template writer", exc.message)
        return None
    except anthropic.APIStatusError as exc:
        log.warning("claude API error %s: %s; using template writer", exc.status_code, exc.message)
        return None
    except anthropic.APIConnectionError as exc:
        log.warning("claude connection error: %s; using template writer", exc)
        return None
    except Exception as exc:  # pydantic validation, unexpected shapes
        log.warning("claude writer failed: %s; using template writer", exc)
        return None
    if response.stop_reason == "refusal" or response.parsed_output is None:
        log.warning("claude declined to write this one (%s); using template writer", response.stop_reason)
        return None
    return response.parsed_output


# --------------------------------------------------------------------------- claude code (subscription, no API bill)
JSON_FIELDS = "skip (boolean), skip_reason (string), category (string), headline (string), caption (string), first_comment (string), hashtags (array of strings), image_query (string), location (string)"


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def claude_code_copy(story: Story, settings: Settings, now: datetime) -> PostCopy | None:
    """Write the caption with headless Claude Code (`claude -p`) authenticated by a Pro/Max subscription token.

    Needs the `claude` CLI on the runner and CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`. No pay-as-you-go API key.
    """
    import os
    import shutil
    import subprocess
    if settings.writer not in ("auto", "claude_code"):
        return None
    token = settings.claude_code_oauth_token or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    binary = shutil.which("claude")
    if not token or not binary:
        return None
    prompt = (build_system_prompt(settings) + "\n\nWrite the post for this story. Reply with ONLY one JSON object (no prose, no code fence) "
              f"with exactly these keys: {JSON_FIELDS}.\n\nSTORY:\n" + json.dumps(story_payload(story, settings, now), ensure_ascii=False, indent=2))
    env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": token}
    env.pop("ANTHROPIC_API_KEY", None)  # make sure the subscription token is what gets used
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as scratch:  # empty cwd: no repo files or CLAUDE.md get pulled into the context
            proc = subprocess.run([binary, "-p", prompt, "--output-format", "json", "--max-turns", "1"],
                                  capture_output=True, text=True, timeout=180, env=env, cwd=scratch)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("claude code writer failed to run: %s", exc)
        return None
    if proc.returncode != 0:
        log.warning("claude code exited %s: %s", proc.returncode, (proc.stderr or proc.stdout)[-300:])
        return None
    outer = _extract_json(proc.stdout) or {}
    result = outer.get("result") if isinstance(outer, dict) and "result" in outer else proc.stdout
    data = _extract_json(result if isinstance(result, str) else json.dumps(result))
    if not data:
        log.warning("claude code returned no JSON; using template writer")
        return None
    try:
        return PostCopy(**{k: v for k, v in data.items() if k in PostCopy.model_fields})
    except Exception as exc:  # pydantic validation
        log.warning("claude code JSON did not validate (%s); using template writer", exc)
        return None


# --------------------------------------------------------------------------- template
SOMBER_WORDS = ("killed", "dies", "died", "dead", "fatal", "death", "shot", "shooting", "homicide", "murder", "drown", "stabbed")


def is_somber(story: Story) -> bool:
    text = story.text()
    return any(w in text for w in SOMBER_WORDS)


ROAD_RE = re.compile(r"\b(I-35W|I-35|I-30|I-20|I-820|Loop 820|SH 121|US 287|Chisholm Trail Parkway|Camp Bowie|Highway 377)\b", re.I)


def hook_for(story: Story, category: str) -> str:
    """First line of a template caption: short, local, Dallas-Texas-TV flavored. The title follows on the next line."""
    text = story.text()
    title = story.title.lower()
    if category == "traffic":
        m = ROAD_RE.search(story.title) or ROAD_RE.search(story.summary)
        return f"{m.group(1)} right now 🚨" if m else "Heads up, Fort Worth drivers 🚧"
    if category == "weather":
        return "Fort Worth weather check 🌤️"
    if category == "food":
        return "New spot alert, Fort Worth 🌮" if ("open" in text or "new" in text) else "Fort Worth foodies 👀"
    if category == "sports":
        if any(w in text for w in ("tcu", "horned frogs", "frogs")):
            return "Dub for the Frogs 🐸" if ("win" in title or "beat" in title) else "Frogs update 🐸"
        return "Fort Worth sports 🏆"
    if category == "crime":
        return "FWPD update 🚔"
    if category == "business":
        return "Big news for Fort Worth 🏗️"
    if category == "culture":
        return "Only in Fort Worth 🤠"
    if category == "community":
        return "Fort Worth, this one's for you 💜"
    if category == "breaking":
        return "🚨 BREAKING"
    return "Fort Worth 📍"


def guess_location(story: Story, settings: Settings) -> str:
    text = story.text()
    for place in PLACES:
        if place.lower() in text:
            return f"{place}, TX"
    return f"{settings.brand.get('city', 'Fort Worth')}, {settings.brand.get('state', 'TX')}"


def _join(first: str, second: str) -> str:
    """Two sentences, one space apart; no stray period after a title that already ends with ! or ?"""
    sep = " " if first.endswith(("!", "?", "…", ".", '."', "!\"", "?\"")) else ". "
    return f"{first}{sep}{second}"


def _tidy(sentence: str, reference: str = "") -> str:
    """An ALL-CAPS press-release title becomes a sentence: 'HILLWOOD EXPANDS ALLIANCETEXAS ... WITH TWO NEW BUILDINGS' ->
    'Hillwood expands AllianceTexas ... with two new buildings', with every name's casing taken from the article text
    (`reference`, usually the summary); without a reference, each word is capitalised as before."""
    text = collapse_ws(sentence).rstrip(" .")
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.85:   # ALL-CAPS press-release title
        if reference:
            cased: dict[str, str] = {}
            for tok in re.findall(r"[A-Za-z][A-Za-z&'’.-]*", reference):
                tok = tok.rstrip(".'’-&")
                if tok and any(c.isupper() for c in tok) and tok.lower() not in cased:
                    cased[tok.lower()] = tok
            words = []
            for i, w in enumerate(text.split()):
                core = w.strip(",.;:!?\"'()")
                tail = w[len(core):] if core else ""
                if core.lower() in cased:
                    words.append(cased[core.lower()] + tail)
                elif i == 0:
                    words.append(core.capitalize() + tail)
                else:
                    words.append(core.lower() + tail)
            text = " ".join(words)
        else:
            text = " ".join(w if (len(w) <= 3 and w.isupper() and w not in ("NEW", "AND", "THE", "FOR")) else w.capitalize() for w in text.split())
    return text


_CHARGE_QUALIFIERS = {"deadly weapon": "with a deadly weapon", "a deadly weapon": "with a deadly weapon", "family violence": "involving family violence",
                      "serious bodily injury": "causing serious bodily injury", "bodily injury": "causing bodily injury",
                      "public servant": "against a public servant", "elderly": "against an elderly person", "child": "against a child",
                      "habitual": "(habitual offender)", "repeat offender": "(repeat offender)"}


def charge_phrase(charge: str) -> str:
    """'Aggravated Robbery' -> 'for aggravated robbery'; 'Failure to Comply, Sex Offender' (the registration offence, as the
    agencies abbreviate it) -> 'on a sex offender failure-to-comply charge'; a comma list of charges -> 'for aggravated assault and parole violation'."""
    c = collapse_ws(charge or "").strip(" .").lower()
    c = re.sub(r"\bw/\s*(?:a\s+)?deadly weapon\b", ", deadly weapon", c)    # "Agg Assault W/Deadly Weapon" is the same qualifier
    c = re.sub(r"\bw/\s*", "with ", c)
    if "sex offender" in c and "comply" in c:
        return "on a sex offender failure-to-comply charge"
    parts = [x.strip() for x in c.split(",") if x.strip()]
    merged: list[str] = []
    for part in parts:                                        # "Aggravated Assault, Deadly Weapon" is one charge with its qualifier
        q = _CHARGE_QUALIFIERS.get(re.sub(r"^(?:w/|with|w)\s*", "", part).strip())
        if q and merged:
            merged[-1] = f"{merged[-1]} {q}"
        else:
            merged.append(part)
    parts = merged
    if len(parts) == 1:
        return f"for {parts[0]}"
    if len(parts) > 1:                                        # "Aggravated Assault, Parole Violation": two charges
        return "for " + ", ".join(parts[:-1]) + f" and {parts[-1]}"
    return f"for {c}" if c else "on a warrant"


BOILERPLATE = ("newsletter", "subscribe", "sign up", "inbox", "click here", "read more", "learn more", "stay informed", "follow us", "check back",
               "enjoy reading the news again", "welcome to the", "pick something out of this list", "this article", "photo by", "courtesy of",
               "biweekly", "weekly column", "in this week", "scroll down", "latest updates from the", "weather impact team",
               "editor's note", "read on for", "hottest headlines", "top stories", "weekly series", "is sponsored by",
               "sponsored", "advertis", "click to", "watch the video", "see the full", "continue reading", "appeared first on",
               "the post ", "related:", "more:", "also read", "photograph by", "photo by", "has more.", "has more on", "joins nbc",
               "joins fox", "to break down", "is a senior writer", "is a staff writer", "is a reporter", "is a freelance", "contact him",
               "contact her", "contributed to this report", "in the video", "player above", "video above", "watch above", "download the",
               "our app", "tap here", "this story will be updated", "check back for updates",
               "help us pursue the truth", "every gift makes a difference", "officials accountable is just beginning",
               "the election is over, but the work", "your donation", "donate today", "become a member")


def _first_sentence(text: str, limit: int = 170) -> str:
    text = collapse_ws(text)
    parts = _split_sentences(text)                                # abbreviation-aware: "Primrose School of N.E. Fort Worth" is one sentence
    first = (parts[0] if parts else text).strip()
    if any(w in first.lower() for w in BOILERPLATE) or len(first) < 25 or looks_like_photo_caption(first):
        return ""
    return first if len(first) <= limit else ""


_ABBREVIATIONS = {"rep", "sen", "gov", "lt", "jr", "sr", "mr", "mrs", "ms", "dr", "st", "ave", "blvd", "rd", "hwy", "no", "vs", "inc", "co",
                  "corp", "ltd", "mt", "ft", "capt", "sgt", "det", "cmdr", "col", "gen", "pvt", "u.s", "a.m", "p.m", "jan", "feb", "mar",
                  "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "e.g", "i.e", "etc", "tx", "dept"}


def _split_sentences(text: str) -> list[str]:
    """Sentence split that survives 'Rep. Eddie Morales Jr.', 'Lt. Gov.-elect', 'U.S.' and quotes after the period."""
    out, start = [], 0
    for m in re.finditer(r"[.!?][\"”’)]*(?=\s+[A-Z0-9\"“(])", text):
        before = text[start:m.start()]
        last = re.findall(r"[A-Za-z.]+$", before)
        tok = (last[0] if last else "").lower().strip(".")
        if (len(tok) == 1 and tok.isalpha()) or tok in _ABBREVIATIONS or "." in tok:   # "I.M." Pei, "U.S.", "a.m."
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


# "Here's what their plans could mean for taxpayers.": a teaser for the article, not a sentence of news (Nov 23, Texas Tribune)
_TEASER_RE = re.compile(r"\s*(?:here[’']s|here is|here are|this is|find out|learn|read on|keep reading|see)\s+(?:what|how|why|who|where|when|the|a)\b", re.I)
# "Watch Titans rookie Carnell Tate score ...", "Check out the play here": a sentence that points at a clip
_CLIP_LEAD_RE = re.compile(r"\s*(?:watch|check out|see|listen to|take a look at)\b(?! (?:out|for)\b)", re.I)
# "That involves the West Fork and Parker County public utility agencies." after a sentence that was dropped for length
# (Nov 22, Fort Worth Report's water story): a demonstrative opener needs the sentence right before it
_DEMONSTRATIVE_RE = re.compile(r"^(?:That|This|These|Those|Such)\s+(?:is|are|was|were|involves?|included?|includes|means?|meant|"
                               r"comes?|came|would|will|could|can|has|have|had|led|leads?|follows?|marks?|marked|makes?|made)\b")
# "The Frogs' five losses before that ...": a sentence that points back at one we did not keep cannot open the caption
_DANGLING_RE = re.compile(r"\b(?:before that|after that|since then|at that point|that loss|that win|that game|that decision)\b", re.I)
# "CBS Sports Texas has independently confirmed that TCU fired ...": the outlet is credited in the first comment, the fact leads
_CONFIRMED_RE = re.compile(r"^(?:[A-Z][\w&.'’-]*\s){1,4}(?:has|have) (?:independently |exclusively )?(?:confirmed|learned) that ")
# a scraped page's image labels and ad slots that run into the text: "Logo text Justin Timberlake is the subject of ..." (Nov 23,
# The Hollywood Reporter), "blogherads.adq.push(function () { ..."
_PAGE_LABEL_RE = re.compile(r"\b(?:Logo text|Logo image|Image credit|Advertisement|ADVERTISEMENT|Skip Ad|Story continues below advertisement)\s+(?=[A-Z])")
_SCRIPT_RE = re.compile(r"\b(?:blogherads|googletag|adq\.push|window\.\w+|function\s*\(\))", re.I)
_SCRIPT_CUT_RE = re.compile(r"\b(?:blogherads|googletag)\b.*?(?:\}\s*\)\s*;|$)", re.S)   # an ad script runs to its "});" or the end
# CBS pages: "Updated on: November 22, 2026 / 12:51 PM CST / CBS/AP" glued to the front of the lead sentence
# the full outlet name is tried first: "Updated on: November 23, 2026 / 11:23 AM CST / CBS Texas It's the season ..." left
# "Texas It's the season" when "CBS" alone matched (Nov 23)
_UPDATED_RE = re.compile(r"(?:(?:(?:Updated|Published) on:\s*)?(?:January|February|March|April|May|June|July|August|September|October|"
                         r"November|December) \d{1,2}, \d{4} / \d{1,2}:\d{2} [AP]M [A-Z]{2,4} / "
                         r"(?:CBS News Texas|CBS Texas|CBS News|CBS/AP|AP|CBS)\s+"
                         r"|(?:Updated|Published) on:[^/]{5,40}/[^/]{3,20}/\s*[A-Z]{2,}(?:/[A-Z]{2,})*(?:\s+(?:News\s+)?Texas\b)?\s+)")

_DATELINE_RE = re.compile(r"^(?:[A-Z][A-Z .'’-]{2,40}, (?:Texas|TX|Okla\.|La\.|N\.M\.)|[A-Z][A-Z .'’-]{2,40}) ?(?:--|[-–—]) ")   # ESPN: "FRISCO, Texas -- "
_CAPTION_RE = re.compile(r"\b(?:on )?(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\.$")
_PHOTO_CAPTION_RE = re.compile(
    r"\(\d{1,2}\) [a-z]"                                                                                         # "Dak Prescott (4) looks to pass": a jersey number
    r"|\b(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),? (?:Jan|Feb|March|April|May|June|July|Aug|Sept?|Oct|Nov|Dec)\.? \d{1,2}, (?:19|20)\d{2}\b"   # "Thursday, Dec. 29, 2022"
    r"|\b(?:AP Photo|Getty Images|USA TODAY Sports|Imagn Images|Mandatory Credit)\b"
    r"|^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, (?:19|20)\d{2}; ")           # "Nov 15, 2026; Arlington, Texas, USA; ..."


def looks_like_photo_caption(sentence: str) -> bool:
    """A page's figure caption scraped as the lead ("... at Nissan Stadium Thursday, Dec. 29, 2022, in Nashville, Tenn.") is not news."""
    return bool(_CAPTION_RE.search(sentence) or _PHOTO_CAPTION_RE.search(sentence))


_QUESTION_REF_RE = re.compile(r"\b(?:that|this|the|those|these) questions?\b", re.I)
_BACKREF_OPENER_RE = re.compile(r"^(?:At|During|In|After|Before) (?:the|that|this) (?:meeting|hearing|session|vote|event|ceremony|briefing|news conference|press conference)\b")
_ITEMS_OPENER_RE = re.compile(r"^The (?:\w+ )?(?:programs?|plans?|projects?|proposals?|changes?|measures?|initiatives?|strategies|options|items) "
                              r"(?:highlighted|mentioned|discussed|described|outlined|presented|listed)\b")   # "The city programs highlighted use..."
_MONEY_RE = re.compile(r"\$\s?\d[\d,.]*(?:\s?(?:million|billion|thousand))?", re.I)
_MEETING_DATE_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})(?:,? (\d{4}))?\b[^.]{0,80}?"
                              r"\b(?:meeting|hearing|session)\b", re.I)


def stale_meeting_recap(story: Story, now: datetime) -> bool:
    """'A proposed pet resort dominated the Nov. 4 Colleyville City Council meeting' published on Nov. 21: a meeting recap
    more than a week old is not news for a daily page. A meeting still to come is never stale."""
    from datetime import date as _date
    lead = " ".join(_split_sentences(collapse_ws(story.summary or ""))[:3])
    m = _MEETING_DATE_RE.search(lead)
    if not m:
        return False
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    ref = story.published or now
    year = int(m.group(3)) if m.group(3) else ref.year
    try:
        when = _date(year, months.index(m.group(1)[:3].lower()) + 1, int(m.group(2)))
    except ValueError:
        return False
    if not m.group(3) and (when - ref.date()).days > 200:
        when = when.replace(year=year - 1)                    # a December meeting named in January
    return (ref.date() - when).days > 7


_FIRST_PERSON_RE = re.compile(r"^(?:I|I'm|I’m|I've|I’ve|I'd|I’d|My)\b")
_DEFINITE_OPENER_RE = re.compile(r"^The (?:effort|plan|program|initiative|project|move|deal|change|decision|measure|proposal|event|ordinance|"
                                 r"policy|agreement|lawsuit|case|funding|money|vote|ruling|order|bill|law|ban|closure|expansion|partnership|"
                                 r"contract) (?:is|was|will|would|has|had|comes|came|includes|aims|calls)\b")


def _story_start(text: str) -> str:
    """Where the story itself begins. A feed that opens with a sentence the story repeats further down has put a teaser
    first: NBC 5's "Detectives learned that the shooting victim and suspect were involved in a verbal and physical
    altercation ..." came before "Fort Worth police are investigating a homicide ..." and again four sentences later
    (Nov 23). An excerpt followed by the full text (the same sentences twice) starts at the full text; a lone teaser
    sentence is dropped."""
    parts = _split_sentences(text)
    norm = [re.sub(r"\W+", " ", p).strip().lower() for p in parts]
    if len(parts) < 3 or len(norm[0]) < 25:
        return text
    j = next((k for k in range(1, len(parts)) if norm[k] == norm[0]), None)
    if j is None or j == 1:
        return text                                   # never repeated, or the lead itself twice in a row
    if all(k + j < len(parts) and norm[k + j] == norm[k] for k in range(1, j)):
        return " ".join(parts[j:])
    return " ".join(parts[1:])


# a long sentence's trailing participle phrase is detail: ", kicking off Thanksgiving week and celebrating the annual ..."
_TRAILING_PHRASE_RE = re.compile(r",\s+(?!according\b)(?:[a-z]{3,}ing|which|while|as well as|along with)\b")
_REPORTING_END_RE = re.compile(r"\b(?:said|says|told|announced|reported|added|explained|wrote)(?:\s+\w+){0,2}$", re.I)


_CONGRATS_RE = re.compile(r"^Congratulations to (?:the )?([A-Z][^,]{2,80}?),\s+(?:which|who)\s+(was|were|is|are|has|have|earned|won)\s+")
# a company's announcement of a hire, in press-release form: Nov 24, "LEWISVILLE, TEXAS (November 23, 2026) – McAdams ...
# announced today the appointment of Marilyn Ramirez as vice president of Energy + Power"
_PRESS_RELEASE_RE = re.compile(r"^[A-Z][A-Z .'’-]+,\s+[A-Z][A-Za-z .]+\s*\((?:January|February|March|April|May|June|July|August|"
                               r"September|October|November|December) \d{1,2}, \d{4}\)\s*[–—-]|\bannounced today\b|\b(?:FOR IMMEDIATE RELEASE|"
                               r"PRNewswire|Business Wire|GLOBE NEWSWIRE)\b")
# the dateline-with-date form without parentheses: "MINERAL WELLS, Texas Nov. 23, 2026 — XMX Defense, an American ..." (Nov 24)
_PRESS_DATELINE_RE = re.compile(r"(?:^|\s)[A-Z][A-Z .'’-]{2,},\s+[A-Z][A-Za-z.]+\.?,?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
                                r"[a-z]*\.?\s+\d{1,2},\s+\d{4}\s*[—–-]")


def press_release(summary: str) -> bool:
    """A company's announcement in press-release form is its advertising, not news."""
    text = summary or ""
    return bool(_PRESS_RELEASE_RE.search(text) or _PRESS_DATELINE_RE.search(text))


_PERSONNEL_PR_RE = re.compile(r"\b(?:appointment of|has (?:named|appointed|hired|promoted)|announced (?:the )?(?:hiring|promotion) of|"
                              r"joins? (?:the firm|the company|as)|welcomes .{3,60} as)\b", re.I)


def personnel_press_release(summary: str) -> bool:
    text = summary or ""
    return bool(_PRESS_RELEASE_RE.search(text)) and bool(_PERSONNEL_PR_RE.search(text))


# a sponsor credit or a superlative is the promoter's copy, not news
_PROMO_SENTENCE_RE = re.compile(r"\b(?:presented by|sponsored by|brought to you by|the ultimate|feel-good|must-see|must see|"
                                r"unforgettable|don't miss|don’t miss|once-in-a-lifetime|world-class experience)\b", re.I)


def trim_trailing_phrase(sentence: str, limit: int) -> str:
    """A sentence over the length limit keeps its main clause when the rest is a trailing phrase. Nov 23, CBS Texas: "The
    Dallas Cowboys and The Salvation Army will mark a major milestone ... at AT&T Stadium on Monday, kicking off Thanksgiving
    week and celebrating the annual Red Kettle Campaign." and the sentence after it both ran past the limit and were dropped
    whole, so the caption kept only the dek about money raised, without the lighting ceremony the headline announced."""
    if not sentence.endswith((".", "!")) or sentence.count('"') % 2 or sentence.count("“") != sentence.count("”"):
        return ""
    best = ""
    for m in _TRAILING_PHRASE_RE.finditer(sentence):
        head = sentence[:m.start()].rstrip(" ,;:")
        if len(head) > limit:
            break
        if (len(head.split()) >= 8 and head.count('"') % 2 == 0 and head.count("“") == head.count("”")
                and not _REPORTING_END_RE.search(head)):
            best = head + "."
    return best


def _sentences(text: str, max_n: int = 4, limit: int = 220, lead: int = 650) -> list[str]:
    """Complete, boilerplate-free sentences from the lead of an article summary, in order (later paragraphs of a scraped
    page can belong to another item, so only the first `lead` characters are considered)."""
    out: list[str] = []
    text = _DATELINE_RE.sub("", _UPDATED_RE.sub("", collapse_ws(text or "")))   # datelines and "Updated on: ..." stamps are not sentences
    text = _story_start(_SCRIPT_CUT_RE.sub(" ", text))
    cut_short = len(text) > lead
    if cut_short:
        text = text[:lead]
    parts = _split_sentences(text)
    if cut_short and parts:
        parts = parts[:-1]                    # the lead limit cut the last sentence: drop it whole, never at "Judge Mark T." (Nov 22)
    merged: list[str] = []
    parts = [re.sub(r"\s+([,.;:!?])", r"\1", _CONFIRMED_RE.sub("", _PAGE_LABEL_RE.sub("", p))) for p in parts]   # "the Tennessee Titans , stripping"
    # a dateline after the dek opens the article's own first sentence: FOX 4's "... Tarrant counties. DALLAS - North Texas
    # faces a gloomy, chilly Tuesday ..." (Nov 24)
    parts = [_DATELINE_RE.sub("", p) for p in parts]
    # the city's voice, not ours: "Congratulations to Tarrant County College, which was listed among ..." (Nov 24)
    parts = [_CONGRATS_RE.sub(lambda m: f"{m.group(1)} {m.group(2)} ", p) for p in parts]
    parts = [re.sub(r"(\w)s ' (?=\S)", r"\1s' ", p) for p in parts]          # ESPN's "the Dallas Cowboys ' 51-30 win" (Nov 24)
    parts = [p for p in parts if not _SCRIPT_RE.search(p)]          # an ad script is not a sentence
    parts = [p for p in parts if not _CLIP_LEAD_RE.match(p) and not _TEASER_RE.match(p)]
    parts = [p[0].upper() + p[1:] if p else p for p in parts]
    for part in parts:                                        # a sentence that opens a quote keeps going until it closes it
        if merged and (merged[-1].count('"') % 2 == 1 or merged[-1].count("“") != merged[-1].count("”")):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    pending_q = None                                          # a lede's question, kept only when the next sentence refers back to it
    last_kept = -2
    for k, part in enumerate(merged):
        prev_q, pending_q = pending_q, None
        if part.count('"') % 2 == 1 or part.count("“") != part.count("”"):
            continue                                          # still unbalanced: a cut-off quote is not a sentence we can post
        if part.endswith("?") and not re.search(r"\b[Yy]ou\b", part) and not part.lower().startswith(("it would be", "imagine", "let's", "let us")):
            pending_q = part                                  # "As more data centers come, who gets a say?" ... "made that question part of his campaign"
            continue
        if part.endswith("?") or re.search(r"\b[Yy]ou\b", part) or part.lower().startswith(("it would be", "imagine", "let's", "let us")):
            continue                                          # a columnist's rhetorical question or second person is not a news sentence
        if _FIRST_PERSON_RE.match(part):
            continue                                          # "I typically start my mornings walking my dogs": a resident's essay, not news
        if len(part) > limit:
            part = trim_trailing_phrase(part, limit) or part
        if len(part) < 25 or len(part) > limit or not part.endswith((".", "!", "?", '"', "”", "’", ")")) or len(part.split()) < 6:
            continue
        if _PROMO_SENTENCE_RE.search(part):
            continue                                          # "The ultimate feel-good show ... presented by PNC Bank" (Nov 24)
        if any(w in part.lower() for w in BOILERPLATE) or part.endswith(("…", "...")) or looks_like_photo_caption(part):
            continue                                          # photo captions end with a date: "...at the Capitol, on November 16, 2026."
        if any(_similar(part, prev) or shared_run(prev, part) for prev in out):     # og:description often repeats the first paragraph
            continue
        money = {m.lower().replace(" ", "") for m in _MONEY_RE.findall(part)}
        if money and any(money & {x.lower().replace(" ", "") for x in _MONEY_RE.findall(prev)} for prev in out):
            continue                                          # "$7 million" a second time is the nut graf repeating itself
        if _DEMONSTRATIVE_RE.match(part) and last_kept != k - 1:
            continue                                          # "That involves the West Fork ...": what "that" was got dropped
        if _QUESTION_REF_RE.search(part):
            if not prev_q or len(out) + 2 > max_n:
                continue                                      # "that question" with no question before it reads as a cut
            out.append(prev_q)
        out.append(part)
        last_kept = k
        if len(out) >= max_n:
            break
    def _backref(s: str) -> bool:
        return bool(_DEFINITE_OPENER_RE.match(s) or _BACKREF_OPENER_RE.match(s) or _ITEMS_OPENER_RE.match(s) or _DANGLING_RE.search(s))
    if len(out) > 1 and _backref(out[0]) and not out[0].endswith("?"):
        lead = next((k for k, s in enumerate(out) if not _backref(s)), None)
        if lead:                              # a nut graf, "At the meeting, ..." or "losses before that" does not open:
            out.insert(0, out.pop(lead))      # the sentence that names the subject goes first (Nov 22: TCU fires Dykes)
    return out


_SIM_STOP = {"the", "and", "for", "with", "that", "this", "will", "are", "was", "were", "has", "have", "had", "its", "from", "into",
             "their", "they", "them", "his", "her", "been", "being", "not", "but", "who", "which", "what", "when", "where", "about",
             "after", "before", "over", "than", "then", "also", "said", "says", "say", "team", "team's"}


def _content_stems(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9&]+", (text or "").lower().replace("’", "'").replace("'s", "")):
        if len(w) <= 2 or w in _SIM_STOP:
            continue
        w = re.sub(r"(?<=\d)(st|nd|rd|th)$", "", w)            # "30th anniversary" and "30 years" share the 30
        for end in ("ing", "ed", "es", "s"):
            if len(w) > len(end) + 3 and w.endswith(end):
                w = w[:-len(end)]
                break
        out.add(w)
    return out


def shared_run(a: str, b: str, n: int = 7) -> bool:
    """b repeats a run of n words from a: the lede restating the dek. Nov 24, FOX 4: "The first freeze warning of the season
    takes effect Tuesday night for parts of North Texas ..." then "North Texas faces a gloomy, chilly Tuesday with scattered
    showers before the first freeze warning of the season takes effect tonight"."""
    wa, wb = re.findall(r"[a-z0-9']+", (a or "").lower()), re.findall(r"[a-z0-9']+", (b or "").lower())
    grams = {tuple(wa[i:i + n]) for i in range(len(wa) - n + 1)}
    return any(tuple(wb[i:i + n]) in grams for i in range(len(wb) - n + 1))


def _similar(a: str, b: str) -> bool:
    """Does sentence b just restate a (the title, or an earlier sentence)? RSS summaries often open with the title, and a
    subhead and a lede often say the same thing in other words: Nov 22, "AT&T Stadium will glow red ... celebrate 30 years
    with The Salvation Army Red Kettle campaign" then "The Dallas Cowboys will bathe AT&T Stadium ... in red light to
    celebrate the 30th anniversary of the team's partnership with The Salvation Army's Red Kettle campaign"."""
    wa = {w for w in re.findall(r"[a-z0-9']+", a.lower()) if len(w) > 2}
    wb = {w for w in re.findall(r"[a-z0-9']+", b.lower()) if len(w) > 2}
    if not wa or not wb:
        return False
    if a.lower()[:30] == b.lower()[:30] or len(wa & wb) / len(wa | wb) >= 0.5:
        return True
    sa, sb = _content_stems(a), _content_stems(b)
    if not sa or not sb:
        return False
    shared = len(sa & sb)
    return shared >= max(3, 0.6 * min(len(sa), len(sb)))


def agency_phrase(agency: str) -> str:
    """'Fort Worth Police Department' -> 'Fort Worth police are', 'Texas DPS' -> 'Texas DPS is'."""
    a = agency.replace("Police Department", "police").strip()
    return f"{a} are" if a.lower().endswith("police") else f"{a} is"


def dallas_caption(story: Story, settings: Settings, now: datetime, category: str) -> list[str]:
    """One or two plain sentences, the way the Dallas Texas TV page writes: 'Kid Cudi joins Kanye at AT&T',
    'Things got heated between Cowboys and 49ers fans at Texas Live during the game. Arlington police responded to the scene. 🚨'"""
    kind = story.source_kind
    x = story.extra
    city = settings.brand.get("city", "Fort Worth")
    if kind == "submission":                 # a viewer's clip: their words, where, and the credit
        credit = x.get("credit") or "a viewer"
        text = _tidy(story.summary or story.title)
        return [truncate(text, 400, "…"), f"📍 {x.get('where') or city}", f"🎥 {'Photo' if x.get('photo') else 'Video'}: {credit}"]
    if kind == "video":                      # a YouTube link post: WATCH line, the channel's own first sentence, the credit
        channel = x.get("channel") or story.source
        lead = _first_sentence(story.summary or "", 200)
        parts = [f"WATCH: {truncate(story.title, 140, '')}"]
        if lead and not _similar(story.title, lead):
            parts.append(lead)
        parts.append(f"Video: {channel} on YouTube")
        return parts
    if kind == "nws_alert":
        until = alert_when(story.summary or "", x.get("ends"), now, settings.tz)
        instr = _first_sentence(x.get("instruction", "")) if x.get("instruction") else ""
        return [f"The National Weather Service has issued a {x.get('event', 'weather alert')} for {alert_area(x.get('area', ''))}{until}.", instr]
    if kind == "culture":
        return [_tidy(story.title) if not story.title.rstrip().endswith(("🐂", "🏃", "🇲🇽", "⛳", "✊🏾", "🎆", "🥵", "🐸", "🎡", "💀🌼", "🎃", "🎬", "🎄", "🦃", "🥶")) else story.title.strip()]
    if kind == "nws_forecast":
        high, low, short = x.get("high"), x.get("low"), (x.get("short") or "").lower()
        try:
            if high is not None and int(high) >= 100:
                return [f"{int(high)} degrees in {city} today 🥵"]
            if low is not None and int(low) <= 32:
                return [f"Freezing tonight in {city}, low of {int(low)} 🥶"]
        except (TypeError, ValueError):
            pass
        tonight = re.search(r"Tonight: ([^.]+)\.", story.summary or "")
        night = f" {tonight.group(1)[0] + tonight.group(1)[1:].lower()} tonight." if tonight else ""
        return [f"{short.capitalize()} and a high of {high} in {city} today.{night}" if high and short else _tidy(story.title)]
    if kind == "event":
        start = x.get("start")
        rd = relative_day(dtparse.isoparse(start), now, settings.tz) if start else (x.get("when") or "")
        when = (rd[0].lower() + rd[1:]) if rd else ""          # "this Saturday", "tonight", "tomorrow"
        artist = story.title.split(" at ")[0].split(":")[0].strip()   # drop tour names: "Ty Myers: The Legal Tour" -> "Ty Myers"
        return [f"{artist} at {x.get('venue', city)} {when}. Tickets in the comments 🎟️"]
    if kind == "event_roundup":
        return [f"This weekend in {city}:"] + [f"{e.get('when', '')} – {e.get('title', '')}" for e in x.get("events", [])[:6]]
    if kind == "wanted":
        return [f"{agency_phrase(x.get('agency', 'Police'))} looking for {x.get('name')}, wanted {charge_phrase(str(x.get('charge', '')))}. "
                f"Crime Stoppers is offering up to {x.get('reward')} for information leading to an arrest.",
                f"Call {x.get('tip_phone')} or submit a tip at 469tips.com. You stay anonymous."]
    if kind == "arrest_log":
        entries = x.get("entries", [])
        return [f"Felony arrests in {city} over the last 24 hours:"] + \
               [f"{e.get('name')}{', ' + str(e['age']) if e.get('age') else ''} – {e.get('charge') or 'charges pending'}" for e in entries[:8]] + \
               [settings.brand.get("crime", {}).get("disclaimer", "")]
    if kind == "reddit":
        return [f"{_tidy(story.title)} (via r/FortWorth)"]
    # regular stories: a 2-4 sentence factual summary in two short paragraphs, like
    # "Rep. Eddie Morales Jr. of Eagle Pass filed House Bill 410. It would make it illegal for ICE agents in Texas to cover
    #  their faces." / "Supporters say agents should be identifiable. ICE says masks protect agents from being targeted."
    first = _tidy(story.title, story.summary or "")
    sents = _sentences(story.summary) if story.summary else []
    if sents:
        pool = sents                      # the article lead tells the story; the headline is already on the card
    else:
        pool = [first]                    # nothing but a title: one plain line, no trailing period ("Kid Cudi joins Kanye at AT&T")
    pool = pool[:4]
    p1, p2 = " ".join(pool[:2]), " ".join(pool[2:4])
    return [p for p in (p1, p2) if p]


TOPIC_IMAGE_QUERIES = [  # first match wins; specific landmarks before generic beats
    ("parade of lights", "Fort Worth Parade of Lights"), ("parade", "holiday parade downtown night"), ("stockyards", "Fort Worth Stockyards"),
    ("dickies arena", "category:Dickies Arena"), ("at&t stadium", "category:AT&T Stadium"), ("cowboys", "category:AT&T Stadium"),
    ("globe life", "category:Globe Life Field"), ("rangers", "category:Globe Life Field"), ("tcu", "category:Amon G. Carter Stadium"),
    ("horned frogs", "category:Amon G. Carter Stadium"), ("mavericks", "category:American Airlines Center"), ("stars", "hockey arena ice"),
    ("texas motor speedway", "category:Texas Motor Speedway"), ("sundance square", "Sundance Square Fort Worth"),
    ("cultural district", "Fort Worth Cultural District"), ("kimbell", "Kimbell Art Museum"), ("botanic garden", "Fort Worth Botanic Garden"),
    ("zoo", "Fort Worth Zoo"), ("trinity river", "Trinity River Fort Worth"), ("panther island", "Trinity River Fort Worth"),
    ("west 7th", "Fort Worth West 7th"), ("magnolia", "Fort Worth Near Southside"), ("near southside", "Fort Worth Near Southside"),
    ("downtown", "Fort Worth downtown"), ("dfw airport", "DFW Airport terminal"), ("i-35w", "Fort Worth highway I-35W"),
    ("35w", "Fort Worth highway I-35W"), ("loop 820", "Texas highway traffic"), ("goodwill", "thrift store"), ("h-e-b", "H-E-B grocery store"),
    ("barbecue", "Texas barbecue brisket"), ("bbq", "Texas barbecue brisket"), ("taco", "street tacos"), ("brewery", "craft beer taproom"),
    ("gas prices", "gasoline pump nozzle fueling car"), ("gasoline", "gasoline pump nozzle fueling car"), ("price of gas", "gasoline pump nozzle fueling car"),
    ("pump prices", "gasoline pump nozzle fueling car"),
    ("thanksgiving", "roast turkey Thanksgiving food"), ("christmas", "Christmas lights downtown"), ("halloween", "Halloween decorations"),
    ("police", "police car lights"), ("arlington", "Arlington Texas downtown"), ("haslet", "Fort Worth suburb"), ("keller", "Keller Texas"),
]


def topic_image_query(story: Story, default: str) -> str:
    """A search phrase for the story's beat. A holiday named as a date ('Gas prices drop ahead of Thanksgiving') is not
    the subject (Nov 22: the gas story searched 'Thanksgiving dinner table' and found strangers at a family table), and a
    beat search asks for things, not people."""
    from .images.library import topic_excluded
    text = story.text()
    for key, query in TOPIC_IMAGE_QUERIES:
        if key in text and not (key in ("thanksgiving", "christmas") and topic_excluded(key, text)):
            return query
    return default


def template_copy(story: Story, settings: Settings, now: datetime) -> PostCopy:
    b = settings.brand
    handle = b.get("handle", "@FortWorthTexasTV")
    category = story.category or story.category_hint or "other"
    emoji = CATEGORY_EMOJI.get(category, "📍")
    cta = f"Follow {handle} for more 📲"
    location = guess_location(story, settings)
    kind = story.source_kind
    first_comment = f"Source: {story.source} {story.url}\n{{photo_credit}}\nDM us your videos & photos 📲"
    image_query = {"weather": "Fort Worth skyline storm clouds", "traffic": "Texas highway traffic night", "crime": "police lights street night",
                   "events": "concert crowd lights", "food": "Texas barbecue plate", "sports": "football stadium Texas",
                   "culture": "Fort Worth Stockyards", "community": "Fort Worth downtown street", "business": "Fort Worth skyline day",
                   "breaking": "Fort Worth downtown night"}.get(category, "Fort Worth skyline")
    headline = _tidy(smart_headline(story.title, 110), story.summary or "")

    if kind == "nws_alert":
        until = alert_when(story.summary or "", story.extra.get("ends"), now, settings.tz)
        lines = [f"⚠️ {story.extra.get('event', 'Weather Alert')} for {alert_area(story.extra.get('area', ''))}{until}"]
        if story.extra.get("instruction"):
            lines.append(truncate(story.extra["instruction"], 220))
        lines += ["Stay safe out there, Fort Worth 💜", cta]
        headline = truncate(f"{story.extra.get('event', 'Weather alert')} for {alert_area(story.extra.get('area', ''), short=True)}{until}", 110, "")
        first_comment = f"Source: National Weather Service {story.url}\n{{photo_credit}}"
        image_query = alert_image_query(story.extra.get("event", ""))
    elif kind == "nws_forecast":
        high, low, short = story.extra.get("high"), story.extra.get("low"), story.extra.get("short")
        lines = ["Good morning, Fort Worth ☀️", f"Today: {short}, high near {high}°" if high else truncate(story.summary, 160)]
        if low:
            lines.append(f"Tonight: low near {low}°")
        lines += [f"📍 {location}", cta]
        headline = truncate(f"Fort Worth forecast: {str(short).lower()}, high near {high}" if high and short else "Today's Fort Worth forecast", 110, "")
        first_comment = f"Source: National Weather Service {story.url}\n{{photo_credit}}"
        image_query = "Fort Worth skyline sunrise"
    elif kind == "event":
        start = story.extra.get("start")
        when_word = relative_day(dtparse.isoparse(start), now, settings.tz) if start else story.extra.get("when", "Soon")
        lines = [f"{when_word} at {story.extra.get('venue', 'Fort Worth')} 🎟️", story.title.split(" at ")[0],
                 story.extra.get("when", ""), "Tickets in the comments 👇", f"📍 {story.extra.get('city', 'Fort Worth')}, TX", cta]
        first_comment = f"🎟️ Tickets: {story.url}\n{{photo_credit}}\nDM us your videos & photos 📲"
        headline = truncate(f"{story.title.split(' at ')[0].split(':')[0].strip()} at {story.extra.get('venue', 'Fort Worth')}, {story.extra.get('when', when_word)}", 110, "")
        genre = str(story.extra.get("genre", "")).lower()
        image_query = {"country": "country music concert stage", "basketball": "basketball arena game", "rodeo": "rodeo arena bull riding",
                       "comedy": "comedy show stage microphone", "hockey": "hockey arena", "football": "football stadium crowd",
                       "hip-hop/rap": "hip hop concert crowd", "pop": "pop concert lights", "rock": "rock concert crowd"}.get(genre, "concert crowd lights")
    elif kind == "event_roundup":
        lines = ["This weekend in Fort Worth 🎟️"] + [f"• {e.get('when', '')} – {e.get('title', '')}" for e in story.extra.get("events", [])[:6]]
        lines += ["Tickets in the comments 👇", cta]
        headline = "This weekend in Fort Worth"
        first_comment = "🎟️ Tickets:\n" + "\n".join(f"{e.get('title', '')}: {e.get('url', '')}" for e in story.extra.get("events", [])[:6]) + "\n{photo_credit}"
    elif kind == "wanted":
        x = story.extra
        city_name = x.get("city") or settings.brand.get("city", "Fort Worth")
        lines = [f"🚨 WANTED in {city_name}: {x.get('name')}",
                 f"Wanted by the {x.get('agency')} {charge_phrase(str(x.get('charge', '')))}.",
                 f"Crime Stoppers will pay up to {x.get('reward')} for information leading to an arrest. Call {x.get('tip_phone')} or submit a tip at 469tips.com. You stay anonymous.",
                 f"📍 {city_name}, TX", "Share this post 🔁"]
        headline = truncate(f"{agency_phrase(x.get('agency', 'Police')).replace(' are', '').replace(' is', '')} searching for {x.get('name')}, wanted {charge_phrase(str(x.get('charge', '')))}", 110, "")
        first_comment = f"Source: {x.get('agency')} most wanted {story.url}\n{{photo_credit}}\nTips: {x.get('tip_url')}"
        location = f"{city_name}, TX"
    elif kind == "arrest_log":
        entries = story.extra.get("entries", [])
        lines = [f"Fort Worth arrest log 🚔 Felony bookings, last {story.title.split('last ')[-1] if 'last ' in story.title else '24 hours'}"]
        lines += [f"• {e.get('name')}{', ' + str(e['age']) if e.get('age') else ''} — {e.get('charge') or 'charges pending'}" for e in entries[:8]]
        lines += [settings.brand.get("crime", {}).get("disclaimer", "All suspects are presumed innocent until proven guilty."), cta]
        headline = f"{len(entries)} felony arrests in Fort Worth over the last 24 hours"
        first_comment = f"Source: Fort Worth Police Department public arrest records {story.url}\n{{photo_credit}}"
        image_query = "police car lights night"
    elif kind == "culture":
        lines = [story.title.strip(), f"📍 {location}", cta]
        headline = truncate(re.sub(r"[^\w\s,.'&:/()-]", "", story.title).strip(), 110, "") or truncate(story.extra.get("name") or story.title, 110, "")
        first_comment = (f"More: {story.url}\n" if story.url else "") + "{photo_credit}\nDM us your videos & photos 📲"
        image_query = story.extra.get("image_query", image_query)
    elif kind == "submission":
        credit = story.extra.get("credit") or "a viewer"
        where = story.extra.get("where") or location
        kind_word = "Photo" if story.extra.get("photo") else "Video"
        lines = [truncate(_tidy(story.summary or story.title), 400, "…"), f"📍 {where}", f"🎥 {kind_word}: {credit}", cta]
        headline = truncate(story.title, 110, "")
        first_comment = f"🎥 {credit}\n{{photo_credit}}\nDM us your videos & photos 📲"
    elif kind == "video":
        channel = story.extra.get("channel") or story.source
        lead = _first_sentence(story.summary or "", 200)
        lines = [f"WATCH: {truncate(story.title, 140, '')}"] + ([lead] if lead and not _similar(story.title, lead) else []) + [f"Video: {channel} on YouTube"]
        headline = truncate(story.title, 110, "")
        first_comment = f"Source: {channel} on YouTube {story.url}"
    elif kind == "reddit":
        lines = ["Trending on r/FortWorth 👀", truncate(story.title, 140), f"📍 {location}", cta]
    else:
        title_line = truncate(story.title, 120, "")
        if is_somber(story):
            lines = [f"🚨 {title_line}"]
            cta = f"We'll share updates as police release them. Follow {handle} 📲"
        else:
            lines = [hook_for(story, category), title_line]
        if story.summary and story.summary.lower()[:40] != story.title.lower()[:40]:
            lines.append(truncate(story.summary, 230))
        lines += [f"📍 {location}", cta]

    hashtags = settings.hashtags_for(category)
    if kind == "wanted":
        hashtags = ["#Wanted", "#CrimeStoppers"] + hashtags
    if kind in ("rss", "reddit"):
        image_query = topic_image_query(story, image_query)
    if (settings.brand.get("caption", {}) or {}).get("style", "dallas") == "dallas":
        lines = dallas_caption(story, settings, now, category)
    return PostCopy(
        skip=False, skip_reason="", category=category if category in CATEGORIES else "other",
        headline=headline, caption="\n\n".join(l for l in lines if l), first_comment=first_comment,
        hashtags=hashtags, image_query=image_query, location=location,
    )


# --------------------------------------------------------------------------- finalize
def finalize(copy: PostCopy, story: Story, settings: Settings) -> PostCopy:
    cap_cfg = settings.brand.get("caption", {}) or {}
    caption = URL_RE.sub("", copy.caption)
    caption = HASHTAG_RE.sub("", caption)
    caption = re.sub(r"[ \t]+\n", "\n", caption)
    caption = re.sub(r"\n{3,}", "\n\n", caption).strip()
    if len(caption) > 900:
        caption = truncate(caption, 900)
    if not cap_cfg.get("emoji", True):
        caption = EMOJI_RE.sub("", caption)
        caption = re.sub(r"[ \t]+\n", "\n", caption)
        caption = re.sub(r"\n[ \t]+", "\n", caption)          # "📍 Keller" -> "Keller", not " Keller"
        caption = re.sub(r"[ \t]{2,}", " ", caption).strip()
    if cap_cfg.get("style", "dallas") == "dallas":
        handle = settings.brand.get("instagram_handle") or settings.brand.get("handle", "")
        cta = str(cap_cfg.get("cta") or "").format(instagram_handle=handle, handle=settings.brand.get("handle", handle)).strip()
        if cta and handle and handle.lower() not in caption.lower():
            caption = f"{caption}\n\n{cta}".strip()
    tags = [clean_hashtag(t) for t in copy.hashtags] if cap_cfg.get("hashtags", False) else []
    tags = [t for t in tags if t]
    text = story.text()
    if cap_cfg.get("hashtags", False):
        for topic, topic_tags in TOPIC_HASHTAGS.items():
            if topic in text:
                tags.extend(t for t in topic_tags if t not in tags)
        for t in settings.hashtags_for(copy.category):
            if t not in tags:
                tags.append(t)
    seen: set[str] = set()
    tags = [t for t in tags if not (t.lower() in seen or seen.add(t.lower()))][:8]
    first_comment = copy.first_comment.strip()
    if story.extra.get("credit") and story.extra["credit"] not in first_comment:
        first_comment = f"🎥 {story.extra['credit']}\n" + first_comment       # submitted clips are credited here, not in the caption
    if story.url and story.url not in first_comment and story.source_kind != "culture":
        first_comment = f"Source: {story.source} {story.url}\n" + first_comment
    tag = story.extra.get("social_tag")
    if tag and tag not in first_comment:
        first_comment = first_comment.replace(f"Source: {story.source} ", f"Source: {story.source} {tag} ", 1) if f"Source: {story.source} " in first_comment else f"{tag}\n" + first_comment
    if "{photo_credit}" not in first_comment:
        first_comment += "\n{photo_credit}"
    headline = re.sub(r"[#@]", "", copy.headline).strip().rstrip(".")
    if story.source_kind in ("rss", "video") and not story.official:
        headline = strip_section_label(headline)
    headline = smart_headline(headline, 120) if len(headline) > 120 else headline
    return copy.model_copy(update={"caption": caption, "hashtags": tags, "first_comment": first_comment,
                                   "headline": headline or smart_headline(story.title, 110)})


# an outlet's section label is not part of the headline: FOX 4's "Dallas Weather: First freeze warning of the season takes
# effect tonight across parts of North Texas" went on a Fort Worth card with "Dallas Weather:" in front (Nov 24)
_SECTION_LABEL_RE = re.compile(r"^(?:(?:Dallas|DFW|Dallas-Fort Worth|North Texas|Fort Worth|Texas|FOX 4|NBC 5|NBC DFW|WFAA|CBS Texas|"
                               r"CBS News Texas|KERA|KXAN|KHOU|KVUE|KENS)\s+)?(?:Weather|Traffic|First Alert|Weather Alert|Weather Live|"
                               r"Weather Update)\s*(?:Live|Update|Alert)?\s*:\s+(?=[A-Z0-9\"“‘'])")


def strip_section_label(headline: str) -> str:
    out = _SECTION_LABEL_RE.sub("", headline or "")
    return out if len(out.split()) >= 4 else headline


def cut_off(text: str) -> bool:
    """A feed teaser that stops mid-sentence: 'Kyrie Irving scored 25 points ... to beat the Los Angeles...'."""
    t = collapse_ws(text or "").rstrip()
    return bool(t) and (t.endswith(("...", "…", "[…]")) or not t.endswith((".", "!", "?", '"', "”", "’", ")")))


def salvage_lead(text: str, min_words: int = 8) -> str:
    """The complete opening clause of a wire lead the feed cut off, ended with a period: 'Joaquín Valiente scored two
    second-half goals in a 2-minute span, Samuel Sarver added ... beat the Portland Timbers 3-0 in Game 1...' ->
    'Joaquín Valiente scored two second-half goals in a 2-minute span.' Only for game recaps (the score is on the card);
    a news lead cut at a comma can drop the part that matters ('The fire was contained, but two firefighters ...')."""
    t = re.sub(r"\s*(\.\.\.|…|\[…\])\s*$", "", collapse_ws(text or ""))
    t = _DATELINE_RE.sub("", t)
    cut = t.rfind(", ")
    while cut > 0:
        head = t[:cut].rstrip(" ,;:")
        if (len(head.split()) >= min_words and head.count('"') % 2 == 0 and head.count("“") == head.count("”")
                and not _APPOSITIVE_RE.search(head) and _GAME_VERB_RE.search(head)):
            return head + "."
        cut = t.rfind(", ", 0, cut)
    return ""


# "Dak Prescott, who threw for 300 yards" is a subject without its verb; a recap's first clause always has a game verb
_APPOSITIVE_RE = re.compile(r",\s+(?:who|whom|whose|which|a|an|the|one of|including|along with|coming off)\b", re.I)
_GAME_VERB_RE = re.compile(r"\b(scored|had|beat|beats|led|won|lost|threw|ran|rushed|caught|added|made|hit|homered|pitched|struck out|finished|"
                           r"rallied|defeated|topped|edged|routed|held|blanked|shut out|outlasted|stunned|upset|clinched|knocked|kicked|"
                           r"sank|drained|tallied|posted|recorded|picked off|intercepted|blocked|saved|stopped)\b", re.I)


_ALERT_WHEN_RE = re.compile(r"\*\s*WHEN\.\.\.\s*(.+?)(?=\s*\*|\.\s|$)", re.S)


def alert_when(summary: str, ends: str | None, now: datetime, tz) -> str:
    """When an alert is in force, with its day: NWS's own "WHEN...From 11 PM Tuesday to 9 AM CST Wednesday" when the text
    has it, else "until 9:00 AM Wednesday". A bare "until 9:00 AM" on a Monday read as tomorrow morning for a freeze that
    starts Tuesday night (Nov 23)."""
    m = _ALERT_WHEN_RE.search(summary or "")
    if m:
        when = re.sub(r"\s+(?:CST|CDT|CT)\b", "", m.group(1).strip().rstrip("."))
        return " " + when[0].lower() + when[1:]
    if not ends:
        return ""
    end = dtparse.isoparse(ends)
    day = relative_day(end, now, tz)
    day = "" if day in ("Today", "Tonight") else (" tomorrow" if day == "Tomorrow" else " " + day.replace("This ", ""))
    return f" until {fmt_time(end, tz)}{day}"


def alert_image_query(event: str) -> str:
    """A stock-photo search for the alert's weather: a Freeze Warning searched "storm clouds Texas" (Nov 23)."""
    low = (event or "").lower()
    if any(w in low for w in ("snow", "ice", "sleet", "winter", "blizzard")):
        return "snow ice road Texas"
    if any(w in low for w in ("freeze", "frost", "wind chill", "cold")):
        return "frost on grass"
    if "heat" in low:
        return "Texas summer sun heat"
    if "fog" in low:
        return "fog morning road"
    if "wind" in low:
        return "wind trees blowing"
    if any(w in low for w in ("fire", "red flag")):
        return "dry grass field Texas"
    return "storm clouds Texas"


def alert_area(area: str, short: bool = False) -> str:
    """"Montague; Cooke; ...; Coryell" as a reader says it; the short form leads with Tarrant County."""
    parts = [a.strip() for a in (area or "").split(";") if a.strip()]
    if not parts:
        return "Tarrant County"
    if short and len(parts) > 4:
        lead = "Tarrant" if "Tarrant" in parts else parts[0]
        return f"{lead} and {len(parts) - 1} other North Texas counties"
    if len(parts) == 1:
        one = parts[0]
        return one if "," in one or one.lower().endswith(("county", "counties")) else f"{one} County"
    return ", ".join(parts[:-1]) + f" and {parts[-1]} counties"


_TODAY_RE_FMT = r"\b(?:{wd},?\s+)?(?:{mon}\.?|{month})\s+{day}\b"


def restate_relative_day(caption: str, text: str, now: datetime, tz) -> str:
    """A story written last week says the event is "next week" and names its date. When that date is today, "next week" is
    stale: Nov 23, CBS Texas's Cowboys blood drive "at AT&T Stadium in Arlington next week ... scheduled for Monday, Nov. 23"."""
    if "next week" not in (caption or "").lower():
        return caption
    local = now.astimezone(tz)
    pattern = _TODAY_RE_FMT.format(wd=local.strftime("%A"), mon=local.strftime("%b"), month=local.strftime("%B"), day=local.day)
    if not re.search(pattern, f"{caption} {text}", re.I):
        return caption
    return re.sub(r"\bnext week\b", "today", caption, flags=re.I)


# a quote's attribution: the closing quote, then a bare capitalized surname and the verb ('...that work," Wilson said.')
_BARE_SAID_RE = re.compile(r"[,.!?…]\s?[\"”’]\s+([A-Z][a-z]+(?:-[A-Z][a-z]+)?) (?:said|says|told|added|noted|explained)\b")
_ROLE_TITLE = r"(?:Superintendent|Mayor|Police Chief|Fire Chief|Chief|Coach|Trustee|Commissioner|Councilmember|Council member|" \
              r"President|Sen\.|Senator|Rep\.|Representative|Gov\.|Governor|Judge|Sheriff|Officer|Sgt\.|Lt\.|Dr\.|Pastor|Principal)"
# capitalized words that sit before a name-like word without being a first name ("Fort Worth Police said")
_NOT_FIRST_NAMES = {"Fort", "Worth", "North", "South", "East", "West", "Texas", "Tarrant", "Dallas", "Arlington", "County", "City",
                    "Police", "Fire", "Department", "District", "School", "State", "University", "The", "A", "An", "In", "On", "At",
                    "And", "But", "For", "With", "From", "After", "Before", "When", "While", "New", "Old", "Lake", "River"}


def introduce_speakers(caption: str, text: str) -> str:
    """A quote credited to a bare surname whose first reference was left out: Nov 23, the Fort Worth Report's Keller ISD bond
    story ended "... a bond is critical to that work," Wilson said, after the sentence naming Superintendent Cory Wilson was
    too long to keep. The surname takes its full first reference from the article ("Superintendent Cory Wilson said")."""
    out = caption or ""
    for m in list(_BARE_SAID_RE.finditer(out)):
        surname = m.group(1)
        if any(f.group(1) not in _NOT_FIRST_NAMES
               for f in re.finditer(r"\b([A-Z][a-z]+)(?: [A-Z]\.)? " + re.escape(surname) + r"\b", out[:m.start(1)])):
            continue                                            # already introduced earlier in the caption
        for f in re.finditer(r"\b((?:" + _ROLE_TITLE + r"\s+)?([A-Z][a-z]+)(?: [A-Z]\.)? " + re.escape(surname) + r")\b", text or ""):
            if f.group(2) in _NOT_FIRST_NAMES:
                continue
            out = out[:m.start(1)] + f.group(1) + out[m.end(1):]
            break
        break                                                   # one speaker per caption: the offsets above moved
    return out


# an announcement that only tells the reader to do something, with no time and no place, is the organizer's ad copy: Nov 24,
# the City of Arlington's "Discover Unique Stories at the 'People Library' on Dec. 5" captioned only "“Borrow” time with
# community members ... Ask questions, share conversations and discover new perspectives."
_IMPERATIVE_START_RE = re.compile(r"^[“\"‘']?(?:Borrow|Ask|Join|Discover|Come|Enjoy|Celebrate|Learn|Bring|Visit|Explore|Get|Register|"
                                  r"Sign up|Grab|Don't miss|Don’t miss|Mark your calendars?|Experience|Shop|Try|Find|Meet|Take|"
                                  r"Stop by|Head (?:out|over|to)|Check out|Listen|Watch|Share|Connect|Hear|Spend|Treat|Gather|Savor|"
                                  r"Unwind|Escape|Make|Start|Kick off|Ring in|Support|Volunteer|Donate|Reserve|RSVP)\b", re.I)
_WHEN_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:a\.?m\.?|p\.?m\.?)|\bnoon\b|\bmidnight\b|"
                      r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b|"
                      r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}\b", re.I)
_WHERE_RE = re.compile(r"\b(?:at|in|on)\s+(?:the\s+)?[A-Z][A-Za-z.'’&-]+")


def promo_blurb(caption: str) -> bool:
    sentences = [x.strip() for x in _split_sentences(collapse_ws(caption or "")) if x.strip()]
    return (bool(sentences) and all(_IMPERATIVE_START_RE.match(x) for x in sentences)
            and not _WHEN_RE.search(caption or "") and not _WHERE_RE.search(caption or ""))


def write_copy(story: Story, settings: Settings, now: datetime, *, force_template: bool = False) -> tuple[PostCopy, str]:
    if (story.source_kind == "rss" and not story.official and (story.category or "") == "sports"
            and not _sentences(story.summary or "") and cut_off(story.summary or "")):
        lead = salvage_lead(story.summary or "")
        if lead and _sentences(lead):
            story.summary = lead                  # the wire recap's first clause; the score itself is the card's headline
    if story.source_kind == "rss" and not story.official and _CLIP_LEAD_RE.match(story.summary or ""):
        # "Watch Titans rookie Carnell Tate score a wild 59-yard touchdown ...": the page is a highlight clip, and a card
        # cannot play it (Nov 22, CBS Sports, render 127)
        return PostCopy(skip=True, skip_reason="a video highlight page: its point is a clip we cannot show", category=story.category or "other",
                        headline=truncate(story.title, 110, ""), caption="", first_comment="", hashtags=[], image_query="", location=""), "template"
    if story.source_kind == "rss" and not story.official and (personnel_press_release(story.summary or "") or
                                                              press_release(story.summary or "")):
        return PostCopy(skip=True, skip_reason="a company press release", category=story.category or "other",
                        headline=truncate(story.title, 110, ""), caption="", first_comment="", hashtags=[], image_query="", location=""), "template"
    if story.source_kind == "rss" and not story.official and stale_meeting_recap(story, now):
        return PostCopy(skip=True, skip_reason="a meeting recap more than a week old", category=story.category or "other",
                        headline=truncate(story.title, 110, ""), caption="", first_comment="", hashtags=[], image_query="", location=""), "template"
    if story.source_kind == "rss" and not story.official and not _sentences(story.summary or ""):
        # the feed gave a headline and nothing to say under it: a post that is its own headline is not a post
        return PostCopy(skip=True, skip_reason="no summary to post: the feed gave only a headline", category=story.category or "other",
                        headline=truncate(story.title, 110, ""), caption="", first_comment="", hashtags=[], image_query="", location=""), "template"
    copy, writer = None, "template"
    if settings.writer != "template" and not force_template:
        copy = claude_code_copy(story, settings, now)
        writer = "claude-code"
        if copy is None:
            copy, writer = claude_copy(story, settings, now), "claude-api"
    if copy is None:
        copy, writer = template_copy(story, settings, now), "template"
    if copy.skip:
        return copy, writer
    out = finalize(copy, story, settings)
    out.caption = restate_relative_day(out.caption, story.summary or "", now, settings.tz)
    out.caption = introduce_speakers(out.caption, story.summary or "")
    if story.source_kind == "rss" and promo_blurb(out.caption):
        return out.model_copy(update={"skip": True, "skip_reason": "a promotional blurb: it only tells the reader to do something, "
                                                                     "with no time and no place"}), writer
    return out, writer
