"""An optional second opinion on a photo: does this file really show what the headline is about?

The subject rules (images/subject.py) are deterministic and run everywhere. When headless Claude Code is available
(CLAUDE_CODE_OAUTH_TOKEN, the same subscription that writes captions), a provider photo for a named subject is also put
to Claude with its title, description and credit, and dropped unless the answer is yes. Library photos are not judged:
every one of them was filed by hand under its subject.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)

PROMPT = """You check news photos for a local news page. First open and look at the image file {path} with the Read tool.
Then answer with one word, yes or no, on the last line.

Headline: {headline}
Story summary: {summary}

Candidate photo:
- file title: {title}
- description: {alt}
- credit: {credit}

Does the picture itself clearly show the specific subject of the headline (the named company, team, person, school, place
or event), so that a reader would see the connection at once? A different person who shares the name, another artist's
show at the same venue, or a generic stand-in (a skyline for a company, an exchange building for a company's IPO, a
street for a festival list, a campus building for a football game) is "no". If you cannot open the image, answer no."""


def available(settings) -> bool:
    token = getattr(settings, "claude_code_oauth_token", None) or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    return bool(token) and bool(shutil.which("claude")) and getattr(settings, "writer", "auto") in ("auto", "claude_code")


def photo_fits(settings, *, headline: str, summary: str, title: str, alt: str, credit: str, path: str = "") -> bool | None:
    """True/False from Claude after it has looked at the file, None when it could not be asked (then the deterministic rules
    decide alone, and a person's photo is not used at all)."""
    if not available(settings):
        return None
    prompt = PROMPT.format(path=path or "(no file)", headline=headline, summary=(summary or "")[:600], title=title or "",
                           alt=(alt or "")[:300], credit=credit or "")
    env = dict(os.environ)
    token = getattr(settings, "claude_code_oauth_token", None)
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    try:
        proc = subprocess.run([shutil.which("claude"), "-p", prompt, "--output-format", "json", "--max-turns", "3",
                               "--allowedTools", "Read"], capture_output=True, text=True, timeout=180, env=env)
        payload = json.loads(proc.stdout or "{}")
        answer = str(payload.get("result") or payload.get("content") or "").strip().lower()
        answer = answer.splitlines()[-1].strip() if answer else answer
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        log.warning("photo judge could not run: %s", exc)
        return None
    if answer.startswith("yes"):
        return True
    if answer.startswith("no"):
        return False
    log.info("photo judge gave no clear answer (%r)", answer[:40])
    return None
