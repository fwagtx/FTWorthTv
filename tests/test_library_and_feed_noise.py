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
    assert topics_for("Largest enrollment drop in Texas history, Morath says", "community", "texas")[:2] == ["school-bus", "schools"]
    assert topics_for("A Kendall County jury found the man guilty", "crime", "texas")[0] == "courthouse"
    # a Houston story never gets the Fort Worth skyline by default
    assert "houston-skyline" in topics_for("Houston council votes on new budget", "politics", "texas")[:3]
    assert topics_for("Something happened", "other", "local")[0] == "skyline"
    # a Dallas City Hall story must not get Fort Worth City Hall or the Fort Worth skyline
    t = topics_for("Voters will decide Dallas City Hall's future in May", "politics", "dfw")
    assert "city-hall" not in t and "skyline" not in t and "dallas-skyline" in t[:2]


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


def test_sports_story_about_a_school_wants_its_stadium():
    from ftworthtv.images.library import topics_for
    text = "No. 2 Utah (10-0) comes to Fort Worth on Saturday night and can clinch a spot in the Big 12 championship game with a win over TCU. The Horned Frogs need to win one of their last two games."
    topics = topics_for(text, "sports", "local", title="Utah visits TCU, close to Big 12 title game")
    assert topics[0] == "tcu-football" and "tcu" in topics
    campus = topics_for("TCU opens a new nursing building on campus", "community", "local", title="TCU opens a new nursing building")
    assert campus[0] == "tcu" and "tcu-football" not in campus


def test_a_venue_named_only_in_the_body_is_not_the_picture():
    from ftworthtv.images.library import topics_for
    body = ("Richard Reinaldo Garcia, 53, was found guilty in a $6 million fraud scheme. Prosecutors said he met victims at a church "
            "in Arlington, not far from AT&T Stadium, and told congregants the Cowboys owner had blessed the fund.")
    topics = topics_for(body, "crime", "dfw", title="North Texas man convicted of defrauding $6M from 70 churches, congregants")
    assert "att-stadium" not in topics


def test_a_team_name_brings_its_stadium_only_for_a_game_there():
    away = topics_for("Cowboys face last-place Titans with new defensive play-caller. The Cowboys travel to Nashville on Sunday.", "sports", "local",
                      title="Cowboys face last-place Titans with new defensive play-caller")
    assert "att-stadium" not in away
    named = topics_for("Cowboys face last-place Titans. Dak Prescott (4) looks to pass at Nissan Stadium in Nashville.", "sports", "local",
                       title="Cowboys face last-place Titans")
    assert "att-stadium" not in named
    home = topics_for("Cowboys host the Eagles on Sunday at AT&T Stadium in Arlington.", "sports", "local", title="Cowboys host the Eagles on Sunday")
    assert home[0] == "att-stadium"
