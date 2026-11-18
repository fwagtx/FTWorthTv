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
