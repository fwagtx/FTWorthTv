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
    # Nov 25: a statewide story that never names Fort Worth or Tarrant County gets no Fort Worth landmark: the Tarrant County
    # Courthouse is not a Kendall County courtroom (KHOU's Tomball pharmacy recall was drafted with the downtown skyline)
    assert "courthouse" not in topics_for("A Kendall County jury found the man guilty", "crime", "texas")
    assert topics_for("A Tarrant County jury found the man guilty", "crime", "texas")[0] == "courthouse"
    recall = "Texas pharmacy recalls medications nationwide. Tomball-based Greenwich Rx is recalling certain medications."
    assert not {"skyline", "downtown", "capitol"} & set(topics_for(recall, "other", "texas", title="Texas pharmacy recalls medications nationwide"))
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


def test_a_venue_is_a_picture_for_a_game_never_for_a_coaching_story():
    coaching = topics_for("Parker disappointed Cowboys pulled play-calling duties, but keeps focus on team. Christian Parker lost the duties Friday.",
                          "sports", "local", title="Parker disappointed Cowboys pulled play-calling duties, but keeps focus on team")
    assert "att-stadium" not in coaching
    game = topics_for("Cowboys beat the Eagles 24-17 on Sunday at AT&T Stadium.", "sports", "local", title="Cowboys beat the Eagles 24-17")
    assert "att-stadium" in game
    # Nov 24: NBC 5's Mavs NBA Cup preview went out with the American Airlines Center; the game was in Denver. A story that does
    # not say where the game is played gets no home venue.
    unknown = topics_for("Cowboys beat the Eagles 24-17 on Sunday.", "sports", "local", title="Cowboys beat the Eagles 24-17")
    assert "att-stadium" not in unknown
    t = "Mavs enter NBA Cup matchup on NBC with eye on building foundation for success"
    mavs = topics_for(f"{t}. Dallas sits atop the West Group A standings entering Tuesday's nationally televised matchup against "
                      "the Denver Nuggets.", "sports", "dfw", title=t)
    assert "aac" not in mavs
    hosts = topics_for("Mavericks host the Nuggets on Tuesday in the NBA Cup.", "sports", "dfw", title="Mavericks host the Nuggets in NBA Cup")
    assert "aac" in hosts
    wire = topics_for("Mavericks beat Nuggets 120-110. DENVER (AP) — Dallas won its third straight.", "sports", "dfw",
                      title="Mavericks beat Nuggets 120-110")
    assert "aac" not in wire
    itself = topics_for("Dickies Arena adds a second entrance ahead of the stock show.", "community", "local", title="Dickies Arena adds a second entrance")
    assert itself[0] == "dickies-arena"


def test_north_texas_is_the_region_never_the_unt_campus():
    t = "5 North Texas police officers among 30 nationwide honored by Justice Department"
    assert "unt" not in topics_for(t, "crime", "local", title=t)
    assert topics_for("UNT Mean Green beat Rice in Denton", "sports", "dfw", title="UNT Mean Green beat Rice in Denton")[0] in ("unt", "unt-football")
    u = "University of North Texas opens a new research hall"
    assert "unt" in topics_for(u, "community", "dfw", title=u)


def test_an_agency_branded_library_photo_is_only_for_that_agencys_story(tmp_path):
    import json as _json
    from ftworthtv.images.library import _cache, pick
    (tmp_path / "assets" / "photos" / "police").mkdir(parents=True)
    (tmp_path / "assets" / "photos" / "police" / "airport.jpg").write_bytes(b"x")
    (tmp_path / "assets" / "photos" / "library.json").write_text(_json.dumps([
        {"id": "lib-airport", "file": "assets/photos/police/airport.jpg", "topic": "police", "credit": "Photo: J", "only_when": ["dfw airport", "airport police"]}]))
    _cache.clear()
    assert pick(tmp_path, ["police"], text="5 North Texas police officers among 30 nationwide honored by Justice Department") is None
    assert pick(tmp_path, ["police"], text="DFW Airport police arrest a man at Terminal D").id == "lib-airport"
    _cache.clear()


def test_a_hospital_named_baylor_is_not_the_waco_campus():
    """Render 112, Nov 22: 'Medical ethicist weighs in on North Texas transplant case' (a lawsuit against Baylor University
    Medical Center in Dallas) drew McLane Stadium in Waco."""
    from ftworthtv.images.library import topics_for
    from ftworthtv.images.subject import plan_subject
    text = "A North Texas transplant agency has sued Baylor University Medical Center."
    assert "baylor" not in topics_for(text, "other", "dfw", title="Medical ethicist weighs in on North Texas transplant case")
    assert "baylor" not in plan_subject("Baylor Scott & White opens new Fort Worth clinic", "", "community").entity_topics
    assert "baylor" in topics_for("Baylor beat TCU 31-24 in Waco.", "sports", "texas", title="Baylor beats TCU")


def test_topic_words_match_whole_words():
    """Nov 25: "snow" matched inside "Amanda Yesnowitz" and "development" inside "in development as new stage musical": a novel's
    musical adaptation was drafted with a 2021 snowstorm map."""
    from ftworthtv.images.library import phrase_in, topics_for
    assert not phrase_in("snow", " amanda yesnowitz ") and phrase_in("snow", " heavy snow tonight ")
    assert phrase_in("storm", " storms roll in ") and phrase_in("tornado", " two tornadoes touched down ")
    t = "Sandra Brown’s novel RAINWATER in development as new stage musical"
    got = topics_for(f"{t}. Brian Feinstein and Amanda Yesnowitz lead the musical adaptation.", "business", "local", title=t)
    assert "ice" not in got and "apartments" not in got
    assert "apartments" in topics_for("Developer plans 300 apartments near the Stockyards", "business", "local",
                                      title="Developer plans 300 apartments near the Stockyards")
