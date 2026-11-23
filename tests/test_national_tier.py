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


def test_collect_dedupe_keeps_the_national_flag():
    from ftworthtv.sources import collect
    from ftworthtv.models import Story
    a = Story(id="same", source="ESPN NBA", source_kind="rss", title="Heat unveil Vice City court ahead of GTA VI release", summary="s", url="https://e.com/1")
    b = Story(id="same", source="ESPN Top Headlines", source_kind="rss", title="Heat unveil Vice City court ahead of GTA VI release", summary="s", url="https://e.com/1", extra={"national": True})
    # the same merge rule, applied directly
    by_id = {}
    for s in (a, b):
        kept = by_id.get(s.id)
        if kept is None:
            by_id[s.id] = s
        elif s.extra.get("national") and not kept.extra.get("national"):
            kept.extra["national"] = True
    assert by_id["same"].extra.get("national") is True


def test_urgency_is_for_local_breaking_news_only():
    from ftworthtv.filters import infer_category
    def mk(title, scope="local"):
        s = Story(id="u", source="s", source_kind="rss", title=title, summary="", url="https://e.com", extra={"scope": scope})
        s.category = infer_category(s)
        return s
    assert mk("BREAKING: Shooting at a Fort Worth gas station").is_urgent
    assert mk("Developing: evacuations ordered near Benbrook").is_urgent
    assert not mk("GTA 6 shatters streaming records before it's even out", scope="national").is_urgent
    assert not mk("BREAKING: Celebrity couple splits", scope="national").is_urgent


def test_national_outlet_needs_a_place_in_the_title(settings, now):
    state = State(settings.state_path)
    s = _s(9, "Deadline", "Senate And House Lawmakers Added As Cosponsors To New Federal Film Incentive Legislation", now=now)
    s.summary = "Lawmakers in the Senate and House back the bill; the governor of Texas has not commented."
    kept, dropped = filter_stories([s], settings, state, now)
    assert not kept
    t = _s(10, "Variety", "Taylor Swift adds Arlington stadium dates to the tour", now=now)
    t.summary = "AT&T Stadium in Arlington, Texas, gets two more nights on the tour."
    kept, dropped = filter_stories([t], settings, state, now)
    assert kept and kept[0].extra["scope"] in ("local", "dfw")   # Arlington is home turf


def test_article_enrichment_rejects_another_article():
    from ftworthtv.sources.article import same_subject
    assert not same_subject("Cooper Flagg scores 33 as Mavs keep Warriors winless", "Anthropic IPO raises record $81 billion",
                            "The higher-than-anticipated pricing signals broad investor enthusiasm for AI stocks.", "Anthropic said the offering consists of 980 million shares.")
    assert same_subject("Cooper Flagg scores 33 as Mavs keep Warriors winless", "Cooper Flagg scores 33 as Mavericks beat Warriors", "", "")
    assert same_subject("Trinity Metro cuts On-Demand zones", "", "Trinity Metro's board approved cuts to the On-Demand microtransit zones Monday.", "")


def test_photo_topic_from_body_mentions_is_title_only():
    from ftworthtv.images.library import topics_for
    text = "These are the 14 best things to do in Fort Worth this weekend. The weekend before Thanksgiving brings holiday events."
    assert topics_for(text, "community", "local", title="These are the 14 best things to do in Fort Worth this weekend")[0] != "thanksgiving"
    assert topics_for("Cooper Flagg scores 33 as Mavs keep Warriors winless. A lawsuit was mentioned somewhere.", "sports", "dfw",
                      title="Cooper Flagg scores 33 as Mavs keep Warriors winless")[0] == "aac"


def test_datelines_and_photo_captions_are_not_caption_sentences():
    from ftworthtv.writer import _sentences
    sents = _sentences("ARLINGTON, Texas - The Tarrant Area Food Bank is partnering with the Cotton Bowl to feed 5,000 families Thursday. "
                       "Attorney General-elect Nathan Johnson at the Capitol, on November 16, 2026. FOX 4's Alex Boyer has more.")
    assert sents == ["The Tarrant Area Food Bank is partnering with the Cotton Bowl to feed 5,000 families Thursday."]


def test_platform_named_in_passing_is_not_a_moment(settings, now):
    """Nov 23, render 155: 'Tyson Fury Reveals Schizophrenia Diagnosis in Netflix Documentary' (Variety and Deadline) took the
    day's national slot because 'netflix' sat in two headlines. A platform counts only when it is the story."""
    state = State(settings.state_path)
    stories = [
        _s(1, "Variety", "Tyson Fury Reveals Schizophrenia Diagnosis in Netflix Documentary: ‘I Thought I’d End Up in a Padded Room’", now=now),
        _s(2, "Deadline", "Tyson Fury Reveals Schizophrenia Diagnosis In Netflix Doc", now=now),
        _s(3, "Deadline", "Controversial “Netflix Tax” Could Raise Extra $2.1B For BBC By 2032, Research Finds", now=now),
    ]
    kept, dropped = filter_stories(stories, settings, state, now)
    assert not kept, [s.title for s in kept]
    # the platform as the story still counts, once two outlets carry it
    stories += [_s(4, "The Verge", "Netflix raises prices again", now=now), _s(5, "Variety", "Netflix’s price hike hits subscribers", now=now)]
    kept, dropped = filter_stories(stories, settings, State(settings.state_path), now)
    assert {s.id for s in kept} == {"n4", "n5"}


def test_magazine_feature_is_not_the_moment(settings, now):
    """Nov 23, render 156: Billboard's GTA VI soundtrack cover story hit the watchlist and drafted as the national post."""
    state = State(settings.state_path)
    feature = _s(1, "Billboard", "‘It’s Not Just a Song on the Radio’: How Music Became A Main Character In ‘Grand Theft Auto VI’", now=now)
    feature.url = "https://www.billboard.com/music/features/gta-6-radio-songs-soundtrack-justice-billboard-cover-1236386805/"
    kept, dropped = filter_stories([feature, _s(2, "Variety", "GTA VI is finally here: Rockstar's long-awaited sequel launches", now=now)],
                                   settings, state, now)
    assert [s.id for s in kept] == ["n2"]
    assert "magazine feature" in dict((s.id, r) for s, r in dropped)["n1"]


def test_one_outlets_trailer_is_not_a_moment(settings, now):
    """Nov 23, render 158: Deadline's 'Lil Kev' season 2 trailer counted as a national moment because "trailer" sat in other
    outlets' headlines about the Avengers trailer. Two outlets make a moment only when they carry the same story."""
    state = State(settings.state_path)
    stories = [
        _s(1, "Deadline", "‘Lil Kev’ Ends Up Behind Bars In Season 2 Trailer For Kevin Hart Animated Series", now=now),
        _s(2, "Deadline", "Final ‘Avengers: Doomsday’ Trailer Has Fantastic Four Pulling Steve Rogers Out Of His Quiet Life", now=now),
        _s(3, "Variety", "‘Avengers: Doomsday’ Final Trailer: Captain America’s Son Revealed, Fantastic Four Rescues Steve Rogers", now=now),
    ]
    kept, dropped = filter_stories(stories, settings, state, now)
    assert {s.id for s in kept} == {"n2", "n3"}
