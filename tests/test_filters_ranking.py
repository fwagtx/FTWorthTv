from ftworthtv.examples import example_stories
from ftworthtv.filters import blocked, filter_stories, infer_category, relevance_score
from ftworthtv.models import Story
from ftworthtv.ranking import pick, rank
from ftworthtv.state import State


def _story(title, summary="", **kw):
    return Story(id=title, source="t", source_kind="rss", title=title, summary=summary, url="https://x/" + title, **kw)


def test_relevance_scoring_prefers_title_hits():
    kws = ["fort worth", "stockyards", "arlington"]
    assert relevance_score(_story("Fort Worth opens new park"), kws) == 2
    assert relevance_score(_story("New park", "in the Stockyards near Fort Worth"), kws) == 2
    assert relevance_score(_story("Austin news"), kws) == 0


def test_blocklist_and_categories():
    assert blocked(_story("Obituary: beloved teacher"), ["obituary"]) == "obituary"
    assert infer_category(_story("Severe thunderstorm warning for Tarrant County")) == "weather"
    assert infer_category(_story("Crash closes I-35W lanes downtown")) == "traffic"
    assert infer_category(_story("Fort Worth City Council approves budget after vote")) == "politics"
    assert infer_category(_story("New barbecue restaurant opens on Magnolia")) == "food"


def test_filter_pipeline_on_examples(settings, now, tmp_path):
    state = State(tmp_path / "s.json")
    stories = example_stories(settings, now)
    kept, dropped = filter_stories(stories, settings, state, now)
    reasons = {s.title: r for s, r in dropped}
    assert any("blocklist" in r for t, r in reasons.items() if t.startswith("Obituary"))
    assert "excluded category: politics" in reasons["Fort Worth City Council approves budget after marathon meeting"]
    assert "not local enough" in reasons["Dallas ISD trustees debate new school start times"]
    assert "not local enough" in reasons["Texas Legislature weighs statewide property tax changes"]
    titles = {s.title for s in kept}
    assert "Arlington police arrest suspect after chase ends near AT&T Stadium" in titles   # Arlington counts as local
    assert all(s.category for s in kept)


def test_already_posted_is_dropped(settings, now, tmp_path):
    state = State(tmp_path / "s.json")
    stories = example_stories(settings, now)
    state.data["posted"][stories[0].id] = {"at": now.isoformat()}
    kept, dropped = filter_stories(stories, settings, state, now)
    assert stories[0].id not in {s.id for s in kept}
    assert any(r == "already posted" for _, r in dropped)


def test_ranking_puts_severe_weather_first_and_pick_is_diverse(settings, now, tmp_path):
    state = State(tmp_path / "s.json")
    kept, _ = filter_stories(example_stories(settings, now), settings, state, now)
    ranked = rank(kept, now)
    assert ranked[0].source_kind == "nws_alert"
    picked = pick(ranked, 4)
    assert len(picked) == 4
    cats = [p.category for p in picked if not p.is_urgent]
    assert len(cats) == len(set(cats))   # no duplicate categories among non-urgent picks


def test_keywords_match_whole_words_only():
    assert infer_category(_story("Fitch upgrades Fort Worth's Drainage Rev Bonds to AAA")) != "weather"
    assert infer_category(_story("Heavy rain floods Fort Worth streets")) == "weather"


def test_culture_calendar_post_outranks_a_plain_rss_item_in_its_category(settings, now):
    from datetime import date
    from ftworthtv.sources.calendar import active_moments, load_moments, moment_story
    m, start, idx = next(x for x in active_moments(load_moments(settings), date(2026, 11, 21)) if x[0]["slug"] == "parade-of-lights")
    culture = moment_story(m, start, idx, now, "Fort Worth"); culture.category = "culture"; culture.relevance = 0
    rss = _story("Free & Fun Events in Arlington: November 19 - 25, 2026", "Stay informed.", always_relevant=True, weight=0.6, published=now)
    rss.category = "culture"; rss.relevance = 2
    assert rank([rss, culture], now)[0] is culture


def test_obituaries_are_blocked_even_without_the_word():
    assert blocked(_story("Pamela Rose Hiles – June 29, 1932 – Nov. 8, 2026"), []) is not None
    assert blocked(_story("Eddie Ray Brewer - Dec. 8, 1952 - Nov. 14, 2026"), []) is not None
    assert blocked(_story("Fort Worth marks 150 years since 1876 railroad arrival, celebrates through 2026"), []) is None
