from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ftworthtv.textutil import clean_hashtag, fmt_time, relative_day, slugify, strip_html, truncate


def test_strip_html_and_entities():
    assert strip_html("<p>Hello&nbsp;<b>Fort</b> Worth &amp; friends<br/>!</p>") == "Hello Fort Worth & friends !"


def test_truncate_on_word_boundary():
    out = truncate("The quick brown fox jumps over the lazy dog", 20)
    assert out.endswith("…") and len(out) <= 20


def test_slugify():
    assert slugify("Crash shuts down I-35W near downtown!") == "crash-shuts-down-i-35w-near-downtown"


def test_relative_day_and_time():
    tz = ZoneInfo("America/Chicago")
    now = datetime(2026, 11, 19, 20, 0, tzinfo=timezone.utc)      # 2pm Thu Central
    tonight = datetime(2026, 11, 20, 1, 30, tzinfo=timezone.utc)  # 7:30pm Thu Central
    assert relative_day(tonight, now, tz) == "Tonight"
    assert relative_day(tonight + timedelta(days=1), now, tz) == "Tomorrow"
    assert relative_day(tonight + timedelta(days=2), now, tz) == "This Saturday"
    assert fmt_time(tonight, tz) == "7:30 PM"


def test_clean_hashtag():
    assert clean_hashtag(" fort worth! ") == "#fortworth"
    assert clean_hashtag("#FortWorth") == "#FortWorth"
