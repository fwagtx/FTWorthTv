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
    # Texas-wide stories are kept at a lower weight with a non-local scope, instead of being dropped
    texas = by_title.get("Texas Legislature weighs statewide property tax changes")
    assert texas is not None and texas.extra.get("scope") == "texas" and texas.weight < 1.0
    # ... but another DFW city's school board is that city's government (Nov 26: the owner skips another city's government)
    assert reasons.get("Dallas ISD trustees debate new school start times") == "another city's government"
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


def test_a_hire_announcement_is_not_news_unless_the_role_is_public():
    from ftworthtv.filters import personnel_move
    assert personnel_move("Unbound Now names Andrea Sparks to executive leadership team")
    assert personnel_move("Acme Bank promotes Jane Doe to chief lending officer")
    assert not personnel_move("Fort Worth names Eddie Garcia police chief")
    assert not personnel_move("TCU names new head coach after Dykes exit")
    assert not personnel_move("Keller ISD board names interim superintendent")


def test_a_story_a_daily_cap_held_back_gets_a_second_day(settings, now):
    from datetime import timedelta
    settings.since_hours = 14
    yesterday = now - timedelta(hours=20)
    held = Story(id="meals", source="Fort Worth ISD", source_kind="rss", title="Fort Worth ISD serves free meals during Thanksgiving break",
                 summary="Students can pick up free meals at campuses during the break, the district said.", url="https://x/meals",
                 published=yesterday, always_relevant=True)
    plain = Story(id="library", source="Fort Worth ISD", source_kind="rss", title="Fort Worth ISD opens a new library at Paschal High",
                  summary="The library opened Monday, the district said.", url="https://x/library", published=yesterday, always_relevant=True)
    stale = Story(id="lot", source="Fort Worth ISD", source_kind="rss", title="Fort Worth ISD repaves the parking lot at Arlington Heights High",
                  summary="The work wraps up this week, the district said.", url="https://x/lot", published=now - timedelta(hours=40), always_relevant=True)
    state = State(settings.state_path)
    state.defer("meals", held.title, "daily cap for community reached", now - timedelta(hours=12))
    state.defer("lot", stale.title, "daily cap for community reached", now - timedelta(hours=30))
    kept, dropped = filter_stories([held, plain, stale], settings, state, now)
    assert [s.id for s in kept] == ["meals"]                                  # the cap-held story gets its second day
    reasons = {s.id: r for s, r in dropped}
    assert reasons["library"].startswith("older than") and reasons["lot"].startswith("older than")   # the window holds for the rest


def test_a_stale_dated_forecast_and_a_bare_listing_leave_the_pool_before_ranking(settings, now):
    stale = Story(id="fc", source="NWS", source_kind="nws_forecast", title="Fort Worth forecast for Tuesday, November 17", summary="Sunny.",
                  url="https://x/fc", published=now, official=True, always_relevant=True)
    bare = Story(id="ev", source="Ticketmaster", source_kind="event", title="Women's Funkytown Showdown at Dickies Arena", summary="Sun, Nov 22 12:00 PM",
                 url="https://x/ev", published=now, always_relevant=True)
    pictured = Story(id="ev2", source="Ticketmaster", source_kind="event", title="Cody Johnson at Dickies Arena", summary="Sat, Nov 28 7:00 PM",
                     url="https://x/ev2", published=now, always_relevant=True, image_url="https://x/ev2.jpg", image_policy="source_image", image_license="ticketmaster")
    kept, dropped = filter_stories([stale, bare, pictured], settings, State(settings.state_path), now)
    reasons = {s.id: r for s, r in dropped}
    assert reasons["fc"] == "dated for a day that has passed" and reasons["ev"] == "event listing without its own picture"
    assert [s.id for s in kept] == ["ev2"]


def test_an_article_outranks_the_channels_video_of_the_same_story(now):
    # the owner wants original posts: a video can only be shared as a link, so the article twin (with its own picture) goes first
    art = Story(id="a", source="Fort Worth ISD", source_kind="rss", title="Fort Worth ISD serves free meals during Thanksgiving break", summary="",
                url="https://x/a", published=now, always_relevant=True, category="community")
    vid = Story(id="v", source="Fort Worth ISD", source_kind="video", title="Fort Worth ISD to serve free meals over Thanksgiving Break", summary="",
                url="https://youtube.com/watch?v=x", published=now, always_relevant=True, category="community")
    assert [s.id for s in rank([vid, art], now)] == ["a", "v"]


def test_another_metro_stations_forecast_page_is_that_metros_weather():
    from ftworthtv.filters import other_metro_forecast
    assert other_metro_forecast("KVUE Austin", "Forecast: What to expect across Texas as Thanksgiving travel gets underway",
                                "https://www.kvue.com/article/weather/forecast/austin-weather-central-texas-forecast/269-43840919")
    assert other_metro_forecast("KHOU 11 Houston", "Cold front arrives Sunday", "https://www.khou.com/article/weather/cold-front/285-1")
    assert not other_metro_forecast("NBC 5 DFW", "Forecast: Cold front brings freezing temps to North Texas", "https://www.nbcdfw.com/weather/x/")
    assert not other_metro_forecast("KXAN Austin", "Texas Senate passes property tax bill", "https://www.kxan.com/news/texas-politics/x/")


def test_a_column_label_marks_a_column():
    from ftworthtv.filters import column_label
    assert column_label("Bob on Business: Biz in the front, party in the back as One University Place breaks ground")
    assert column_label("Opinion: Fort Worth needs a bigger convention center")
    assert column_label("Commentary | The Stockyards are changing")
    assert not column_label("Fort Worth council votes on the budget")
    assert not column_label("Review of the year: the biggest Fort Worth stories")


def test_a_sale_guide_is_a_shopping_guide_not_news():
    from ftworthtv.filters import shopping_guide
    assert shopping_guide("A Guide to the Best Black Friday Streaming Deals: See Platforms, Prices & Plans")
    assert shopping_guide("Eureka Ergonomic Has Black Friday Deals to Give Your Space the Upgrade It Needs")
    assert not shopping_guide("Fort Worth council approves deal with developer for downtown tower")
    assert not shopping_guide("Rangers deal pitcher to the Yankees for two prospects")


def test_a_watch_it_free_pitch_is_an_ad_not_news():
    """Nov 26, render 277: Billboard's halftime-show 'Watch Online for Free' piece from its product-recommendations section."""
    from ftworthtv.filters import shopping_guide
    t = "Goo Goo Dolls’ Halftime Show at the Chiefs vs. Bills Thanksgiving Game: Watch Online for Free"
    assert shopping_guide(t)
    assert shopping_guide("Goo Goo Dolls halftime show", "https://www.billboard.com/culture/product-recommendations/goo-goo-dolls-1236389230/")
    assert shopping_guide("How to watch the Cowboys game without cable")
    assert shopping_guide("Stream the Macy's parade for free: every option")
    assert not shopping_guide("Fort Worth library offers free movie screenings this weekend")
    assert not shopping_guide("Watch: Fort Worth firefighters free a dog trapped in a storm drain")
    assert not shopping_guide("Fort Worth police release video of the chase", "https://www.nbcdfw.com/news/local/fort-worth-chase/3912345/")


def test_another_metros_local_story_is_that_metros_news_whatever_the_beat(settings, now):
    from ftworthtv.filters import other_metro_title
    assert other_metro_title("HPD: Teens find man's body in elevator shaft of abandoned downtown Houston building")
    assert other_metro_title("Harris County opens new animal shelter")
    assert not other_metro_title("Texas Senate passes property tax bill in Austin")        # the state's news names the state
    assert not other_metro_title("Fort Worth and Houston split the state's new water money")
    houston = Story(id="h", source="KHOU 11 Houston", source_kind="rss", title="HPD: Teens find man's body in elevator shaft of abandoned downtown Houston building",
                    summary="Houston police said the teens were exploring the building Friday night when they found the body.", url="https://x/h", published=now)
    kept, dropped = filter_stories([houston], settings, State(settings.state_path), now)
    assert not kept and dropped[0][1] in ("another metro's local story", "other-metro crime, not statewide", "not local enough (relevance 0 < 2)")


def test_an_outlets_digest_is_not_a_story():
    from ftworthtv.filters import digest_title
    assert digest_title("Hot dog chain Portillo's closes 2 DFW restaurants and more top stories")
    assert digest_title("5 things to know this Monday in Fort Worth")
    assert not digest_title("Hot dog chain Portillo's closes 2 DFW restaurants")


def test_a_crash_on_another_metros_stretch_of_i_35_is_that_metros_news(settings, now):
    from datetime import timedelta
    crash = Story(id="sa", source="KENS 5 San Antonio", source_kind="rss", title="One person dead in 18-wheeler explosion at I-35 on San Antonio's northeast side, police say",
                  summary="San Antonio police said the truck caught fire after a crash on Interstate 35 early Saturday.", url="https://x/sa", published=now - timedelta(hours=1))
    kept, dropped = filter_stories([crash], settings, State(settings.state_path), now)
    assert not kept and ("other-metro" in dropped[0][1] or "another metro" in dropped[0][1] or "not local enough" in dropped[0][1])


def test_another_dfw_citys_police_blotter_is_not_ours():
    from ftworthtv.filters import another_citys_blotter
    assert another_citys_blotter("Juvenile shot in vehicle in stable condition, Dallas police say no arrests made yet")
    assert another_citys_blotter("Police shot at suspected burglars in Far East Dallas, no injuries reported")
    assert not another_citys_blotter("Dallas Cowboys fan dies after altercation during 49ers game, Arlington police say")   # a death runs
    assert not another_citys_blotter("Fort Worth police: one person shot in stable condition near the Stockyards")          # ours runs


def test_sportsbook_picks_and_promos_are_not_news():
    from ftworthtv.filters import betting_promo
    assert betting_promo("Cowboys vs. Eagles odds, picks, best bets: Proven model reveals NFL Week 12 predictions")
    assert betting_promo("F1 odds, predictions: Get almost $4,000 in bonuses from betting apps, sportsbooks for Las Vegas")
    assert betting_promo("NFL Week 11 last-minute picks, best bets: Fernando Mendoza's Raiders face tough task")
    assert betting_promo("Mavericks vs. Lakers", "Use this DraftKings promo code to claim bonus bets before tipoff")
    assert betting_promo("Cowboys vs. Commanders prediction, pick, odds, spread: Dallas looks to stay alive")   # singular "pick" slipped through
    assert betting_promo("Week 12 NFL score predictions, best picks today: Expert reveals exact scores")
    assert not betting_promo("Cowboys beat Eagles 31-24 as Prescott throws three touchdowns")
    assert not betting_promo("Mavericks beat the odds to win in overtime")
    assert betting_promo("Prisco's Week 11 NFL picks: 49ers over Vikings, Cowboys rout Titans, Panthers edge Falcons")   # Nov 22
    assert not betting_promo("Cowboys pick up a fifth-round pick in the trade")
    assert betting_promo("NFL Week 11 upset alert: Can Titans shock Cowboys? Two straight losses for Steelers?")   # Nov 22
    assert not betting_promo("Rangers games will stay on FanDuel Sports Network Southwest next season")
    assert not betting_promo("Texas Lottery: Powerball jackpot climbs to $900 million")


def test_a_teams_game_notes_sheet_is_not_a_story():
    from ftworthtv.filters import game_notes
    for title in ("Postgame Notes - vs. Utah", "Pregame Notes: TCU at Baylor", "Game Notes vs. Kansas State", "Notes & Quotes: Utah",
                  "Box Score: TCU 24, Utah 31", "Week 13 Notes", "TCU Football Weekly Release: Baylor"):
        assert game_notes(title), title
    for title in ("Stats: How are the Texas Longhorns performing in the 2026 season?",
                  "College football grades: Texas earns 'A' for dominant win, Indiana gets 'D' on Week 12 report card"):
        assert game_notes(title), title                                              # Nov 22: KXAN's explainer, CBS's grades column
    for title in ("TCU Falls to Utah in Home Finale", "Mavericks notebook: Flagg's rookie season so far",
                  "Fort Worth council notes concerns over budget"):
        assert not game_notes(title), title


def test_an_experts_view_is_not_the_story_and_cold_fronts_are_weather():
    from datetime import datetime, timezone
    from ftworthtv.filters import expert_commentary, infer_category
    from ftworthtv.models import Story
    assert expert_commentary("Medical ethicist weighs in on North Texas transplant case involving brain-dead woman")
    assert expert_commentary("Medical ethics expert weighs in on Dallas organ donation dispute")
    assert not expert_commentary("Fort Worth mayor weighs in on the budget vote")          # an official's view is news
    s = Story(id="cf", source="CBS Texas", source_kind="video", title="Cold fronts in store for North Texas this week",
              summary="A cold front on Sunday will keep temps across North Texas in the 60s into Monday.", url="https://x",
              published=datetime(2026, 11, 22, tzinfo=timezone.utc))
    assert infer_category(s) == "weather"                                                   # was "business" ("in store")


def test_two_results_naming_the_same_teams_are_one_game():
    """Render 115, Nov 22: KXAN's 'No. 5 Texas avoids letdown, routs Arkansas 45-3 on Senior Day' was drafted the morning
    after 'Arch Manning steps up as Longhorns blow out Arkansas' went out."""
    from ftworthtv.filters import same_game
    assert same_game("No. 5 Texas avoids letdown, routs Arkansas 45-3 on Senior Day", "Arch Manning steps up as Longhorns blow out Arkansas")
    assert same_game("TCU Falls to Utah in Home Finale", "Horned Frogs come up short against No. 2 Utah")
    assert not same_game("Sarkisian hopes to send Texas seniors out in style against Arkansas", "Arch Manning steps up as Longhorns blow out Arkansas")
    assert not same_game("Mavericks top the Clippers 110-100", "Stars edge Blues in shootout")


def test_a_feature_naming_a_big_event_is_not_the_event_and_a_second_recap_is_the_same_game():
    """Render 116, Nov 22: ESPN's 'From 100 losses to ... building a World Series contender? Why Mike Trout has new hope'
    passed on the watchlist term 'world series'; 'Lone unbeaten Utah seals spot in Big 12 title game win over TCU' came
    after 'TCU Falls to Utah in Home Finale' had gone out."""
    from ftworthtv.filters import _HYPOTHETICAL_RE, same_game
    assert _HYPOTHETICAL_RE.search("From 100 losses to ... building a World Series contender? Why Mike Trout has new hope for Angels")
    assert not _HYPOTHETICAL_RE.search("Rangers win the World Series in Game 5")
    assert same_game("Lone unbeaten Utah seals spot in Big 12 title game win win over TCU", "TCU Falls to Utah in Home Finale")


def test_a_final_score_is_sports_and_setting_a_fire_is_crime():
    """Nov 26, render 278: WFAA Sports' Bourque goal story and WFAA's Family Dollar arson attempt were both filed as "other",
    so the hockey story could not take a sports text card and the arson attempt slipped past the crime cap."""
    from ftworthtv.filters import infer_category
    from ftworthtv.models import Story

    def cat(title, source="WFAA", hint=None):
        st = Story(id="x", title=title, url="u", source=source, source_kind="rss", summary="")
        st.category_hint = hint
        return infer_category(st)

    assert cat("Mavrik Bourque returns to Dallas and scores his first goal for Nashville in 3-1 win") == "sports"
    assert cat("Stars beat the Blues 4-2 behind Robertson's hat trick") == "sports"
    assert cat("Man attempts to set fire to Dallas Family Dollar, DFR says") == "crime"
    assert cat("Arson investigators look into east Fort Worth church fire") == "crime"
    assert cat("Fort Worth council approves budget in 7-2 vote") != "sports"
    assert cat("Tarrant County home prices down 5-10% from last year") != "sports"
    assert cat("Rangers beat Astros 5-4 in 10 innings") == "sports"
    assert cat("Home workshop sparks early morning fire on Thanksgiving in Fort Worth") == "breaking"


def test_the_wfaa_sports_feed_is_a_sports_feed():
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "sources.yaml").read_text())
    feeds = [f for group in cfg.values() if isinstance(group, list) for f in group if isinstance(f, dict)]
    wfaa = [f for f in feeds if f.get("name") == "WFAA Sports"]
    assert wfaa and wfaa[0].get("category_hint") == "sports"


def test_the_holiday_is_when_not_what_a_story_is():
    """Nov 26, render 281: on Thanksgiving a Fort Worth house fire with a rescue (WFAA) and a holiday-crash study (CultureMap) were
    filed as community for "Thanksgiving" and "holiday" (title words count double) and held by the community cap."""
    from ftworthtv.filters import fire_incident, infer_category
    from ftworthtv.models import Story

    def cat(title, summary="", source="WFAA"):
        return infer_category(Story(id="x", title=title, url="u", source=source, source_kind="rss", summary=summary))

    fire = "Neighbors kick in door to rescue elderly couple as Thanksgiving fire burns North Texas homes"
    assert fire_incident(fire) and cat(fire) == "breaking"
    assert cat("North Texas leads state in severe holiday crashes on major interstates",
               "Texas interstates saw the most severe crashes over the holidays.", source="CultureMap Fort Worth") == "traffic"
    assert cat("Happy Thanksgiving Fort Worth") == "community"
    assert cat("Thanksgiving dinner served to 500 at Fort Worth shelter by volunteers") == "community"
    assert cat("Christmas in the Garden returns to Fort Worth Botanic Garden") == "events"   # a light show (Nov 26, render 288)
    assert cat("Botanic Garden opens new Japanese garden pavilion for the holidays") == "culture"
    assert not fire_incident("Thanksgiving fire safety tips from Fort Worth firefighters")


def test_a_headline_set_in_another_metro_is_its_news_even_with_texas_in_a_later_clause():
    """Nov 26, render 283: KXAN's "Rabid dog found in San Marcos as Texas rabies cases top 2025 totals" was drafted with a
    photo of a Plaza San Marcos shopping centre's signs."""
    from ftworthtv.filters import other_metro_title
    from ftworthtv.images.subject import plan_subject
    title = "Rabid dog found in San Marcos as Texas rabies cases top 2025 totals"
    assert other_metro_title(title)
    assert other_metro_title("Shooting in downtown Houston leaves 3 hurt, police say")
    assert not other_metro_title("Texas Senate passes property tax bill in Austin")
    assert not other_metro_title("Austin-based Dell to cut 1,000 Texas jobs")
    assert not other_metro_title("Fort Worth man arrested in Houston after chase")
    plan = plan_subject(title, "A dog in San Marcos tested positive for rabies as Texas surpassed last year's total.", "other")
    assert "San Marcos" not in plan.search_names


def test_a_critics_review_of_a_named_work_is_a_column():
    """Nov 26, render 284: the Fort Worth Report's film review reached the photo step."""
    from ftworthtv.filters import column_label
    assert column_label("‘Club Kid’ Review: From dance beats to heartbeats, Jordan Firstman’s vibrant and touching debut feature")
    assert column_label("Movie review: 'Wicked: For Good' sticks the landing")
    assert column_label("Restaurant Review: A new Tex-Mex spot on Magnolia Avenue")
    assert not column_label("Review of the year: the biggest Fort Worth stories")
    assert not column_label("Fort Worth council to review zoning plan for Stockyards")
    assert not column_label("'Wicked: For Good' tops the Thanksgiving box office")


def test_a_reactions_roundup_is_not_news_and_an_injury_exit_is_a_happening():
    """Nov 26, render 290: Jason Kelce's reactions to the Eagles' win and Cooper DeJean's concussion, both from the game the
    page had already posted, drafted with a text card and the AT&T Stadium stands."""
    from ftworthtv.filters import roundup_column
    from ftworthtv.images.subject import happened
    assert roundup_column("'Happy Thanksgiving America': Jason Kelce leads reactions to Eagles' win over Cowboys")
    assert roundup_column("Fans react to Cowboys' collapse against the Eagles")
    assert roundup_column("NFL world reacts to Cowboys' fourth-down call")
    assert not roundup_column("Fort Worth residents react to council's budget vote")
    assert happened("Eagles DB DeJean (concussion) exits win early at Cowboys", "rss")
    assert not happened("Walgreens exits two Fort Worth locations next month", "rss")


def test_a_road_closed_last_night_has_reopened_by_morning():
    """Nov 27, render 295: WFAA's 8:55 p.m. Denton I-35 closure (crews cleaning the roadway) was drafted for 8:02 a.m. as crime."""
    from datetime import datetime, timezone
    from ftworthtv.filters import infer_category, stale_closure
    from ftworthtv.models import Story
    now = datetime(2026, 11, 27, 13, 14, tzinfo=timezone.utc)
    st = Story(id="x", title="Northbound I-35 closed in Denton due to 'hazard' damaging tires, police say", url="u", source="WFAA",
               source_kind="rss", summary="Denton Police say drivers will have to exit at Fort Worth Drive as crews clean the roadway.",
               published=datetime(2026, 11, 27, 2, 55, tzinfo=timezone.utc))
    assert stale_closure(st, now) and infer_category(st) == "traffic"
    assert not stale_closure(st, datetime(2026, 11, 27, 4, 0, tzinfo=timezone.utc))          # an hour later it was news
    planned = Story(id="y", title="I-30 lanes closed this weekend for bridge work in west Fort Worth", url="u", source="WFAA",
                    source_kind="rss", summary="TxDOT says the lanes will be closed through Monday.",
                    published=datetime(2026, 11, 26, 20, 0, tzinfo=timezone.utc))
    assert not stale_closure(planned, now)


def test_another_citys_arson_attempt_is_its_blotter_and_its_skyline_is_no_sports_picture():
    """Nov 27, render 297: a day-old Dallas Family Dollar arson attempt (no one hurt) and a Frisco flag-football feature with the
    Dallas skyline."""
    from ftworthtv.filters import another_citys_blotter
    from ftworthtv.images.library import topics_for
    assert another_citys_blotter("Man attempts to set fire to Dallas Family Dollar, DFR says")
    assert not another_citys_blotter("Man arrested after setting fire to Fort Worth apartment complex")
    assert not another_citys_blotter("Arson suspect sought after fire kills 2 in Dallas")
    t = "A groundbreaking new chapter for girls' flag football arrives in Frisco"
    assert "dallas-skyline" not in topics_for(t.lower(), "sports", "dfw", title=t)


def test_the_winning_sides_recap_is_the_same_game_and_predictions_are_not_news():
    """Nov 27, render 298: ESPN's Eagles-side recap and the Cowboys channel's schedule predictions the morning after the
    page posted the 39-38 result; Jerry Jones backing his coach is news."""
    from ftworthtv.filters import hypothetical_sports, same_game
    posted = "Cowboys blow 21-point lead in 39-38 Thanksgiving loss to Eagles"
    assert same_game("Joe Milton has huge game as Eagles shock Cowboys on Thanksgiving", posted)
    assert not same_game("Cowboys' Jones backing Schottenheimer despite 'damning setbacks'", posted)
    assert not same_game("Eagles beat Commanders 24-20", posted)
    assert hypothetical_sports("Predicting the Cowboys' Tough Final Stretch | Special Edition")
    assert hypothetical_sports("2027 NFL Draft: Remaining games that will determine the draft order, including No. 1 overall")
    assert not hypothetical_sports("Cowboys' Jones backing Schottenheimer despite 'damning setbacks'")


def test_a_tiered_ranking_is_a_column_and_another_metros_things_to_do_is_its_event():
    """Nov 27, render 304: CBS Sports' tiered ranking of Cowboys coach candidates, and KXAN's Austin watch party with Kyle Field."""
    from ftworthtv.filters import other_metro_url, roundup_column
    from ftworthtv.images.library import drop_stadiums_off_the_field
    assert roundup_column("A premature, unauthorized, tiered ranking of every possible Dallas Cowboys coach -- should Jerry Jones need it")
    assert not roundup_column("Cowboys' Jones backing Schottenheimer despite 'damning setbacks'")
    assert other_metro_url("https://www.kxan.com/things-to-do/state-theatre-to-host-free-texas-vs-texas-am-rivalry-watch-party/")
    assert not other_metro_url("https://www.wfaa.com/things-to-do/fort-worth-stock-show/")
    assert drop_stadiums_off_the_field(["texas-am"], "State Theatre to host free Texas vs. Texas A&M rivalry watch party") == []


def test_an_agencys_name_does_not_make_another_metros_crime_statewide(settings, now):
    """Nov 27, render 305: KENS 5's "Suspect arrested after alleged shooting, pursuit involving DPS trooper in downtown San
    Antonio" passed as statewide news for "A Texas DPS trooper" in its summary. DPS works every city; the story is San Antonio's."""
    from ftworthtv.filters import set_in_other_metro, statewide
    t = "Suspect arrested after alleged shooting, pursuit involving DPS trooper in downtown San Antonio"
    summ = ("A Texas DPS trooper discharged a weapon while pursuing a suspect who allegedly fired at a victim in downtown "
            "San Antonio early Friday, police said.")
    kens = Story(id="k", source="KENS 5 San Antonio", source_kind="rss", title=t, summary=summ,
                 url="https://www.kens5.com/article/news/local/shooting-at-alamo-plaza-downtown-san-antonio/273-b2ff13d7",
                 published=now, extra={"scope": "texas"})
    assert set_in_other_metro(t, summ)
    assert not statewide(kens)
    kept, dropped = filter_stories([kens], settings, State(settings.state_path), now)
    assert not kept and dropped[0][1] in ("other-metro crime, not statewide", "another metro's local story",
                                          "not local enough (relevance 0 < 2)")
    # the headline alone need not name the city: the summary's first sentence sets it there
    assert set_in_other_metro("Suspect arrested after pursuit involving DPS trooper", summ)
    # a word about the story's reach still carries it, wherever it started
    amber = Story(id="a", source="KENS 5 San Antonio", source_kind="rss", title="Amber Alert issued for 4-year-old taken in San Antonio",
                  summary="Texas DPS issued an Amber Alert early Friday.", url="https://x/a", published=now)
    assert statewide(amber)
    # an agency story no other metro claims stays statewide
    dps = Story(id="d", source="KXAN Austin", source_kind="rss", title="Texas DPS warns of new driver license text scam",
                summary="The Texas DPS says the texts ask drivers to pay a fake renewal fee.", url="https://x/d", published=now)
    assert statewide(dps)
    # our own city named: not another metro's story
    assert not set_in_other_metro("DPS trooper hurt in crash on I-35W in Fort Worth",
                                  "The trooper was taken to a hospital in Fort Worth after the crash near San Antonio's convoy.")


def test_another_citys_community_feature_and_the_same_vote_of_confidence(settings, now):
    """Nov 27, render 309: WFAA's Dallas ministry Thanksgiving dinner was drafted as regional news with a stock turkey plate,
    and WFAA's "Jerry Jones says he still believes in Brian Schottenheimer ..." six hours after ESPN's "Cowboys' Jones backing
    Schottenheimer despite 'damning setbacks'" went out."""
    from ftworthtv.filters import another_citys_community_feature, same_vote_of_confidence
    from ftworthtv.images.subject import happened
    dallas = "Forced to flee their countries, Dallas gave them a place at the table this Thanksgiving"
    assert another_citys_community_feature(dallas)
    assert another_citys_community_feature("'A little bit of joy': Dallas Animal Shelter dogs get a Thanksgiving feast")
    assert not another_citys_community_feature("North Texas community rallies to keep local students in Macy's Thanksgiving Day Parade")
    assert not another_citys_community_feature("Fort Worth and Dallas churches team up for toy drive")
    assert not another_citys_community_feature("Grapevine family's lights display draws crowds")
    story = Story(id="wfaa", source="WFAA", source_kind="rss", title=dallas,
                  summary="For 16 years, a Dallas couple and their ministry have welcomed hundreds of refugees to the Thanksgiving table.",
                  url="https://www.wfaa.com/article/life/heartwarming/forced-to-flee/287-943ef796", published=now)
    kept, dropped = filter_stories([story], settings, State(settings.state_path), now)
    assert not kept and dropped[0][1] == "another city's community feature"
    assert happened(dallas)                          # a dinner that took place is a happening: no stock plate
    assert not happened("Where to find Thanksgiving dinner in Fort Worth")
    posted = "Cowboys' Jones backing Schottenheimer despite 'damning setbacks'"
    assert same_vote_of_confidence("Jerry Jones says he still believes in Brian Schottenheimer despite mounting meltdowns by Cowboys",
                                   "Jerry Jones says he still believes Brian Schottenheimer is the right coach for the Dallas Cowboys.", posted)
    assert not same_vote_of_confidence("Jerry Jones says Cowboys will sign Micah Parsons to an extension", "", posted)
    assert not same_vote_of_confidence("Rangers back Bochy for 2027 season", "", posted)


def test_a_uniforms_listicle_is_a_column_and_no_other_citys_skyline_stands_in():
    """Nov 27, render 310: ESPN's "Houston's all-black threads top best uniforms of college football Week 13" drafted as Texas
    sports with the Houston skyline."""
    from ftworthtv.filters import roundup_column
    from ftworthtv.images.library import topics_for
    t = "Houston's all-black threads top best uniforms of college football Week 13"
    assert roundup_column(t)
    assert roundup_column("Rams and Cowboys top Week 12 uniforms")
    assert not roundup_column("TCU unveils new uniforms for rivalry game")
    assert not roundup_column("Cowboys top Chiefs 31-28 in throwback uniforms")
    assert not roundup_column("Cowboys top Lions in uniforms")
    assert roundup_column("The top 10 uniforms of rivalry week")
    body = "Houston's threads will blend into the Texas sky for its Week 13 clash against Baylor."
    for cat in ("sports", "community", "crime"):
        topics = topics_for(f"{t} {body}".lower(), cat, "texas", title=t)
        assert not any(x in topics for x in ("houston-skyline", "dallas-skyline", "austin-skyline", "san-antonio-skyline")), (cat, topics)
