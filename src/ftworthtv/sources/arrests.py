"""Fort Worth PD public arrest log (pdapps.fortworthtexas.gov "Recent Arrests"): names, ages, charges, booking times.

No photos are published there. We turn the felony bookings of the last day into one "arrest log" roundup post,
the way DFW news pages do. Off by default in config: it is public record, but it names people who have only been
accused, so decide deliberately.
"""
from __future__ import annotations

import html as htmllib
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil import parser as dtparse

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import truncate

log = logging.getLogger(__name__)

URL = "https://pdapps.fortworthtexas.gov/OnlineServices/Reports/RecentArrests"
ENTRY_RE = re.compile(r'<div class="box post">(.*?)</div>\s*</section>', re.S)
DEGREE_RE = re.compile(r"-(F1|F2|F3|SJF|MA|MB|MC)\b")
FELONY_WORDS = ("murder", "capital", "manslaughter", "aggravated", "agg ", "robbery", "burglary", "sexual", "indecency",
                "child", "kidnap", "deadly", "trafficking", "arson", "evading", "firearm", "weapon", "injury to", "stalking")
SEVERITY = {"F1": 5, "F2": 4, "F3": 3, "SJF": 2, "MA": 1, "MB": 0, "MC": 0}


def _lines(block: str) -> list[str]:
    text = re.sub(r"<br\s*/?>", "\n", block)
    text = re.sub(r"<[^>]+>", "", text)
    text = htmllib.unescape(text)
    return [l.strip() for l in text.splitlines() if l.strip()]


def parse_entries(page_html: str) -> list[dict]:
    entries: list[dict] = []
    for block in ENTRY_RE.findall(page_html):
        lines = _lines(block)
        if not lines:
            continue
        entry = {"name": lines[0], "age": None, "sex_race": "", "booked": None, "charges": [], "status": "", "degree": "MC"}
        m = re.match(r"([A-Z]/[A-Z])\s*\((\d+)\s*YOA\)", lines[1] if len(lines) > 1 else "")
        if m:
            entry["sex_race"], entry["age"] = m.group(1), int(m.group(2))
        in_charges = False
        for line in lines[1:]:
            if line.startswith("Booking Date/Time:"):
                try:
                    entry["booked"] = dtparse.parse(line.split(":", 1)[1].strip())
                except (ValueError, OverflowError):
                    pass
                continue
            if line.startswith(("Report No:", "Booking No:")):
                continue
            if "Charge(s):" in line:
                in_charges = True
                line = line.split("Charge(s):", 1)[1]
            if "Status:" in line:
                charge, _, status = line.partition("Status:")
                if charge.strip() and in_charges:
                    entry["charges"].append(charge.strip())
                entry["status"] = status.strip()
                in_charges = False
                continue
            if in_charges and line:
                entry["charges"].append(line.strip())
        degrees = [d for c in entry["charges"] for d in DEGREE_RE.findall(c)]
        if degrees:
            entry["degree"] = max(degrees, key=lambda d: SEVERITY.get(d, 0))
        elif any(w in " ".join(entry["charges"]).lower() for w in FELONY_WORDS):
            entry["degree"] = "F3"
        entries.append(entry)
    return entries


def clean_charge(charge: str) -> str:
    """'PC 22.02(a)(1)  Aggravated Assault causes serious bodily injury-Family violence-F2-$25,000.00' -> 'Aggravated assault causes serious bodily injury (family violence)'"""
    c = re.sub(r"^(PC|HSC|TC|TRC|CCP|GC|PEN|TPC|ALCB|FC|HS)\s*[\d.()a-zA-Z-]*\s*", "", charge.strip())
    c = re.sub(r"-\$[\d,.]+$", "", c)
    c = DEGREE_RE.sub("", c)
    c = re.sub(r"\s+", " ", c).strip(" -")
    return c[:90]


def felony_bookings(entries: list[dict], since: datetime, min_degree: str = "F3") -> list[dict]:
    threshold = SEVERITY.get(min_degree, 3)
    out = []
    for e in entries:
        if not e["booked"] or e["booked"] < since:
            continue
        if SEVERITY.get(e["degree"], 0) < threshold:
            continue
        out.append(e)
    return sorted(out, key=lambda e: (-SEVERITY.get(e["degree"], 0), e["booked"]), reverse=False)


def roundup_story(entries: list[dict], now: datetime, tz: ZoneInfo, cfg: dict) -> Story | None:
    local = now.astimezone(tz)
    since = (local - timedelta(hours=int(cfg.get("window_hours", 24)))).replace(tzinfo=None)
    picked = felony_bookings(entries, since, cfg.get("min_degree", "F3"))[: int(cfg.get("max_entries", 8))]
    if len(picked) < int(cfg.get("min_entries", 3)):
        return None
    lines = []
    for e in picked:
        who = e["name"].title()
        age = f", {e['age']}" if e.get("age") else ""
        charge = clean_charge(e["charges"][0]) if e["charges"] else "charges pending"
        more = f" (+{len(e['charges']) - 1} more)" if len(e["charges"]) > 1 else ""
        lines.append(f"• {who}{age} — {charge}{more}")
    return Story(
        id=f"arrests-{local.date().isoformat()}",
        source="Fort Worth Police Department",
        source_kind="arrest_log",
        title=f"Fort Worth arrest log: {len(picked)} felony bookings in the last {int(cfg.get('window_hours', 24))} hours",
        summary="\n".join(lines),
        url=URL,
        published=now,
        category_hint="crime",
        image_policy="none",
        official=True,
        always_relevant=True,
        weight=float(cfg.get("weight", 0.8)),
        extra={"entries": [{"name": e["name"].title(), "age": e["age"], "charge": clean_charge(e["charges"][0]) if e["charges"] else "",
                            "degree": e["degree"], "status": e["status"]} for e in picked], "total_scanned": len(entries)},
    )


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("arrest_log", {}) or {}
    if settings.offline or not cfg.get("enabled", False):
        return []
    resp = http.get(cfg.get("url", URL), headers={"Accept": "text/html"})
    entries = parse_entries(resp.text)
    log.info("arrest log: %d bookings on the page", len(entries))
    story = roundup_story(entries, now, settings.tz, cfg)
    return [story] if story else []
