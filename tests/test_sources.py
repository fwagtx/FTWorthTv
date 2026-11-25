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
