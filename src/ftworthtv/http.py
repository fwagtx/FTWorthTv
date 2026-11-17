"""HTTP helpers: one shared session with retries, polite User-Agent, and safe downloads."""
from __future__ import annotations

import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

DEFAULT_UA = "FTWorthTv/0.1 (+https://github.com/fwagtx/FTWorthTv; automated local news page)"
_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(total=3, backoff_factor=0.8, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset(["GET", "HEAD"]))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.headers["User-Agent"] = DEFAULT_UA
        _session = s
    return _session


def get(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: int = 25) -> requests.Response:
    resp = session().get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def get_json(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: int = 25):
    resp = get(url, params=params, headers=headers, timeout=timeout)
    return resp.json()


def download(url: str, dest: Path, *, max_bytes: int = 20_000_000, allowed_prefixes: tuple[str, ...] = ("image/",),
             headers: dict | None = None, timeout: int = 40) -> Path:
    """Stream a file to disk, refusing anything that is not an image (or too big)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with session().get(url, stream=True, headers=headers, timeout=timeout) as resp:
        resp.raise_for_status()
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if allowed_prefixes and not any(ctype.startswith(p) for p in allowed_prefixes):
            raise ValueError(f"unexpected content-type {ctype!r} for {url}")
        size = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"download exceeds {max_bytes} bytes: {url}")
                fh.write(chunk)
    return dest
