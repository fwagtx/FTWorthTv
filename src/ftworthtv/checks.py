"""Pre-publish checks: nothing goes out that its source does not support.

Two passes. After the caption is written (phase 1): every caption sentence, number and quotation must be found in the
story's own text (title, summary, article lead, structured fields); a Claude caption that fails is replaced by the
template caption, which is composed from the source's sentences, and a story that still fails is skipped.
Right before publishing (phase 2): the source link must still answer (a pulled article is never promoted), and a wanted
bulletin's agency page is read again so a captured fugitive is never posted.
"""
from __future__ import annotations

from pathlib import Path

import logging
import re
from urllib.parse import urlparse

from .models import PostCopy, PostDraft, Story

log = logging.getLogger(__name__)

_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "after", "as", "by", "is", "are", "was",
         "were", "be", "been", "from", "its", "it", "this", "that", "these", "those", "new", "says", "say", "said", "will",
         "over", "into", "up", "out", "than", "then", "when", "who", "what", "which", "has", "have", "had", "not", "but",
         "his", "her", "their", "they", "them", "she", "he", "we", "you", "our", "also", "about", "more", "most", "now",
         "one", "two", "three", "first", "last", "next", "year", "years", "week", "day", "days", "today", "tonight",
         "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "fort", "worth", "texas", "tx",
         "told", "according", "officials", "police", "city", "county", "there", "here", "where", "still", "just", "some",
         "would", "could", "should", "may", "might", "because", "while", "since", "until", "before", "being", "well",
         "even", "much", "many", "each", "both", "all", "any", "own", "same", "other", "such", "only", "very", "can",
         "does", "did", "do", "if", "so", "no", "yes", "per", "like", "get", "got", "goes", "going", "went", "comes",
         "came", "come", "between", "through", "during", "against", "under", "around", "across", "off", "down", "back",
         "every", "within", "without", "least", "another", "again", "far", "away", "ahead", "near", "stay", "stays"}
_QUOTE_RE = re.compile(r'"([^"]{12,}?)"|“([^”]{12,}?)”|(?:^|(?<=[\s(]))\'([^\']{12,}?)\'(?=[\s.,;:!?)]|$)|(?:^|(?<=[\s(]))‘([^’]{12,}?)’(?=[\s.,;:!?)]|$)')
_NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'-]{3,}", _norm(text)) if w.strip("'-") not in _STOP]


def _stem(w: str) -> str:
    w = w.strip("'-")
    for suf in ("'s", "ies", "ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“‘(])", (text or "").replace("\n", " "))
    return [p.strip() for p in parts if len(p.strip()) > 20]


def source_text(story: Story) -> str:
    """Everything the writer was allowed to know: title, summary, article lead and the structured fields."""
    parts = [story.title or "", story.summary or ""]
    for k, v in (story.extra or {}).items():
        if isinstance(v, (str, int, float)) and k not in ("scope", "feed_title", "image_query"):
            parts.append(str(v))
        elif isinstance(v, list):
            parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
        elif isinstance(v, dict):
            parts.extend(str(x) for x in v.values() if isinstance(x, (str, int, float)))
    return _norm(" ".join(parts))


# fixed wording the template writer adds around the facts (tip lines, ticket lines, sign-offs): not claims about the story
TEMPLATE_PHRASES = ("crime stoppers", "submit a tip", "you stay anonymous", "tickets in the comments", "stay safe out there",
                    "national weather service", "good morning, fort worth", "this weekend in fort worth", "dm us", "follow ",
                    "share this post", "presumed innocent", "charges are accusations", "we'll share updates")
STRUCTURED_KINDS = ("nws_alert", "nws_forecast", "event", "event_roundup", "wanted", "arrest_log", "culture", "video", "submission")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")


def _digits(text: str) -> set[str]:
    return {d.lstrip("0") or "0" for d in re.findall(r"\d[\d,]*(?:\.\d+)?", text.replace(",", ""))}


def caption_problems(copy: PostCopy, story: Story, *, min_ratio: float = 0.6, writer: str | None = None) -> list[str]:
    """Why a caption cannot go out: a sentence, number or quotation the source does not contain.
    Template captions for structured sources (alerts, forecasts, events, wanted bulletins) are built from the fields
    themselves, so only their numbers and quotations are checked."""
    src = source_text(story)
    src_stems = {_stem(w) for w in _words(src)}
    src_digits = _digits(src)
    problems: list[str] = []
    caption = copy.caption or ""
    check_sentences = not (writer == "template" and story.source_kind in STRUCTURED_KINDS)
    for sent in _sentences(caption) if check_sentences else []:
        low = _norm(sent)
        if any(p in low for p in TEMPLATE_PHRASES):
            continue
        words = [_stem(w) for w in _words(sent)]
        if len(words) >= 3:
            hit = sum(1 for w in words if w in src_stems)
            if hit / len(words) < min_ratio:
                problems.append(f"sentence not supported by the source: {sent[:80]!r}")
    for num in _NUMBER_RE.findall(_TIME_RE.sub(" ", caption)):     # clock times are formatted by us, not quoted
        bare = (num.strip("$%").replace(",", "")).lstrip("0") or "0"
        if bare not in src_digits and bare.rstrip("0").rstrip(".") not in src_digits:
            problems.append(f"number not in the source: {num}")
    for groups in _QUOTE_RE.findall(caption):
        quote = next((g for g in groups if g), "")
        q = _norm(quote).strip(" .,")
        if len(q.split()) >= 3 and q not in src:
            problems.append(f"quotation not in the source: {quote[:60]!r}")
    problems += weekday_mismatches(caption, story.published)
    return problems


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_WEEKDAY_DATE_RE = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                              r"[a-z]*\.?\s+(\d{1,2})\b")


def weekday_mismatches(text: str, published=None) -> list[str]:
    """'until 6 a.m. Monday, Nov. 26' in a story published Nov 22, 2026 (a Sunday): Nov. 26 is a Thursday. A weekday that
    disagrees with its date means one of them is wrong (often a recycled article), and the page must not repeat it."""
    from datetime import date, datetime, timezone
    ref = (published or datetime.now(timezone.utc)).date() if hasattr(published or datetime.now(timezone.utc), "date") else date.today()
    out = []
    for wd, mon, day in _WEEKDAY_DATE_RE.findall(text or ""):
        m, d = _MONTHS[mon.lower()[:3]], int(day)
        for year in (ref.year, ref.year + 1, ref.year - 1):
            try:
                when = date(year, m, d)
            except ValueError:
                continue
            if abs((when - ref).days) <= 200:
                if _WEEKDAYS[when.weekday()] != wd.lower():
                    out.append(f"weekday and date disagree: {wd}, {mon} {d} is a {_WEEKDAYS[when.weekday()].title()} in {year}")
                break
    return out


def source_alive(url: str, *, timeout: int = 20) -> str | None:
    """A pulled article (404/410) or a link that now lands on a homepage must not be promoted; bot walls (403) are not
    evidence of anything, and a network error is reported, not treated as a dead link."""
    if not url:
        return None
    try:
        from . import http
        resp = http.session().get(url, timeout=timeout, allow_redirects=True)
    except Exception as exc:
        log.warning("source check could not reach %s: %s", url, exc)
        return None
    if resp.status_code in (404, 410):
        return f"source link returns {resp.status_code}"
    final = urlparse(resp.url or url)
    if urlparse(url).path.strip("/") and not final.path.strip("/"):
        return "source link now redirects to the homepage"
    return None


def wanted_still_listed(story: Story, *, timeout: int = 20) -> str | None:
    """Read the agency's page again: a fugitive who was caught since the run began is never posted."""
    name = str((story.extra or {}).get("name") or "").strip()
    if story.source_kind != "wanted" or not name or not story.url:
        return None
    try:
        from . import http
        page = _norm(http.session().get(story.url, timeout=timeout).text)
    except Exception as exc:
        log.warning("wanted check could not read %s: %s", story.url, exc)
        return None
    page = re.sub(r"<[^>]+>", " ", page)
    tokens = [t for t in _norm(name).split() if len(t) > 1]
    if not all(t in page for t in tokens):
        return f"{name} is no longer listed on the agency's page"
    return None


OWN_PHOTO_PROVIDERS = ("source", "nws", "ticketmaster", "camera", "placeholder", "card", "quote")


def photo_subject_problem(draft: PostDraft) -> str | None:
    """A library or stock photo must still show what the headline is about (checked again at publish time)."""
    if draft.mode != "photo" or not draft.image or draft.image.provider in OWN_PHOTO_PROVIDERS:
        return None
    from .images.subject import subject_fits
    ok, why = subject_fits(draft.story.title, draft.story.text(), draft.copy.category, draft.image.subject, kind=draft.story.source_kind)
    return None if ok else f"photo does not show the subject: {why}"


def preflight(draft: PostDraft, *, network: bool = True) -> list[str]:
    """Everything that must hold right before a post is handed to the publisher."""
    problems = caption_problems(draft.copy, draft.story, writer=draft.writer)
    if network:
        dead = source_alive(draft.story.url)
        if dead:
            problems.append(dead)
        gone = wanted_still_listed(draft.story)
        if gone:
            problems.append(gone)
    if draft.mode == "photo" and draft.image is None:
        problems.append("photo post without an image")
    wrong = photo_subject_problem(draft)
    if wrong:
        problems.append(wrong)
    if draft.mode == "video" and not draft.video_url and not (draft.video_path and Path(draft.video_path).exists()):
        problems.append("video post without a clip")
    return problems
