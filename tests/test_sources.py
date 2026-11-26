import json

from ftworthtv.examples import _fill, example_stories
from ftworthtv.sources import nws, rss, ticketmaster


def test_rss_parse_extracts_items_images_and_dates(examples_dir, now):
    cfg = {"name": "Fort Worth Report", "always_relevant": True, "image_policy": "none", "weight": 1.0}
    stories = rss.parse_feed(cfg, _fill((examples_dir / "fortworth_report_feed.xml").read_text(), now, now.tzinfo), now)
    assert len(stories) == 7
    bbq = next(s for s in stories if "barbecue" in s.title.lower())
    assert bbq.image_url == "https://example.com/images/bbq.jpg"
    assert bbq.published is not None and bbq.age_hours(now) < 1
    assert bbq.summary.startswith("A family-run smokehouse")
    assert bbq.always_relevant and bbq.image_policy == "none"


def test_rss_thumbnail_extraction(examples_dir, now):
    cfg = {"name": "FOX 4 Dallas-Fort Worth", "weight": 0.8}
    stories = rss.parse_feed(cfg, _fill((examples_dir / "fox4_feed.xml").read_text(), now, now.tzinfo), now)
    herd = next(s for s in stories if "cattle drive" in s.title.lower())
    assert herd.image_url == "https://example.com/images/stockyards.jpg"


def test_nws_alert_parsing_filters_minor_and_keeps_severe(examples_dir, now, settings):
    payload = json.loads(_fill((examples_dir / "nws_alerts.json").read_text(), now, settings.tz))
    stories = nws.parse_alerts(payload, settings.sources["nws"], now)
    assert len(stories) == 1
    alert = stories[0]
    assert alert.is_urgent and alert.source_kind == "nws_alert"
    assert alert.image_url.endswith("KFWS_0.gif") and alert.image_policy == "source_image"
    assert alert.extra["event"] == "Severe Thunderstorm Warning"


def test_nws_forecast_parsing(now, settings):
    payload = {"properties": {"periods": [
        {"name": "Today", "temperature": 72, "temperatureUnit": "F", "shortForecast": "Sunny", "windSpeed": "10 mph", "windDirection": "S",
         "isDaytime": True, "probabilityOfPrecipitation": {"value": 20}, "detailedForecast": "Sunny, with a high near 72."},
        {"name": "Tonight", "temperature": 48, "shortForecast": "Clear", "isDaytime": False}]}}
    story = nws.parse_forecast(payload, now, settings.tz, settings.sources["nws"])
    assert story.id.startswith("forecast-2026-11-19")
    assert "high near 72" in story.summary and story.extra["low"] == 48


def test_ticketmaster_parsing_and_roundup(examples_dir, now, settings):
    payload = json.loads(_fill((examples_dir / "ticketmaster_events.json").read_text(), now, settings.tz))
    events = ticketmaster.parse_events(payload, settings.sources["ticketmaster"], now, settings.tz)
    assert len(events) == 4
    country = next(e for e in events if "Country" in e.title)
    assert country.image_url.endswith("country-16x9.jpg")       # widest 16:9 wins
    assert country.weight > 1.0                                  # Dickies Arena boost
    assert country.extra["venue"] == "Dickies Arena"
    rodeo = next(e for e in events if "Rodeo" in e.title)
    assert rodeo.category_hint == "sports"
    roundup = ticketmaster.roundup_story(events, now, settings.tz)
    assert roundup and roundup.source_kind == "event_roundup" and len(roundup.extra["events"]) == 4


def test_example_stories_loads_everything(settings, now):
    stories = example_stories(settings, now)
    kinds = {s.source_kind for s in stories}
    assert {"rss", "nws_alert", "event", "event_roundup"} <= kinds
    assert len(stories) >= 15


def test_article_parser_reads_og_tags_and_body_image():
    from ftworthtv.sources.article import parse_article
    html = """<html><head><meta property="og:title" content="Suspect Arrested in Robbery"/>
    <meta property="og:description" content="FWPD arrested a 24-year-old man."/>
    <meta property="article:published_time" content="2026-11-16T15:00:00-06:00"/></head>
    <body><main><img src="/logo.svg"><img src="/files/assets/police/booking-photo.jpg">
    <p>Fort Worth Police arrested a 24-year-old man on Monday in connection with a string of robberies on East Lancaster Avenue.</p>
    <p>Short.</p></main></body></html>"""
    info = parse_article(html, "https://police.fortworthtexas.gov/news-articles/x")
    assert info["title"] == "Suspect Arrested in Robbery"
    assert info["image"] == "https://police.fortworthtexas.gov/files/assets/police/booking-photo.jpg"
    assert info["summary"].startswith("Fort Worth Police arrested")
    assert info["published"].year == 2026


def test_article_parser_prefers_og_image():
    from ftworthtv.sources.article import parse_article
    html = '<meta name="twitter:image" content="https://x/y.jpg"><img src="/other.jpg">'
    assert parse_article(html, "https://x/")["image"] == "https://x/y.jpg"


def test_opencities_listing_parser(settings, now):
    from pathlib import Path
    from ftworthtv.sources.opencities import parse_listing
    html = Path(__file__).parent.joinpath("fixtures/opencities_fwpd_listing.html").read_text(encoding="utf-8")
    cfg = {"name": "Fort Worth Police Department", "category_hint": "crime", "official": True, "image_policy": "source_image"}
    stories = parse_listing(html, "https://police.fortworthtexas.gov/news-articles", cfg, now, settings.tz)
    assert len(stories) == 3
    s = stories[0]
    assert s.url.startswith("https://police.fortworthtexas.gov/news-articles/2026/")
    assert s.title and s.summary and s.published is not None and s.published.year == 2026
    assert s.official and s.image_policy == "source_image" and s.category_hint == "crime"
    assert s.extra["generic_image"] is True and s.image_url is None   # the "news release" graphic is not used as the photo


def test_arrest_log_parser_and_roundup(settings):
    from datetime import datetime, timezone
    from pathlib import Path
    from ftworthtv.sources.arrests import clean_charge, parse_entries, roundup_story
    html = Path(__file__).parent.joinpath("fixtures/fwpd_recent_arrests.html").read_text(encoding="utf-8")
    entries = parse_entries(html)
    assert len(entries) == 3
    assert entries[0]["name"] == "DOE, JOHN" and entries[0]["age"] == 40 and entries[0]["booked"].year == 2026
    assert entries[1]["degree"] == "F2" and len(entries[1]["charges"]) == 2
    assert clean_charge(entries[1]["charges"][0]).startswith("Aggravated Assault")
    now = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
    story = roundup_story(entries, now, settings.tz, {"window_hours": 48, "min_degree": "MA", "min_entries": 1})
    assert story and story.source_kind == "arrest_log" and story.extra["entries"][0]["degree"] in ("F2", "F3")
    assert "•" in story.summary


def test_wanted_parsers_skip_juveniles_and_keep_local(settings, now):
    from pathlib import Path
    from ftworthtv.sources.wanted import parse_arlington, parse_dps, parse_fwpd, person_story
    fx = Path(__file__).parent / "fixtures"
    fw = parse_fwpd(fx.joinpath("fwpd_most_wanted.html").read_text(encoding="utf-8"), "https://police.fortworthtexas.gov/Crime-Public-Info/most-wanted", now)
    assert [p["name"] for p in fw] == ["Sample Adult", "Sample Minor"]
    assert fw[0]["charge"] == "Aggravated Robbery" and fw[0]["reward"] == "$2,000" and fw[0]["age"] == 36
    assert fw[0]["image"] == "https://police.fortworthtexas.gov/files/assets/police/v/1/most-wanted/images/2026/sample-adult.png"
    agency = {"name": "Fort Worth Police Department", "city": "Fort Worth"}
    assert person_story(fw[0], agency, "https://x", now, "Fort Worth").source_kind == "wanted"
    assert person_story(fw[1], agency, "https://x", now, "Fort Worth") is None      # 16-year-old: never posted
    ar = parse_arlington(fx.joinpath("arlington_wanted.html").read_text(encoding="utf-8"), "https://www.arlingtontx.gov/x", now)
    assert len(ar) == 2 and ar[0]["name"] == "Sample ONE" and ar[1]["charge"] == "Burglary" and ar[0]["image"].startswith("https://www.arlingtontx.gov/files/")
    dps = parse_dps(fx.joinpath("dps_fugitives.html").read_text(encoding="utf-8"), "https://www.dps.texas.gov/texas10mostwanted/mostwanted/fugitives", now)
    assert len(dps) == 1 and dps[0]["name"] == "Sample Local" and dps[0]["image"].startswith("data:image/jpeg") and dps[0]["reward"] == "$7,500"


def test_wanted_story_renders_as_contained_mugshot_card(settings, now, tmp_path):
    from pathlib import Path
    from PIL import Image
    from ftworthtv.images import plan_image
    from ftworthtv.models import PostDraft
    from ftworthtv.sources.wanted import parse_dps, person_story
    from ftworthtv.state import State
    from ftworthtv.writer import write_copy
    fx = Path(__file__).parent / "fixtures"
    person = parse_dps(fx.joinpath("dps_fugitives.html").read_text(encoding="utf-8"), "https://www.dps.texas.gov/x", now)[0]
    story = person_story(person, {"name": "Texas DPS"}, "https://www.dps.texas.gov/x", now, "Fort Worth")
    story.category = "crime"
    copy, writer = write_copy(story, settings, now)
    assert copy.caption.startswith("Texas DPS is looking for Sample Local, wanted for") and copy.hashtags == []
    assert "Call " in copy.caption and "#" not in copy.caption and "Follow us" not in copy.caption
    settings.offline = False  # the data: URI needs no network
    draft = PostDraft(story=story, copy=copy, writer=writer)
    asset = plan_image(draft, settings, State(tmp_path / "s0.json"), tmp_path / "w0")
    assert asset.provider == "source" and asset.license == "official" and asset.path.name == "post.jpg"   # default: our post card
    settings.brand["card"]["style"] = "plain"
    asset = plan_image(draft, settings, State(tmp_path / "s.json"), tmp_path / "w")
    assert asset.provider == "source" and asset.license == "official"
    with Image.open(asset.path) as im:   # plain style: the booking photo as-is (upscaled), never cropped
        assert im.height > im.width and min(im.size) >= 720
    settings.brand["card"]["style"] = "headline"
    asset = plan_image(draft, settings, State(tmp_path / "s2.json"), tmp_path / "w2")
    with Image.open(asset.path) as im:
        assert im.size == (1080, 1350)


def test_culture_calendar_windows_and_captions(settings):
    from datetime import date, datetime, timezone
    from ftworthtv.sources.calendar import active_moments, load_moments, moment_story
    moments = load_moments(settings)
    assert len(moments) >= 15
    act = active_moments(moments, date(2026, 11, 21))
    slugs = {m["slug"] for m, _, _ in act}
    assert "parade-of-lights" in slugs and "stock-show" not in slugs
    jan = active_moments(moments, date(2027, 1, 20))
    assert {"stock-show", "freeze", "mlk-parade"} <= {m["slug"] for m, _, _ in jan}
    m, start, idx = next(x for x in act if x[0]["slug"] == "parade-of-lights")
    story = moment_story(m, start, idx, datetime(2026, 11, 21, 18, tzinfo=timezone.utc), "Fort Worth")
    assert story.source_kind == "culture" and story.id == "culture-parade-of-lights-2026-0" and "Parade of Lights" in story.title
    # weekly repeats inside a long window get distinct ids
    s2 = active_moments(moments, date(2026, 12, 9))
    xmas = next(x for x in s2 if x[0]["slug"] == "stockyards-christmas")
    assert xmas[2] == 1


def test_daily_category_caps(settings, now, tmp_path):
    from ftworthtv.examples import example_stories
    from ftworthtv.pipeline import run
    settings.brand["content_mix"]["caps_per_day"] = {"events": 0, "sports": 0, "food": 0, "culture": 0, "business": 0, "community": 0, "traffic": 1, "weather": 1}
    settings.max_posts = 5
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    cats = [d.copy.category for d in report.drafts]
    assert cats.count("events") == 0 and cats.count("traffic") <= 1
    assert any("daily cap" in r for _, r in report.skipped)


def test_article_page_photo_credit_is_read():
    from ftworthtv.sources.article import parse_article
    html = """<html><head><meta property="og:title" content="Northwest ISD approves boundaries"><meta property="og:image" content="https://fortworthreport.org/wp-content/uploads/2026/11/nisd.jpg"></head>
    <body><article><figure><img src="/wp-content/uploads/2026/11/nisd.jpg"><figcaption>Parents fill the Northwest ISD boardroom on Monday. (Photo by Matthew Sgroi | Fort Worth Report)</figcaption></figure>
    <p>Northwest ISD trustees voted 6-0 to approve revised high school attendance boundaries for next school year, keeping hundreds of students in place.</p></article></body></html>"""
    info = parse_article(html, "https://fortworthreport.org/2026/11/18/x/")
    assert info["image"] == "https://fortworthreport.org/wp-content/uploads/2026/11/nisd.jpg"
    assert info["credit"] == "Matthew Sgroi"
    html2 = html.replace("(Photo by Matthew Sgroi | Fort Worth Report)", "(Courtesy of Northwest ISD)")
    assert parse_article(html2, "https://x/")["credit"] == "Northwest ISD"


def test_feed_config_sets_photo_policy_and_licence():
    from ftworthtv.sources.rss import parse_feed
    from datetime import datetime, timezone
    xml = """<rss><channel><title>Fort Worth Report</title><item><title>Keller ISD weighs a bond</title><link>https://fortworthreport.org/2026/11/20/keller-isd-bond/</link>
    <description>Trustees will vote next month on a $300 million bond package.</description></item></channel></rss>"""
    s = parse_feed({"name": "Fort Worth Report", "image_policy": "source_image", "image_license": "cc-by-nc-nd", "fetch_article": True}, xml, datetime(2026, 11, 20, tzinfo=timezone.utc))[0]
    assert s.image_policy == "source_image" and s.image_license == "cc-by-nc-nd"


def test_a_photographer_named_twice_by_the_page_is_credited_once():
    from ftworthtv.sources.article import photo_credit
    html = '<figure><img src="x.jpg"><figcaption><span>Credit:</span> Bob Daemmrich Bob Daemmrich for The Texas Tribune</figcaption></figure>'
    assert photo_credit(html, {}) == "Bob Daemmrich for The Texas Tribune"
    assert photo_credit('<figcaption>Photo by Jane Doe / Fort Worth Report</figcaption>', {}) == "Jane Doe"


def test_a_bot_challenge_or_an_empty_body_is_a_failure_not_a_quiet_feed():
    from ftworthtv.sources.rss import feed_problem
    waf = b'<!DOCTYPE html><html><head><script>window.awsWafCookieDomainList = [];</script></head></html>'
    assert feed_problem(202, waf) == "blocked by a bot challenge (HTTP 202)"
    assert feed_problem(200, b"<html><title>Just a moment...</title></html>").startswith("blocked by a bot challenge")
    assert feed_problem(200, b"") == "empty body (HTTP 200)"
    assert feed_problem(200, b'<?xml version="1.0"?><rss><channel><title>x</title></channel></rss>') is None


def test_feeds_use_the_quick_session_so_a_tarpit_costs_one_timeout():
    from ftworthtv import http
    retry = http.quick_session().get_adapter("https://example.com/feed").max_retries
    assert retry.read == 0 and retry.total == 1
    assert http.session().get_adapter("https://example.com/feed").max_retries.total == 3     # pages and photos keep their retries


def test_a_teaser_story_is_recategorized_after_its_lead_is_read(settings, now, monkeypatch):
    """Nov 24, render 205: NBC 5's "Affidavit: Dallas mother ambushed on her birthday by brother-in-law, nephew" was "other" on
    its teaser; the article lead made it crime, and the day's crime posts were used up, but it went out as "other"."""
    from datetime import timedelta
    from ftworthtv.models import Story
    from ftworthtv.pipeline import run
    import ftworthtv.sources.article as article
    story = Story(id="aff1", source="NBC 5 DFW", source_kind="rss", url="https://www.nbcdfw.com/news/local/x/1/", published=now - timedelta(hours=1),
                  title="Affidavit: Fort Worth mother ambushed on her birthday by brother-in-law, nephew",
                  summary="What first raised fears of road rage was an alleged family ambush.")
    def lead(s, min_len=160):
        s.summary = ("Police say a Fort Worth mother of four was shot and killed while driving home from work on her birthday. "
                     "Police arrested a suspect on a murder charge on Sunday.")
        return s
    monkeypatch.setattr(article, "enrich_summary", lead)
    settings.offline = False
    settings.brand["content_mix"]["caps_per_day"] = {"crime": 0}
    report = run(settings, now=now, stories=[story], publisher_name="dryrun")
    assert not report.drafts
    assert any(s.id == "aff1" and r == "daily cap for crime reached" for s, r in report.skipped)


def test_one_weather_story_a_morning(settings, now, monkeypatch):
    """Nov 25, render 227: CBS Texas's YouTube "Freezing temps hit parts of North Texas" an hour after CBS News Texas's freeze warning."""
    from datetime import timedelta
    from ftworthtv.pipeline import _recent_weather_story
    from ftworthtv.state import State
    state = State(settings.state_path)
    state.data.setdefault("posted", {})["w1"] = {"category": "weather", "kind": "rss", "at": (now - timedelta(hours=1)).isoformat()}
    assert _recent_weather_story(state, now)
    assert not _recent_weather_story(state, now + timedelta(hours=7))
    state.data["posted"]["w1"]["kind"] = "nws_forecast"
    assert not _recent_weather_story(state, now)


def test_a_numbered_seats_race_is_the_same_news_until_a_decision():
    """Nov 25: the Fort Worth Report's "Texas Supreme Court mulls candidate's eligibility in House 93 race" was drafted the
    morning after FOX 4's "Texas House District 93 winner remains unknown amid eligibility dispute" went out."""
    from ftworthtv.filters import same_seat_news
    posted = "Texas House District 93 winner remains unknown amid eligibility dispute"
    assert same_seat_news("Texas Supreme Court mulls candidate’s eligibility in House 93 race", "", posted)
    assert not same_seat_news("Texas Supreme Court rules Lomick ineligible in House 93 race", "", posted)       # a decision is news
    assert not same_seat_news("Lomick sworn in as House District 93 representative", "", posted)
    assert not same_seat_news("Texas Senate District 9 race heads to runoff", "", posted)                     # another seat


def test_a_campaigns_headshots_on_a_newsroom_page_are_not_the_newsrooms():
    """Nov 25: the Fort Worth Report's House 93 story carried the candidates' headshots credited "Ericka Lomick and Alan
    Blaylock campaigns"; the Report's licence covers its own photographers' work."""
    from ftworthtv.images import _THIRD_PARTY_RE
    assert _THIRD_PARTY_RE.search("Ericka Lomick and Alan Blaylock campaigns")
    assert _THIRD_PARTY_RE.search("Photo provided by the family")
    assert _THIRD_PARTY_RE.search("Photo via Wikimedia")                          # the old patterns still hold
    assert not _THIRD_PARTY_RE.search("Maria Crane | Fort Worth Report")
    assert not _THIRD_PARTY_RE.search("Leila Saidane for The Texas Tribune")


def test_one_person_spelled_two_ways_holds_the_caption():
    """Nov 24: FOX 4's House District 93 caption went out with "Erick Lomick" and "Erika Lomick" (her name is Ericka)."""
    from ftworthtv.checks import name_spellings
    bad = ("Three weeks after the election, it's still not clear who will represent Tarrant County's Texas House District 93. "
           "Democrat Erika Lomick narrowly beat Republican Alan Blaylock. Erick Lomick suspended her campaign in September.")
    assert name_spellings(bad) == ["one person spelled two ways: Erick Lomick / Erika Lomick"]
    assert name_spellings("Ericka Lomick beat Alan Blaylock in Fort Worth; Fort Worth police said nothing.") == []
    assert name_spellings("John Smith and Jane Smith, his wife, spoke to the Fort Worth City Council.") == []


def test_another_dfw_citys_crime_from_days_ago_is_not_ours():
    """Nov 25 (a Wednesday): WFAA's "North Texas man dead following shooting Sunday, Garland police say"."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ftworthtv.filters import another_citys_old_crime
    wed = datetime(2026, 11, 25, 8, 30, tzinfo=ZoneInfo("America/Chicago"))
    assert another_citys_old_crime("North Texas man dead following shooting Sunday, Garland police say", wed) == "Sunday"
    assert another_citys_old_crime("Man killed in Dallas shooting Tuesday night, police say", wed) == ""      # yesterday
    assert another_citys_old_crime("Fort Worth man killed in shooting Sunday", wed) == ""                     # ours stays


def test_the_citys_stock_notice_graphic_is_not_a_photo():
    """Nov 25: "City seeks input on 2025-26 federal housing funds" came with city-news-request-for-public-comment.jpg."""
    from datetime import datetime, timezone
    from ftworthtv.sources.opencities import parse_listing
    html = ('<article><a href="/news/2026/11/caper"><h2 class="list-item-title">City seeks input on 2025-26 federal housing funds</h2>'
            '<img src="/files/assets/public/v/1/news/images/city-news-request-for-public-comment.jpg?w=300">'
            '<p class="published-on small-text">Published on November 25, 2026</p><p>The City is inviting residents to comment.</p></a></article>')
    story = parse_listing(html, "https://www.fortworthtexas.gov/news", {"name": "City of Fort Worth"}, datetime.now(timezone.utc))[0]
    assert story.image_url is None and story.extra["generic_image"]


def test_an_explainer_about_a_posted_subject_is_the_same_story():
    """Nov 25: WFAA's "What is Weatherford Aerospace?" an hour after the shelter-in-place post about the fire there."""
    from ftworthtv.filters import explainer_of_posted
    posted = "Residents told to shelter in place as crews respond to a fire at Weatherford Aerospace"
    assert explainer_of_posted("What is Weatherford Aerospace?", "", posted)
    assert explainer_of_posted("What we know about the Weatherford Aerospace fire", "", posted)
    assert not explainer_of_posted("Weatherford Aerospace fire under control, officials say", "", posted)   # an update is news
    assert not explainer_of_posted("What is the Fort Worth Stock Show?", "", posted)


def test_one_incident_at_one_place_is_one_story_until_something_new():
    """Nov 25: WFAA's YouTube "A fire was reported at Weatherford Aerospace ..." two hours after the shelter-in-place post."""
    from ftworthtv.filters import same_incident
    posted = "Residents told to shelter in place as crews respond to a fire at Weatherford Aerospace"
    assert same_incident("A fire was reported at Weatherford Aerospace on West 3rd Street in Weatherford, officials said.", "", posted)
    assert not same_incident("Weatherford Aerospace to rebuild after fire, CEO says", "", posted)          # a follow-up is news
    assert not same_incident("Shelter-in-place lifted after Weatherford Aerospace fire", "", posted)
    assert not same_incident("Fire at Fort Worth apartment complex displaces families", "", "Fire at Arlington apartment complex injures two")


def test_a_pundits_prediction_is_not_news():
    """Nov 25, CBS Sports: "Cowboys vs. Eagles Thanksgiving prediction: ..." and "One bold prediction for each NFL Thanksgiving game"."""
    from ftworthtv.filters import betting_promo
    assert betting_promo("Cowboys vs. Eagles Thanksgiving prediction: Dallas looks for first win streak of 2026 vs. ex-QB")
    assert betting_promo("One bold prediction for each NFL Thanksgiving game, including Cowboys' Dak Prescott to feast on Eagles")
    assert not betting_promo("Cowboys beat Eagles 27-20 on Thanksgiving")


def test_a_weekly_listings_page_is_a_column():
    """Nov 25: Fort Worth Weekly's "Film Shorts // November 25 – December 1, 2026" drew the Stockyards' cattle pens."""
    from ftworthtv.filters import roundup_column
    assert roundup_column("Film Shorts // November 25 – December 1, 2026")
    assert roundup_column("Night & Day // Nov 26 – Dec 2, 2026")
    assert not roundup_column("Fort Worth film festival returns in March")


def test_another_team_with_our_teams_nickname_is_not_ours():
    """Nov 25: CBS Sports' "Oklahoma State rewards Eric Morris with contract extension after Cowboys' dramatic turnaround"
    counted as local news and drew a Dallas Cowboys photo."""
    from ftworthtv.filters import other_teams_nickname
    from ftworthtv.images.subject import plan_subject, provider_queries
    t = "Oklahoma State rewards Eric Morris with contract extension after Cowboys' dramatic turnaround"
    assert other_teams_nickname(f"{t}. Morris has led the Cowboys to a 7-4 record in Stillwater.") == "oklahoma state"
    assert other_teams_nickname("Rangers beat Islanders at Madison Square Garden") == "madison square garden"
    assert other_teams_nickname("Cowboys beat Eagles 27-20 on Thanksgiving at AT&T Stadium") == ""
    assert other_teams_nickname("Dallas Cowboys face former Oklahoma State star in Week 13") == ""
    pairs = provider_queries(plan_subject(t, "", "sports"), t, "sports")
    assert not any("dallas cowboys" in lab for _, lab in pairs)


def test_a_recipe_feature_and_a_menu_reveal_are_not_text_card_news(settings, now):
    """Nov 25: Fort Worth Weekly's "Ate Days of Thanksgiving Leftovers" (a salsa brand's recipes) and NBC 5's "Annual Dallas
    Cowboys Thanksgiving Day game menu revealed" (a concessionaire's menu, drafted as a sports text card)."""
    from ftworthtv.filters import _RECIPE_RE, infer_category
    from ftworthtv.models import Story
    assert _RECIPE_RE.search("Ate Days of Thanksgiving Leftovers")
    menu = Story(id="m", source="NBC 5 DFW", source_kind="rss", title="Annual Dallas Cowboys Thanksgiving Day game menu revealed",
                 summary="Fans will once again be able to enjoy all their favorite Thanksgiving holiday menu classics.", url="u",
                 category_hint="sports")
    assert infer_category(menu) == "food"


def test_a_beat_is_searched_on_commons_only(monkeypatch, settings):
    """Nov 25: Openverse's Flickr result for "Sundance Square Fort Worth" was Bass Hall on a rainy day, for a tree lighting."""
    import inspect
    from ftworthtv import images
    src = inspect.getsource(images.plan_image)
    assert 'queries, labels = [f"commons:{copy.image_query}"]' in src


def test_a_bar_guide_a_training_grant_and_a_june_street_in_november():
    """Nov 25: CultureMap's "Get holly jolly at these 2026 holiday pop-up bars around Fort Worth" (a guide's list, with a June
    2016 Main Street photo) and KVUE's "Texas State's ALERRT Center receives $10M to expand active shooter response training"
    (filed as breaking news, drafted as a text card)."""
    from ftworthtv.filters import infer_category, roundup_column
    from ftworthtv.images.library import in_season
    from ftworthtv.models import Story
    assert roundup_column("Get holly jolly at these 2026 holiday pop-up bars around Fort Worth")
    assert not roundup_column("Fort Worth bar owner charged after fight")
    grant = Story(id="a", source="KVUE Austin", source_kind="rss", title="Texas State's ALERRT Center receives $10M to expand active "
                  "shooter response training", summary="The money will fund the Preparing for Active Shooter Situations program.", url="u")
    assert infer_category(grant) != "breaking"
    real = Story(id="b", source="WFAA", source_kind="rss", title="Active shooter reported at Fort Worth mall, police say",
                 summary="Police responded to reports of an active shooter.", url="u")
    assert infer_category(real) in ("breaking", "crime")
    assert not in_season({"title": "File:Fort Worth June 2016 09 (Main Street).jpg"}, 11)
    assert in_season({"title": "File:Fort Worth skyline.jpg"}, 11)


def test_a_postponed_parade_is_not_canceled_and_is_searched_as_the_parade():
    """Nov 25: Billboard's "Hold Your Turkeys! Macy's 100th Thanksgiving Day Parade Has Been Postponed" came with the dek "...
    has officially been canceled", which the caption kept, and searched "Macy" (the Herald Square store)."""
    from ftworthtv.checks import status_clash
    from ftworthtv.images.subject import plan_subject
    t = "Hold Your Turkeys! Macy’s 100th Thanksgiving Day Parade Has Been Postponed: Here’s the New Date"
    assert status_clash(t, "The Macy's 100th Thanksgiving Day Parade 2026 has officially been canceled.")
    assert not status_clash("Parade canceled due to storms", "The parade was canceled.")
    names = plan_subject(t, "Macy’s 100th Thanksgiving Day parade will be postponed to Saturday.", "events").search_names
    assert "Macy" not in names and any(n.startswith("Macy") and "Thanksgiving" in n for n in names)


def test_a_weeklys_review_and_listing_sections_are_skipped():
    """Nov 25: Fort Worth Weekly's film review ("Hexed: 'Cause It's Witchcraft", Film Reviews) was drafted with the Stockyards'
    Cantina Cadillac, the culture beat's default search."""
    import inspect
    from datetime import datetime, timezone
    from ftworthtv import images
    from ftworthtv.sources.rss import parse_feed
    feed = ("<rss><channel><title>FW Weekly</title>"
            "<item><title>Hexed: 'Cause It's Witchcraft</title><link>https://x/hexed</link><category><![CDATA[Film Reviews]]></category>"
            "<description>A review of the Disney film.</description></item>"
            "<item><title>City council approves budget</title><link>https://x/budget</link><category><![CDATA[News]]></category>"
            "<description>The Fort Worth City Council approved the budget Tuesday.</description></item></channel></rss>")
    got = parse_feed({"name": "Fort Worth Weekly", "skip_sections": ["Film Reviews"]}, feed, datetime.now(timezone.utc))
    assert [s.title for s in got] == ["City council approves budget"]
    assert "DEFAULT_IMAGE_QUERIES.get(copy.category)" in inspect.getsource(images.plan_image)


def test_a_leagues_uniform_roundup_is_a_column():
    """Nov 25: ESPN's "Rams and Cowboys top Week 12 uniforms" ("what each NFL team is wearing in Week 12")."""
    from ftworthtv.filters import roundup_column
    assert roundup_column("Rams and Cowboys top Week 12 uniforms")
    assert not roundup_column("Cowboys unveil throwback uniforms for Thanksgiving game")


def test_the_page_image_passes_the_same_stock_graphic_check_as_the_listing(monkeypatch):
    """Nov 25, render 252: the listing rejected city-news-work-session-room_1.jpg as a stock graphic and enrich() put it straight
    back as the page's og:image. The page's image now passes the same check; the City's photo of the room a noticed meeting is
    held in is that meeting's place, and a real photo under /sites/default/files/ is no stock graphic."""
    from datetime import datetime, timezone
    from ftworthtv.models import Story
    from ftworthtv.sources import article
    from ftworthtv.sources.opencities import generic_image, parse_listing

    room = "https://www.fortworthtexas.gov/files/assets/public/v/1/news/images/city-news-work-session-room_1.jpg?w=1200"
    notice = "https://www.fortworthtexas.gov/files/assets/public/v/1/news/images/city-news-request-for-public-comment.jpg?w=1200"
    assert not generic_image(room, "Work session, special called meeting scheduled Dec. 1")
    assert generic_image(room, "City seeks input on 2025-26 federal housing funds")      # the room is not that story's picture
    assert generic_image(notice, "City seeks input on 2025-26 federal housing funds")
    assert not generic_image("https://example.org/sites/default/files/2026-11/parade.jpg", "Parade of Lights")

    html = ('<article><a href="/news/2026/11/ws"><h2 class="list-item-title">Work session, special called meeting scheduled Dec. 1</h2>'
            '<img src="/files/assets/public/v/1/news/images/city-news-work-session-room_1.jpg?dimension=smallthumbnail&w=300">'
            '<p class="published-on small-text">Published on November 25, 2026</p><p>Both meetings will be held at City Hall.</p></a></article>')
    story = parse_listing(html, "https://www.fortworthtexas.gov/news", {"name": "City of Fort Worth"}, datetime.now(timezone.utc))[0]
    assert story.image_url and not story.extra["generic_image"]

    caper = Story(id="c", source="City of Fort Worth", source_kind="rss", title="City seeks input on 2025-26 federal housing funds",
                  summary="The City is inviting residents to comment on the plan before it goes to the council in December.", url="u")
    monkeypatch.setattr(article, "fetch_article", lambda url: {"image": notice, "summary": "", "description": "", "credit": ""})
    article.enrich(caper)
    assert caper.image_url is None


def test_a_ranking_listicle_is_a_column():
    """Nov 25, render 257: CBS Sports' "NFL on Thanksgiving halftime shows: Ranking the 10 most memorable performances"."""
    from ftworthtv.filters import roundup_column
    assert roundup_column("NFL on Thanksgiving halftime shows: Ranking the 10 most memorable performances")
    assert roundup_column("Ranking every Cowboys Thanksgiving uniform")
    assert roundup_column("The 25 greatest Horned Frogs of all time")
    assert not roundup_column("TCU ranked No. 12 in the latest College Football Playoff rankings")
    assert not roundup_column("Fort Worth ranks among the best cities for first-time homebuyers")
    assert not roundup_column("Ranking member Veasey tours Fort Worth flood project")


def _beat_fallbacks(settings, tmp_path, monkeypatch, title, summary, scope):
    from ftworthtv import images
    from ftworthtv.models import PostCopy, PostDraft, Story
    from ftworthtv.state import State
    calls = []

    def fake_find_photo(queries, *args, **kwargs):
        calls.append(kwargs.get("fallback"))
        return None
    monkeypatch.setattr(images, "find_photo", fake_find_photo)
    monkeypatch.setattr("ftworthtv.images.library.pick", lambda *a, **k: None)     # nothing in the library: the search runs
    settings.offline = False
    story = Story(id="h", source="CBS Sports", source_kind="rss", title=title, summary=summary, url="https://x/h",
                  category="sports", extra={"scope": scope})
    copy = PostCopy(category="sports", headline=title, caption=summary, image_query="category:AT&T Stadium")
    images.plan_image(PostDraft(story=story, copy=copy, writer="template"), settings, State(tmp_path / "s.json"), tmp_path / "w")
    return calls


def test_the_city_skyline_stands_in_only_for_a_story_about_the_city(settings, tmp_path, monkeypatch):
    """Nov 25, render 257: the halftime-shows list found no AT&T Stadium file and fell back to a 2007 downtown Fort Worth
    skyline, for a national story that never names Fort Worth."""
    national = _beat_fallbacks(settings, tmp_path, monkeypatch, "NFL on Thanksgiving halftime shows through the years",
                               "Thanksgiving has featured big performances from top artists since 1997. Miranda Lambert performs in Texas.",
                               "national")
    assert national and not any(national)
    local = _beat_fallbacks(settings, tmp_path, monkeypatch, "Fort Worth budget hearing set for Tuesday",
                            "The Fort Worth City Council will hear residents on the budget Tuesday.", "local")
    assert local and all(local)


def test_a_wanted_name_in_capitals_is_printed_in_proper_case_and_keeps_its_id():
    """Nov 26, render 259: Arlington's "Ezequiel MONTEMAYOR" was drafted as "Arlington police searching for Ezequiel
    MONTEMAYOR, wanted for theft" (and Nov 23-25 bulletins went out the same way). The card and caption print the name in
    proper case; the story id stays on the agency's spelling so a bulletin already posted is never posted again."""
    from datetime import datetime, timezone
    from ftworthtv.sources.wanted import person_story, proper_name
    from ftworthtv.textutil import stable_id
    assert proper_name("Ezequiel MONTEMAYOR") == "Ezequiel Montemayor"
    assert proper_name("Lou Ann MIDDLETON") == "Lou Ann Middleton"
    assert proper_name("Sean MCDONALD") == "Sean McDonald"
    assert proper_name("Shaquille O'NEAL") == "Shaquille O'Neal"
    assert proper_name("Ana SMITH-JONES") == "Ana Smith-Jones"
    assert proper_name("Robert GRIFFIN III") == "Robert Griffin III"
    assert proper_name("DeShawn McKinney") == "DeShawn McKinney"           # mixed case stays as written
    agency = {"name": "Arlington Police Department", "city": "Arlington"}
    p = {"name": "Ezequiel MONTEMAYOR", "charge": "Theft", "reward": "$2,000", "image": "https://x/m.jpg", "age": None}
    story = person_story(p, agency, "https://x", datetime.now(timezone.utc), "Fort Worth")
    assert story.title == "WANTED: Ezequiel Montemayor" and story.extra["name"] == "Ezequiel Montemayor"
    assert story.id == stable_id("wanted", "Arlington Police Department", "Ezequiel MONTEMAYOR", "Theft")


def test_a_fire_headline_is_breaking_news_whatever_day_it_fell_on():
    """Nov 26, render 260: WFAA's "Home workshop sparks early morning fire on Thanksgiving in Fort Worth" was filed as
    community, its "Thanksgiving" outscoring the fire."""
    from ftworthtv.filters import fire_incident, infer_category
    from ftworthtv.models import Story
    story = Story(id="f", source="WFAA", source_kind="video", title="Home workshop sparks early morning fire on Thanksgiving in Fort Worth",
                  summary="A home business sparked an early morning fire in Fort Worth on Thanksgiving. The American Red Cross is "
                          "assisting the several people that were displaced.", url="https://www.youtube.com/watch?v=x")
    assert infer_category(story) == "breaking"
    assert fire_incident("Fire damages Weatherford Aerospace plant building")
    assert fire_incident("Crews battle two-alarm apartment fire in east Fort Worth")
    assert not fire_incident("Cowboys fire offensive coordinator after loss")
    assert not fire_incident("TCU stays on fire at home with win over Baylor")
    assert not fire_incident("Fort Worth fire chief to retire after 30 years")
    assert not fire_incident("Fire department recruits battle live fire in academy drill")


def test_to_hail_someone_is_not_a_hailstorm():
    """Nov 26, render 261: the Fort Worth Report's state-bird story ("Others hail the mockingbird") drew a supercell."""
    from ftworthtv.filters import infer_category
    from ftworthtv.images.library import topics_for
    from ftworthtv.models import Story
    title = "Two state legislators want to change the state bird. Tarrant County birders weigh in"
    text = (f"{title} Some Texans support elevating the golden-cheeked warbler. Others hail the mockingbird, nearly 100 years into "
            "holding the honorary title.")
    assert "storm" not in topics_for(text, "community", "local", title=title)
    assert "storm" not in topics_for("Fort Worth native hailed as a hero after rescue", "community", "local")
    assert "storm" in topics_for("Large hail pounds Fort Worth as storms roll through", "weather", "local")
    story = Story(id="b", source="Fort Worth Report", source_kind="rss", title=title, summary=text, url="u")
    assert infer_category(story) != "weather"


def test_the_nws_forecast_stands_down_after_a_stations_forecast_that_morning(settings, now):
    """Nov 26, render 261: FOX 4's "festive chill" forecast (sunny, high of 53) went out at 6:43 and the NWS "Fort Worth
    forecast: sunny, high near 53" was drafted for 7:58."""
    from datetime import timedelta
    from ftworthtv.models import Story
    from ftworthtv.pipeline import run
    from ftworthtv.state import State
    state = State(settings.state_path)
    state.data.setdefault("posted", {})["fox"] = {"category": "weather", "kind": "rss", "source": "FOX 4 Dallas-Fort Worth",
                                                   "title": "Breezy, near-freezing festive chill grips North Texas",
                                                   "at": (now - timedelta(hours=3)).isoformat()}
    state.save()
    forecast = Story(id="forecast-x", source="National Weather Service Fort Worth", source_kind="nws_forecast",
                     title="Fort Worth forecast for Thursday, November 19", summary="Sunny, with a high near 53.",
                     url="https://forecast.weather.gov/x", published=now - timedelta(hours=1), category_hint="weather",
                     official=True, always_relevant=True)
    report = run(settings, now=now, stories=[forecast], publisher_name="dryrun")
    assert any(s.id == "forecast-x" and r == "a station's forecast already went out this morning" for s, r in report.skipped)


def test_a_forecast_takes_a_picture_in_season_or_a_text_card(settings, tmp_path, monkeypatch):
    """Nov 25: the NWS "Fort Worth forecast: sunny, high near 54" went out with a summer skyline (green lawns, full trees).
    The library's skylines carry their season, and a weather story never searches the web for a stand-in."""
    from ftworthtv import images
    from ftworthtv.models import PostCopy, PostDraft, Story
    from ftworthtv.state import State
    calls = []
    monkeypatch.setattr(images, "find_photo", lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr("ftworthtv.images.library.pick", lambda *a, **k: None)      # nothing in season for this sky
    settings.offline = False
    story = Story(id="fc", source="National Weather Service Fort Worth", source_kind="nws_forecast",
                  title="Fort Worth forecast for Thursday, November 26", summary="Mostly cloudy, with a high near 48.",
                  url="https://forecast.weather.gov/x", category="weather", official=True, extra={"short": "Mostly Cloudy"})
    copy = PostCopy(category="weather", headline="Fort Worth forecast: mostly cloudy, high near 48", caption="Mostly cloudy.",
                    image_query="Fort Worth skyline")
    images.plan_image(PostDraft(story=story, copy=copy, writer="template"), settings, State(tmp_path / "s.json"), tmp_path / "w")
    assert calls == []


def test_another_dfw_citys_cold_case_and_a_traditions_history_are_not_this_pages_news():
    """Nov 26, render 263: FOX 4's "Trackdown: Help find Dallas rapper BFG Baandz's killer" (a shooting "earlier this year")
    and CBS News Texas's "Why do the Detroit Lions and Dallas Cowboys play every year on Thanksgiving? The history"."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ftworthtv.filters import another_citys_old_crime, evergreen_explainer
    thu = datetime(2026, 11, 26, 8, 15, tzinfo=ZoneInfo("America/Chicago"))
    assert another_citys_old_crime("Trackdown: Help find Dallas rapper BFG Baandz’s killer", thu,
                                   "Dallas police are searching for two suspects in the fatal shooting of a rap artist earlier this year.")
    assert another_citys_old_crime("Dallas police release video of suspects in shooting", thu,
                                   "The shooting happened in June outside a club.") == "in June"
    assert another_citys_old_crime("Dallas police investigating overnight shooting", thu, "Police said the shooting happened just after midnight.") == ""
    assert another_citys_old_crime("Trackdown: Help find Fort Worth man's killer", thu, "The shooting happened earlier this year.") == ""
    assert evergreen_explainer("Why do the Detroit Lions and Dallas Cowboys play every year on Thanksgiving? The history")
    assert evergreen_explainer("The history of the Fort Worth Stock Show parade")
    assert not evergreen_explainer("Cowboys beat Eagles on Thanksgiving behind Prescott's three touchdowns")
    assert not evergreen_explainer("Why gas prices are falling ahead of Thanksgiving travel")


def test_a_freezing_forecast_on_thanksgiving_is_weather():
    """Nov 26, render 263: CBS News Texas's "North Texas faces freezing Thanksgiving morning before weekend warmup" was filed as
    community and drew a smoked turkey."""
    from ftworthtv.filters import infer_category
    from ftworthtv.models import Story
    story = Story(id="w", source="CBS News Texas", source_kind="rss", url="u",
                  title="North Texas faces freezing Thanksgiving morning before weekend warmup",
                  summary="Sunny skies, warmer temperatures and gusty winds are ahead. Expect a seasonably cool but sunny Thanksgiving.")
    assert infer_category(story) == "weather"


def test_a_weekly_events_column_and_another_dfw_citys_officials_are_not_this_pages_news():
    """Nov 26, render 264: the Arlington Report's "Out and About in Arlington: ..." column (with "Alice out and about in
    Nairobi" for its picture) and FOX 4's "Top Dallas Police spokesperson reinstated after public integrity investigation"."""
    from ftworthtv.filters import another_dfw_citys_government, roundup_column
    assert roundup_column("Out and About in Arlington: Christmas spirit gobbles up Thanksgiving festivities")
    assert another_dfw_citys_government("Top Dallas Police spokesperson reinstated after public integrity investigation")
    assert another_dfw_citys_government("Dallas police chief's publishing company, book signing events raise ethics questions")
    assert another_dfw_citys_government("Plano ISD board votes to close two schools")
    assert not another_dfw_citys_government("Dallas police: man killed in overnight shooting")       # a crime is still a crime story
    assert not another_dfw_citys_government("Fort Worth police chief named")


def test_one_verdict_told_twice_a_verdicts_picture_and_a_holiday_that_has_come():
    """Nov 26, render 265: FOX 4's "Fort Worth country singer found not guilty after murder trial" (the Tarrant County
    Courthouse for its picture) a day after CBS's "Fort Worth recording artist acquitted of murder ...", and CBS's "Dallas food
    pantry sees increased need ahead of Thanksgiving" (a supermarket aisle) on Thanksgiving morning."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ftworthtv.filters import same_verdict, stale_dated_title
    from ftworthtv.images.library import topics_for
    from ftworthtv.images.subject import happened
    posted = "Fort Worth recording artist acquitted of murder in 2025 shooting death of man, court records show"
    assert same_verdict("Fort Worth country singer found not guilty after murder trial", "", posted)
    assert not same_verdict("Fort Worth man sentenced to life for 2023 murder", "", "Fort Worth woman sentenced for murder of toddler")
    assert not same_verdict("Arlington man found guilty of robbery", "", posted)
    assert happened("Fort Worth country singer found not guilty after murder trial")
    tz = ZoneInfo("America/Chicago")
    title = "Dallas food pantry sees increased need ahead of Thanksgiving"
    assert stale_dated_title(title, datetime(2026, 11, 26, 9, tzinfo=tz))
    assert not stale_dated_title(title, datetime(2026, 11, 24, 9, tzinfo=tz))
    assert stale_dated_title("Toy drive collects gifts ahead of Christmas", datetime(2026, 12, 26, 9, tzinfo=tz))
    assert stale_dated_title("Fireworks rules ahead of New Year's", datetime(2027, 1, 1, 9, tzinfo=tz))
    assert not stale_dated_title("Fireworks rules ahead of New Year's", datetime(2026, 12, 30, 9, tzinfo=tz))
    assert "grocery" not in topics_for(f"{title} The Stewpot food bank serves 300 a day.", "community", "dfw", title=title)
    assert "grocery" in topics_for("SNAP benefits delay hits grocery budgets", "community", "local")


def test_a_stores_promotion_and_one_shooting_told_twice():
    """Nov 26, render 266: KENS 5's "Here, everything's better: H-E-B offers holiday savings to help fill the family table" and
    FOX 4's "Fort Worth shooting leaves three men hospitalized after fight" after NBC 5's "Investigation underway after 3
    injured in Fort Worth shooting" went out."""
    from ftworthtv.filters import retail_promotion, same_count_incident
    assert retail_promotion("Here, everything’s better: H-E-B offers holiday savings to help fill the family table")
    assert retail_promotion("Walmart rolls out Black Friday deals early")
    assert not retail_promotion("H-E-B to open new store in Fort Worth's Alliance area")
    assert not retail_promotion("City offers savings on water bills for seniors")
    posted = "Investigation underway after 3 injured in Fort Worth shooting"
    assert same_count_incident("Fort Worth shooting leaves three men hospitalized after fight", "", posted)
    assert not same_count_incident("2 killed in Fort Worth crash on I-35W", "", posted)
    assert not same_count_incident("Three hurt in Dallas shooting", "", posted)


def test_the_holiday_table_is_only_the_greetings_picture():
    """Nov 26, render 267: NBC 5's "North Texas volunteers prepare 7,000 Thanksgiving meals for neighbors in need" drew a family
    carving a turkey at home."""
    from ftworthtv.images.library import topics_for
    title = "North Texas volunteers prepare 7,000 Thanksgiving meals for neighbors in need"
    assert "thanksgiving" not in topics_for(f"{title} Operation Turkey is delivering meals.", "community", "dfw", title=title)
    assert "thanksgiving" in topics_for("Happy Thanksgiving Fort Worth", "community", "local", title="Happy Thanksgiving Fort Worth")


def test_the_writers_category_is_the_one_the_days_rules_count(settings, now, monkeypatch):
    """Nov 26, render 267: NBC 5's "Fort Worth prepared to provide emergency overflow shelter as cold settles in" passed the
    weather checks under another category and came out of the writer as weather, hours after the day's forecast went out."""
    from datetime import timedelta
    from ftworthtv import pipeline
    from ftworthtv.models import Story
    from ftworthtv.state import State
    state = State(settings.state_path)
    state.data.setdefault("posted", {})["fox"] = {"category": "weather", "kind": "rss", "source": "FOX 4 Dallas-Fort Worth",
                                                   "title": "Breezy, near-freezing festive chill grips North Texas",
                                                   "at": (now - timedelta(hours=3)).isoformat()}
    state.save()
    real = pipeline.write_copy

    def as_weather(story, *a, **k):
        copy, writer = real(story, *a, **k)
        return copy.model_copy(update={"category": "weather"}), writer
    monkeypatch.setattr(pipeline, "write_copy", as_weather)
    story = Story(id="shelter", source="NBC 5 DFW", source_kind="rss", url="https://www.nbcdfw.com/news/local/x/1/",
                  title="Fort Worth opens emergency overflow shelter for people experiencing homelessness",
                  summary="The city of Fort Worth is reminding residents of resources available to people experiencing homelessness "
                          "and outlining when the emergency overflow shelter will open this week.",
                  published=now - timedelta(hours=1))
    report = pipeline.run(settings, now=now, stories=[story], publisher_name="dryrun")
    assert any(s.id == "shelter" and r == "a weather story already went out in the last six hours" for s, r in report.skipped)


def test_a_verdict_on_a_team_is_a_column_and_another_match_is_not_its_picture():
    """Nov 26, render 268: ESPN's "With World Cup qualification at stake, the USWNT has no excuses" with "Levi's Stadium 2026
    FIFA World Cup Australia v. Paraguay" (the USWNT plays El Salvador in Mansfield)."""
    from ftworthtv.filters import roundup_column
    from ftworthtv.images.providers import other_event_photo
    assert roundup_column("With World Cup qualification at stake, the USWNT has no excuses")
    story = ("The USWNT faces El Salvador in the Concacaf quarterfinal on Friday in Mansfield, Texas, one win from the 2027 "
             "Women's World Cup.")
    assert other_event_photo("Levi's Stadium 2026 FIFA World Cup Australia v. Paraguay", "World Cup", story)
    assert not other_event_photo("USWNT vs El Salvador 2024 friendly", "USWNT", story)
    assert not other_event_photo("TCU vs. Baylor 2024", "TCU", "TCU hosts Baylor on Saturday at Amon G. Carter Stadium.")


def test_daily_fantasy_advice_is_a_betting_column():
    """Nov 26, render 269: CBS Sports' "NFL DFS, Thanksgiving Day: Top daily Fantasy picks, lineups for Bears-Lions, Cowboys-Eagles,
    Chiefs-Bills" as a sports text card."""
    from ftworthtv.filters import _BETTING_RE
    assert _BETTING_RE.search("NFL DFS, Thanksgiving Day: Top daily Fantasy picks, lineups for Bears-Lions, Cowboys-Eagles, Chiefs-Bills")
    assert _BETTING_RE.search("Week 13 fantasy rankings: CeeDee Lamb a top-five receiver")
    assert _BETTING_RE.search("Start 'em, sit 'em: Week 13")
    assert not _BETTING_RE.search("Cowboys beat Eagles 31-24 on Thanksgiving")
    assert not _BETTING_RE.search("Fantasy football star CeeDee Lamb leads Cowboys past Eagles")


def test_another_citys_skyline_is_not_a_features_picture():
    """Nov 26, render 270: NBC 5's "Private social clubs: Dallas' new 'third place for the wealthy'" drew the Dallas skyline."""
    from ftworthtv.images.library import topics_for
    title = "Private social clubs: Dallas' new ‘third place for the wealthy'"
    assert "dallas-skyline" not in topics_for(f"{title} Members-only spaces in Highland Park Village.", "community", "dfw", title=title)
    assert "dallas-skyline" in topics_for("Dallas City Council approves new budget", "politics", "dfw", title="Dallas City Council approves new budget")


def test_a_writers_own_voice_is_a_column():
    """Nov 26, render 271: the Fort Worth Report's "Weekend Worthy" column captioned "Nothing like the delicious smell of turkey
    roasting in the oven to remind me: Happy Thanksgiving!"."""
    from ftworthtv.checks import first_person_voice
    from ftworthtv.filters import roundup_column
    assert first_person_voice("Nothing like the delicious smell of turkey roasting in the oven to remind me: Happy Thanksgiving!") == "me"
    assert first_person_voice("My favorite holiday market opens Friday.") == "My"
    assert first_person_voice("“Because it’s fun and it tastes good,” Max said. “I love it,” he added.") == ""
    assert first_person_voice("A crash closed I-35W northbound near Meacham Boulevard.") == ""
    assert roundup_column("Weekend Worthy: Cliburn piano concert sets Christmas scene at Stockyards")


def test_an_alert_until_a_time_this_morning_is_over_by_afternoon():
    """Nov 26, render 273: CBS's "A First Alert Weather Day is in effect this morning until 9 a.m." drafted for 1:35 p.m."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ftworthtv.writer import passed_window
    tz = ZoneInfo("America/Chicago")
    caption = "Thanksgiving is off to a cold start. A First Alert Weather Day is in effect this morning until 9 a.m. due to the first freeze."
    assert passed_window(caption, datetime(2026, 11, 26, 13, 12, tzinfo=tz)) == "until 9 a.m."
    assert passed_window(caption, datetime(2026, 11, 26, 7, 30, tzinfo=tz)) == ""
    assert passed_window("The westbound lanes will stay closed until 5 p.m. Friday.", datetime(2026, 11, 26, 18, 0, tzinfo=tz)) == ""
