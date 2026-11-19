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


def _tidy(sentence: str) -> str:
    text = collapse_ws(sentence).rstrip(" .")
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.85:   # ALL-CAPS press-release title
        text = " ".join(w if (len(w) <= 3 and w.isupper() and w not in ("NEW", "AND", "THE", "FOR")) else w.capitalize() for w in text.split())
    return text


BOILERPLATE = ("newsletter", "subscribe", "sign up", "inbox", "click here", "read more", "learn more", "stay informed", "follow us", "check back",
               "enjoy reading the news again", "welcome to the", "pick something out of this list", "this article", "photo by", "courtesy of",
               "biweekly", "weekly column", "in this week", "scroll down",
               "sponsored", "advertis", "click to", "watch the video", "see the full", "continue reading", "appeared first on",
               "the post ", "related:", "more:", "also read")


def _first_sentence(text: str, limit: int = 170) -> str:
    text = collapse_ws(text)
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    first = (m.group(1) if m else text).strip()
    if any(w in first.lower() for w in BOILERPLATE) or len(first) < 25:
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


def _sentences(text: str, max_n: int = 4, limit: int = 220, lead: int = 650) -> list[str]:
    """Complete, boilerplate-free sentences from the lead of an article summary, in order (later paragraphs of a scraped
    page can belong to another item, so only the first `lead` characters are considered)."""
    out: list[str] = []
    text = collapse_ws(text or "")
    if len(text) > lead:
        cut = text.rfind(". ", 0, lead)
        text = text[:cut + 1] if cut > 0 else text[:lead]
    for part in _split_sentences(text):
        if len(part) < 25 or len(part) > limit or not part.endswith((".", "!", "?", '"', "”", "’", ")")) or len(part.split()) < 6:
            continue
        if any(w in part.lower() for w in BOILERPLATE) or part.endswith(("…", "...")):
            continue
        if any(_similar(part, prev) for prev in out):     # og:description often repeats the first paragraph
            continue
        out.append(part)
        if len(out) >= max_n:
            break
    return out


def _similar(a: str, b: str) -> bool:
    """Does sentence b just restate title a? (RSS summaries often open with the title.)"""
    wa = {w for w in re.findall(r"[a-z0-9']+", a.lower()) if len(w) > 2}
    wb = {w for w in re.findall(r"[a-z0-9']+", b.lower()) if len(w) > 2}
    if not wa or not wb:
        return False
    return a.lower()[:30] == b.lower()[:30] or len(wa & wb) / len(wa | wb) >= 0.5


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
    if kind == "nws_alert":
        ends = x.get("ends")
        until = f" until {fmt_time(dtparse.isoparse(ends), settings.tz)}" if ends else ""
        instr = _first_sentence(x.get("instruction", "")) if x.get("instruction") else ""
        return [f"The National Weather Service has issued a {x.get('event', 'weather alert')} for {x.get('area', 'Tarrant County')}{until}.", instr]
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
        return [f"{agency_phrase(x.get('agency', 'Police'))} looking for {x.get('name')}, wanted for {str(x.get('charge', '')).lower()}. "
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
    first = _tidy(story.title)
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
    ("thanksgiving", "Thanksgiving dinner table"), ("christmas", "Christmas lights downtown"), ("halloween", "Halloween decorations"),
    ("police", "police car lights"), ("arlington", "Arlington Texas downtown"), ("haslet", "Fort Worth suburb"), ("keller", "Keller Texas"),
]


def topic_image_query(story: Story, default: str) -> str:
    text = story.text()
    for key, query in TOPIC_IMAGE_QUERIES:
        if key in text:
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
    headline = _tidy(smart_headline(story.title, 110))

    if kind == "nws_alert":
        ends = story.extra.get("ends")
        until = f" until {fmt_time(dtparse.isoparse(ends), settings.tz)}" if ends else ""
        lines = [f"⚠️ {story.extra.get('event', 'Weather Alert')} for {story.extra.get('area', 'Tarrant County')}{until}"]
        if story.extra.get("instruction"):
            lines.append(truncate(story.extra["instruction"], 220))
        lines += ["Stay safe out there, Fort Worth 💜", cta]
        headline = truncate(f"{story.extra.get('event', 'Weather alert')} issued for {story.extra.get('area', 'Tarrant County')}{until}", 110, "")
        first_comment = f"Source: National Weather Service {story.url}\n{{photo_credit}}"
        image_query = "storm clouds Texas"
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
                 f"Wanted by the {x.get('agency')} for {x.get('charge')}.",
                 f"Crime Stoppers will pay up to {x.get('reward')} for information leading to an arrest. Call {x.get('tip_phone')} or submit a tip at 469tips.com. You stay anonymous.",
                 f"📍 {city_name}, TX", "Share this post 🔁"]
        headline = truncate(f"{agency_phrase(x.get('agency', 'Police')).replace(' are', '').replace(' is', '')} searching for {x.get('name')}, wanted for {str(x.get('charge', '')).lower()}", 110, "")
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
    if "{photo_credit}" not in first_comment:
        first_comment += "\n{photo_credit}"
    headline = re.sub(r"[#@]", "", copy.headline).strip().rstrip(".")
    headline = smart_headline(headline, 120) if len(headline) > 120 else headline
    return copy.model_copy(update={"caption": caption, "hashtags": tags, "first_comment": first_comment,
                                   "headline": headline or smart_headline(story.title, 110)})


def write_copy(story: Story, settings: Settings, now: datetime, *, force_template: bool = False) -> tuple[PostCopy, str]:
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
    return finalize(copy, story, settings), writer
