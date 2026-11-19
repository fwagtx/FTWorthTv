from datetime import datetime, timezone
from pathlib import Path

from ftworthtv.images.library import avoid_words_for, pick, topics_for
from ftworthtv.sources.rss import clean_feed_text


def test_feed_noise_is_removed():
    t = clean_feed_text("Students cook side dishes as part […] The post Ate Days of Thanksgiving Love appeared first on Fort Worth Weekly .")
    assert "appeared first" not in t and "[…]" not in t
    assert t.startswith("Students cook side dishes as part")


def test_library_topics_put_the_subject_first():
    assert topics_for("Trinity Metro approved cuts to its On-Demand service", "traffic", "local")[0] == "transit"
    assert topics_for("Largest enrollment drop in Texas history, Morath says", "community", "texas")[0] == "schools"
    assert topics_for("A Kendall County jury found the man guilty", "crime", "texas")[0] == "courthouse"
    # a Houston story never gets the Fort Worth skyline by default
    assert "houston-skyline" in topics_for("Houston council votes on new budget", "politics", "texas")[:3]
    assert topics_for("Something happened", "other", "local")[0] == "skyline"


def test_other_city_words_are_avoided():
    words = avoid_words_for("Trinity Metro cuts across Fort Worth")
    assert "houston" in words and "dallas" in words
    assert "dallas" not in avoid_words_for("Fort Worth and Dallas share the airport")


def test_pick_from_library(tmp_path: Path):
    lib = tmp_path / "assets" / "photos"
    lib.mkdir(parents=True)
    (lib / "a.jpg").write_bytes(b"x")
    (lib / "b.jpg").write_bytes(b"x")
    (lib / "library.json").write_text('[{"id": "lib-a", "file": "assets/photos/a.jpg", "topic": "transit", "credit": "Photo: A"},'
                                      ' {"id": "lib-b", "file": "assets/photos/b.jpg", "topic": "skyline", "credit": "Photo: B"}]')
    assert pick(tmp_path, ["transit", "skyline"]).id == "lib-a"
    assert pick(tmp_path, ["transit", "skyline"], used={"lib-a"}).id == "lib-b"
    # recently used is a preference, not a ban: the right subject wins over novelty
    assert pick(tmp_path, ["transit", "skyline"], used={"lib-a"}, recently_used=lambda i: i == "lib-b").id == "lib-b"
    assert pick(tmp_path, ["transit", "skyline"], used={"lib-a", "lib-b"}) is None
