from datetime import datetime, timedelta, timezone

from ftworthtv.filters import filter_stories
from ftworthtv.models import Story
from ftworthtv.state import State


def _s(i, source, title, national=True, now=None):
    return Story(id=f"n{i}", source=source, source_kind="rss", title=title, summary="Some summary text about it.",
                 url=f"https://example.com/{i}", published=(now or datetime.now(timezone.utc)) - timedelta(hours=1),
                 extra={"national": national})


def test_national_watchlist_and_buzz(settings, now):
    state = State(settings.state_path)
    stories = [
        _s(1, "Variety", "GTA VI is finally here: Rockstar's long-awaited sequel launches", now=now),          # watchlist: one hit is enough
        _s(2, "Variety", "Some actor joins an indie film nobody has heard of", now=now),                        # nothing
        _s(3, "Billboard", "Pop star announces tour dates for 2027 stadium run", now=now),                      # big-moment term, one outlet
        _s(4, "The Verge", "Netflix raises prices again", now=now),                                             # term carried by 2 outlets ->
        _s(5, "Variety", "Netflix price hike hits subscribers this month", now=now),                            #   both pass the gate
        _s(6, "NPR News", "Man dies at 54 after crash", now=now),                                               # crime/traffic never
    ]
    kept, dropped = filter_stories(stories, settings, state, now)
    kept_ids = {s.id for s in kept}
    assert "n1" in kept_ids and kept[[s.id for s in kept].index("n1")].extra["scope"] == "national"
    assert "n2" not in kept_ids and "n3" not in kept_ids and "n6" not in kept_ids
    assert {"n4", "n5"} <= kept_ids
    assert all(s.extra.get("national_term") for s in kept if s.id in ("n1", "n4", "n5"))


def test_national_moment_not_repeated(settings, now):
    state = State(settings.state_path)
    state.data["posted"]["x"] = {"at": (now - timedelta(hours=5)).isoformat(), "title": "GTA VI launches today on PS5 and Xbox"}
    kept, dropped = filter_stories([_s(1, "IGN", "GTA VI review: the biggest game of the decade", now=now)], settings, state, now)
    assert not kept and "already covered" in dropped[0][1]
