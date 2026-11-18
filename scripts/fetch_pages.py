"""Polite fetcher for PUBLIC agency pages (press rooms, news listings) so their structure can be inspected from a
machine without internet access. Identifies itself, honors robots.txt, follows a few news links one level deep.

Usage: python scripts/fetch_pages.py out/pages URL [URL ...]
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests

UA = "FTWorthTv/0.1 (+https://github.com/fwagtx/FTWorthTv; local news page bot; contact via GitHub issues)"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/pages")
URLS = [u for u in sys.argv[2:] if u.strip()]
_robots: dict[str, robotparser.RobotFileParser] = {}


def allowed(url: str) -> bool:
    origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
    rp = _robots.get(origin)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(origin + "/robots.txt")
            rp.read()
        except Exception:
            rp = None  # no robots.txt reachable: default allow
        _robots[origin] = rp
    return True if rp is None else rp.can_fetch(UA, url)


def save(url: str, body: bytes, tag: str = "") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", url.split("://", 1)[-1]).strip("_")[:120]
    (OUT / f"{tag}{name}.html").write_bytes(body)


LOG: list[str] = []


def log(line: str) -> None:
    print(line)
    LOG.append(line)


def fetch(url: str) -> bytes | None:
    if not allowed(url):
        log(f"SKIP (robots.txt disallows) {url}")
        return None
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"}, timeout=30)
        log(f"{r.status_code} {len(r.content):>8}  {url}  -> {r.url}")
        time.sleep(1.0)
        return r.content if r.ok else None
    except Exception as exc:
        log(f"ERR {url}: {exc}")
        return None


def save_robots(url: str) -> None:
    origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
    out = OUT / ("robots__" + re.sub(r"[^a-zA-Z0-9]+", "_", urlparse(url).netloc) + ".txt")
    if out.exists():
        return
    try:
        r = requests.get(origin + "/robots.txt", headers={"User-Agent": UA}, timeout=20)
        OUT.mkdir(parents=True, exist_ok=True)
        out.write_text(f"# {r.status_code}\n" + r.text[:20000], encoding="utf-8")
    except Exception as exc:
        log(f"robots.txt fetch failed for {origin}: {exc}")


for url in URLS:
    save_robots(url)
    body = fetch(url)
    if not body:
        continue
    save(url, body)
    html = body.decode("utf-8", "ignore")
    links: list[str] = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', html):
        full = urljoin(url, href)
        if urlparse(full).netloc != urlparse(url).netloc or full.rstrip("/") == url.rstrip("/"):
            continue
        if re.search(r"(news-articles/|/news/20|/newsroom/|/press-release|/wanted|/news/\d|/News/|/article/)", full, re.I) and full not in links:
            links.append(full)
    print(f"   {len(links)} candidate article links on {url}")
    for link in links[:4]:
        sub = fetch(link)
        if sub:
            save(link, sub, tag="article__")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "fetch-log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
