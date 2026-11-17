from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ftworthtv.config import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def now() -> datetime:
    # a Thursday 5:30pm Central so the weekend roundup + evening events make sense
    return datetime(2026, 11, 19, 23, 30, tzinfo=timezone.utc)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Real config files, but out/ and state/ redirected into tmp and no secrets from the environment."""
    env = {"FTWTV_PUBLISHER": "dryrun", "FTWTV_OUT_DIR": str(tmp_path / "out"), "FTWTV_STATE_PATH": str(tmp_path / "state" / "posted.json")}
    s = Settings.load(root=ROOT, env=env)
    s.offline = True
    return s


@pytest.fixture
def examples_dir() -> Path:
    return ROOT / "examples"
