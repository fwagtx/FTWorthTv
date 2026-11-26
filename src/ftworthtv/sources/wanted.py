"""WANTED bulletins with official photos: FWPD Most Wanted, Arlington PD "Cash for Crooks", Texas DPS 10 Most Wanted.

These pages exist to be shared: the agency publishes the photo, the name and the charge and asks the public for tips.
That makes them the cleanest "mugshot" content a local news page can run. Juveniles are skipped, every post names
the agency, carries the Crime Stoppers tip line and the presumption-of-innocence disclaimer.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

from .. import http
from ..config import Settings
from ..models import Story
from ..textutil import stable_id, strip_html, truncate

log = logging.getLogger(__name__)

TIP_PHONE = "817-469-TIPS (8477)"
TIP_URL = "https://469tips.com"
LOCAL_WORDS = ("tarrant", "fort worth", "arlington", "north richland hills", "keller", "mansfield", "haltom", "euless", "hurst", "bedford", "grapevine", "southlake")

FWPD_ARTICLE_RE = re.compile(r"<article[^>]*>(.*?)</article>", re.S | re.I)
ARL_RE = re.compile(r'<img[^>]+alt="Wanted fugitive #\d+"[^>]+src="([^"]+)"[^>]*/?>\s*<br\s*/?>\s*(.*?)<br\s*/?>\s*(.*?)</p>', re.S | re.I)
DPS_RE = re.compile(r'<div id="fugDiv(\d+)" class="fugiDiv">(.*?)(?=<div id="fugDiv\d+"|$)', re.S)


def _reward(html: str) -> str:
    m = re.search(r"up to\s*(?:<[^>]+>\s*)*\$\s*([\d,]+)", html, re.I)
    return f"${m.group(1)}" if m else "$2,000"


def _age(dob: str | None, now: datetime) -> int | None:
    if not dob:
        return None
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", dob.strip())
    if not m:
        return None
    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yy < 100:
        yy = 2000 + yy if yy <= now.year - 2000 else 1900 + yy
    try:
        born = datetime(yy, mm, dd, tzinfo=now.tzinfo)
    except ValueError:
        return None
    return int((now - born).days // 365.25)


def parse_fwpd(html: str, base_url: str, now: datetime) -> list[dict]:
    reward = _reward(html)
    people = []
    for block in FWPD_ARTICLE_RE.findall(html):
        img = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
        name = re.search(r'list-item-title"?>\s*(.*?)\s*</h3>', block, re.S | re.I)
        if not img or not name:
            continue
        dob = re.search(r"DOB:\s*(?:</b>)?\s*([\d/]+)", block, re.I)
        charge = re.search(r"Wanted For:\s*(?:</b>)?\s*(.*?)</p>", block, re.S | re.I)
        by = re.search(r"Wanted By:\s*(?:</b>)?\s*(.*?)</p>", block, re.S | re.I)
        tip = re.search(r'href="([^"]+)"[^>]*title="[^"]*TIP', block, re.I)
        people.append({
            "name": strip_html(name.group(1)), "charge": strip_html(charge.group(1)) if charge else "outstanding warrant",
            "wanted_by": strip_html(by.group(1)) if by else "FWPD", "dob": dob.group(1) if dob else None,
            "age": _age(dob.group(1) if dob else None, now),
            "image": urljoin(base_url, img.group(1).split("?", 1)[0]), "reward": reward,
            "tip_url": tip.group(1) if tip else TIP_URL, "details": "",
        })
    return people


def parse_arlington(html: str, base_url: str, now: datetime) -> list[dict]:
    reward = _reward(html)
    return [{"name": strip_html(name), "charge": strip_html(charge) or "outstanding warrant", "wanted_by": "Arlington PD", "dob": None, "age": None,
             "image": urljoin(base_url, src), "reward": reward, "tip_url": TIP_URL, "details": ""}
            for src, name, charge in ARL_RE.findall(html)]


def parse_dps(html: str, base_url: str, now: datetime, local_only: bool = True) -> list[dict]:
    people = []
    for fid, block in DPS_RE.findall(html):
        first = re.search(r'class="fName">\s*(?:<strong>)?\s*(.*?)\s*(?:</strong>)?\s*</span>', block, re.S)
        last = re.search(r'class="lName">\s*(.*?)\s*</span>', block, re.S)
        img = re.search(r'<img[^>]+class="imagePic"[^>]+src="([^"]+)"', block, re.I) or re.search(r'<img[^>]+src="(data:image/[^"]+)"', block, re.I)
        if not (first and last and img):
            continue
        text = strip_html(block)
        if local_only and not any(w in text.lower() for w in LOCAL_WORDS):
            continue
        reward = re.search(r"\$\s*([\d,]+)", text)
        charge = re.search(r"(?:Wanted For|Wanted for|Charges?)[:\s]+(.*?)(?:\s{2,}|Reward|Last|$)", text, re.I)
        people.append({
            "name": f"{strip_html(first.group(1))} {strip_html(last.group(1))}".strip(), "charge": truncate(charge.group(1), 120) if charge else "wanted by Texas DPS",
            "wanted_by": "Texas DPS", "dob": None, "age": None, "image": img.group(1) if img.group(1).startswith("data:") else urljoin(base_url, img.group(1)),
            "reward": f"${reward.group(1)}" if reward else "a cash reward", "tip_url": urljoin(base_url, f"FugitiveDetails?id={fid}"),
            "details": truncate(text, 500),
        })
    return people


PARSERS = {"fwpd": parse_fwpd, "arlington": parse_arlington, "dps": parse_dps}

_SUFFIXES = {"II", "III", "IV", "V"}


def proper_name(name: str) -> str:
    """'Ezequiel MONTEMAYOR' -> 'Ezequiel Montemayor': Arlington's list writes surnames in capitals, and the card and caption
    printed them that way (Nov 23-26). A word already in mixed case stays as written (DeShawn, McKinney); 'MCDONALD' ->
    'McDonald', "O'NEAL" -> "O'Neal", 'SMITH-JONES' -> 'Smith-Jones', and a generational suffix (III) keeps its capitals."""
    def fix(word: str) -> str:
        if not word.isupper() or len(word.strip(".")) < 2 or word in _SUFFIXES:
            return word
        out = "-".join(part.capitalize() for part in word.split("-"))
        out = re.sub(r"(?<=\bO['’])([a-z])", lambda m: m.group(1).upper(), out)
        return re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), out)
    return " ".join(fix(w) for w in (name or "").split())


def person_story(p: dict, agency: dict, page_url: str, now: datetime, city: str) -> Story | None:
    if p.get("age") is not None and p["age"] < 18:
        return None  # never a juvenile
    raw_name, charge, reward = p["name"], p["charge"], p["reward"]
    name = proper_name(raw_name)
    summary = (f"{name} is wanted by the {agency['name']} for {charge}. Crime Stoppers will pay up to {reward} for information "
               f"leading to an arrest. Call {TIP_PHONE} or submit a tip at {p.get('tip_url') or TIP_URL}. Tipsters stay anonymous.")
    return Story(
        id=stable_id("wanted", agency["name"], raw_name, charge),     # the agency's spelling: bulletins already posted keep their id
        source=agency["name"],
        source_kind="wanted",
        title=f"WANTED: {name}",
        summary=summary,
        url=page_url,
        published=now,
        category_hint="crime",
        image_url=p["image"],
        image_credit=f"Photo: {agency['name']}",
        image_license="official",
        image_policy="source_image",
        official=True,
        always_relevant=True,
        weight=float(agency.get("weight", 0.8)),
        extra={"name": name, "charge": charge, "agency": agency["name"], "reward": reward, "tip_phone": TIP_PHONE,
               "tip_url": p.get("tip_url") or TIP_URL, "age": p.get("age"), "city": agency.get("city", city), "details": p.get("details", "")},
    )


def fetch(settings: Settings, now: datetime) -> list[Story]:
    cfg = settings.sources.get("wanted", {}) or {}
    if settings.offline or not cfg.get("enabled", True):
        return []
    city = settings.brand.get("city", "Fort Worth")
    stories: list[Story] = []
    for agency in cfg.get("agencies", []) or []:
        parser = PARSERS.get(agency.get("kind"))
        if not parser or not agency.get("enabled", True):
            continue
        try:
            resp = http.get(agency["url"], headers={"Accept": "text/html"})
            kwargs = {"local_only": bool(agency.get("local_only", True))} if agency.get("kind") == "dps" else {}
            people = parser(resp.text, str(resp.url), now, **kwargs)
            log.info("wanted %-28s %2d people", agency["name"], len(people))
            for p in people:
                story = person_story(p, agency, agency["url"], now, city)
                if story:
                    stories.append(story)
        except Exception as exc:
            log.warning("wanted %s failed (%s): %s", agency.get("name"), agency.get("url"), exc)
    return stories
