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
    titles = {s.title for s in kept}
    by_title = {s.title: s for s in kept}
    # the study: state/local politics is the reference page's best topic, so it stays (capped per day in brand.yaml)
    assert "Fort Worth City Council approves budget after marathon meeting" in titles
    assert by_title["Fort Worth City Council approves budget after marathon meeting"].category == "politics"
    # DFW-wide and Texas-wide stories are kept at a lower weight with a non-local scope, instead of being dropped
    dallas = by_title.get("Dallas ISD trustees debate new school start times")
    texas = by_title.get("Texas Legislature weighs statewide property tax changes")
    assert dallas is not None and dallas.extra.get("scope") == "dfw" and dallas.weight < 1.0
    assert texas is not None and texas.extra.get("scope") == "texas" and texas.weight < dallas.weight
    assert "Arlington police arrest suspect after chase ends near AT&T Stadium" in titles   # Arlington counts as local
    assert by_title["Arlington police arrest suspect after chase ends near AT&T Stadium"].extra.get("scope") == "local"
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


def test_same_story_from_two_outlets_is_posted_once(settings, now, tmp_path):
    from ftworthtv.filters import same_story
    from ftworthtv.models import Story
    a = "Cowboys strip play-calling duties from defensive coordinator Christian Parker"
    b = "Dallas Cowboys take play-calling away from defensive coordinator Christian Parker, sources say"
    c = "Fort Worth Parade of Lights 2026: street closures, parking and more tips"
    assert same_story(a, b) and not same_story(a, c)
    state = State(tmp_path / "s.json")
    state.data["posted"]["x1"] = {"at": now.isoformat(), "title": a, "url": "https://x/1"}
    stories = [Story(id="y2", source="WFAA", source_kind="rss", title=b, summary="The Cowboys made the change Tuesday, the team confirmed in a statement.",
                     url="https://x/2", published=now, always_relevant=True)]
    kept, dropped = filter_stories(stories, settings, state, now)
    assert not kept and "another outlet" in dropped[0][1]


def test_non_local_share_is_counted_per_day(settings, now, tmp_path):
    from ftworthtv.models import PostCopy, PostDraft, PublishResult, Story
    state = State(tmp_path / "s.json")
    day = now.date().isoformat()
    for i, scope in enumerate(("texas", "dfw", "local")):
        story = Story(id=f"n{i}", source="x", source_kind="rss", title=f"Story {i} with enough words here", summary="", url=f"https://x/{i}", extra={"scope": scope})
        draft = PostDraft(story=story, copy=PostCopy(headline="h", caption="c", category="sports"), writer="template")
        state.record(draft, PublishResult(ok=True, publisher="dryrun", detail="", post_id=None, url=None), now, day)
    assert state.non_local_posts_on(day) == 2 and state.posts_on(day) == 3


def test_another_metros_weekend_roundup_is_not_ours():
    from ftworthtv.filters import other_metro_roundup
    assert other_metro_roundup("Austin weekend: Theater performances, Bastrop B-day")
    assert other_metro_roundup("Things to do in Houston this weekend")
    assert not other_metro_roundup("These are the 14 best things to do in Fort Worth this weekend")
    assert not other_metro_roundup("Austin ISD trustees vote to close four schools")


def test_another_regions_story_is_not_ours():
    from ftworthtv.filters import other_region
    assert other_region("Why fall foliage looks different across South Central Texas")
    assert not other_region("North Texas fall foliage peaks this week")
    assert not other_region("Texas public schools lose 135,000 students")
    assert not other_region("Hill Country flooding kills 3 as rivers rise overnight")   # a disaster anywhere in Texas is statewide news


def test_the_same_reopening_under_two_headlines_is_one_story():
    from ftworthtv.filters import same_story
    assert same_story("Downton Fort Worth restaurant reopens three years after an explosion",
                      "Fort Worth restaurant will reopen nearly three years after hotel explosion")
    assert not same_story("Fort Worth restaurant will reopen nearly three years after hotel explosion",
                          "Fort Worth police searching for Kenneth Gaines")


def test_a_story_posted_yesterday_is_not_posted_again_under_another_headline(settings, now):
    from datetime import timedelta
    from ftworthtv.filters import filter_stories
    from ftworthtv.models import PostCopy, PostDraft, PublishResult, Story
    from ftworthtv.state import State
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    state = State(settings.state_path)
    first = Story(id="v1", source="WFAA", source_kind="video", title="Downton Fort Worth restaurant reopens three years after an explosion", summary="",
                  url="https://www.youtube.com/watch?v=x", published=now - timedelta(hours=5), category_hint="food", extra={"scope": "local"})
    state.record(PostDraft(story=first, copy=PostCopy(category="food", headline="h", caption="c", first_comment=""), writer="template"),
                 PublishResult(ok=True, publisher="dryrun", post_id="1"), now - timedelta(hours=4), now.astimezone(settings.tz).date().isoformat())
    second = Story(id="a1", source="WFAA", source_kind="rss", title="Fort Worth restaurant will reopen nearly three years after hotel explosion",
                   summary="Musume in downtown Fort Worth reopens after the hotel explosion in Fort Worth.", url="https://www.wfaa.com/y",
                   published=now - timedelta(hours=1), category_hint="food", extra={"scope": "local"})
    kept, dropped = filter_stories([second], settings, state, now)
    assert not kept and dropped and dropped[0][1].startswith("same story already posted")


def test_a_story_the_session_skipped_is_not_drafted_again(settings, now):
    from datetime import timedelta
    from ftworthtv.filters import filter_stories
    from ftworthtv.models import Story
    from ftworthtv.state import State
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    state = State(settings.state_path)
    story = Story(id="d1", source="WFAA Sports", source_kind="rss", title="Dallas installs 10 new hydration stations at White Rock Lake",
                  summary="Ten new hydration stations at White Rock Lake Park in Dallas, North Texas.", url="https://www.wfaa.com/z",
                  published=now - timedelta(hours=1), category_hint="community", extra={"scope": "dfw"})
    state.mark_skipped("d1", "a Dallas park amenity is not Fort Worth news", now)
    kept, dropped = filter_stories([story], settings, state, now)
    assert not kept and dropped[0][1] == "skipped by the reviewing session"


def test_another_citys_government_is_that_citys_news():
    from ftworthtv.filters import other_metro_local
    assert other_metro_local("Austin Mayor Pro Tem announces resignation, run for Texas Senate")
    assert other_metro_local("Houston City Council approves $7 billion budget")
    assert not other_metro_local("Fort Worth City Council approves budget")
    assert not other_metro_local("Texas Senate passes property tax cut")


def test_another_citys_ballot_fight_is_that_citys_news():
    from ftworthtv.filters import other_metro_local
    assert other_metro_local("Austin voter files lawsuit challenging approved Prop J")
    assert not other_metro_local("Tarrant County voters approve $1.2 billion bond")


def test_three_headlines_about_one_reopening_are_one_story():
    from ftworthtv.filters import same_story
    assert same_story("Downton Fort Worth restaurant reopens three years after an explosion",
                      "Musume restaurant reopens 3 years after hotel blast in downtown Fort Worth")
    assert not same_story("Musume restaurant reopens 3 years after hotel blast in downtown Fort Worth",
                          "Fort Worth restaurant week returns with 3 new spots downtown")


def test_a_gift_guide_is_not_news():
    from ftworthtv.filters import shopping_guide
    assert shopping_guide("The Top Texas Gifts of 2026", "https://www.texasmonthly.com/style/top-texas-gift-guide-2026/")
    assert shopping_guide("Best gifts for the Cowboys fan in your life")
    assert not shopping_guide("Fort Worth toy drive collects 4,000 gifts for Tarrant County kids")


def test_a_conference_name_does_not_make_a_georgia_story_texas_news(settings, now):
    from datetime import timedelta
    from ftworthtv.filters import filter_stories
    from ftworthtv.models import Story
    from ftworthtv.state import State
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    georgia = Story(id="g1", source="ESPN College Football", source_kind="rss", title="Georgia AG encourages SEC to take 'action' vs. LSU, 'including expulsion'",
                    summary="The Georgia Attorney General blasted LSU in a letter to SEC commissioner Greg Sankey.", url="https://www.espn.com/a",
                    published=now - timedelta(hours=1), category_hint="sports", extra={"national": True})
    cowboys = Story(id="c1", source="ESPN NFL", source_kind="rss", title="Cowboys beat Eagles 24-17 as Dak Prescott throws three touchdowns",
                    summary="The Dallas Cowboys beat the Philadelphia Eagles at AT&T Stadium in Arlington, Texas.", url="https://www.espn.com/b",
                    published=now - timedelta(hours=1), category_hint="sports", extra={"national": True})
    kept, dropped = filter_stories([georgia, cowboys], settings, State(settings.state_path), now)
    assert [s.id for s in kept] == ["c1"] and dropped and dropped[0][0].id == "g1"
