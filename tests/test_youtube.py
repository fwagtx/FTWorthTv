from datetime import datetime, timezone

from ftworthtv.sources.youtube import parse_feed

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>City of Fort Worth</title>
 <entry>
  <id>yt:video:abc123XYZ00</id><yt:videoId>abc123XYZ00</yt:videoId>
  <title>Fort Worth City Council approves 2027 budget</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=abc123XYZ00"/>
  <published>2026-11-19T13:00:00+00:00</published>
  <media:group>
   <media:title>Fort Worth City Council approves 2027 budget</media:title>
   <media:thumbnail url="https://i2.ytimg.com/vi/abc123XYZ00/hqdefault.jpg" width="480" height="360"/>
   <media:description>The council voted 9-2 on Tuesday. Watch the full discussion.</media:description>
   <media:community><media:statistics views="1234"/></media:community>
  </media:group>
 </entry>
 <entry>
  <id>yt:video:live0000001</id><yt:videoId>live0000001</yt:videoId>
  <title>LIVE: City Council meeting</title>
  <published>2026-11-19T12:00:00+00:00</published>
 </entry>
</feed>"""


def test_youtube_feed_becomes_a_video_story():
    now = datetime(2026, 11, 19, 14, 0, tzinfo=timezone.utc)
    stories = parse_feed({"name": "City of Fort Worth", "always_relevant": True, "category_hint": "community"}, ATOM, now)
    assert len(stories) == 1                      # the live stream is skipped
    s = stories[0]
    assert s.source_kind == "video" and s.url.endswith("abc123XYZ00") and s.extra["views"] == 1234
    assert s.summary.startswith("The council voted 9-2")
    assert s.image_policy == "none" and s.always_relevant


def test_video_caption_and_link_mode(settings, now):
    from ftworthtv.writer import write_copy
    s = parse_feed({"name": "City of Fort Worth", "always_relevant": True}, ATOM, now)[0]
    copy, writer = write_copy(s, settings, now)
    assert copy.caption.startswith("WATCH: Fort Worth City Council approves 2027 budget")
    assert "Video: City of Fort Worth on YouTube" in copy.caption
    assert "youtube.com/watch?v=abc123XYZ00" in copy.first_comment


def test_video_gate_is_cautious():
    from ftworthtv.sources.youtube import wanted_title
    g = {"skip_in_title": ["meeting", "podcast"]}
    assert wanted_title({"name": "City of Fort Worth"}, "Fort Worth opens new fire station on the west side", g)
    assert not wanted_title({"name": "City of Fort Worth"}, "City Council meeting - November 18, 2026", g)
    station = {"name": "FOX 4", "title_must_name_place": True}
    assert wanted_title(station, "Fort Worth police investigate overnight shooting", g)
    assert not wanted_title(station, "Heavy rain floods streets in Houston suburbs", g)
    assert not wanted_title(station, "Vehicle crashes into Dallas home overnight, injuring four.", g)     # Dallas alone is not our beat
    assert not wanted_title(station, "Dallas ISD to vote on closing 6 schools amid budget deficit", g)
    assert not wanted_title(station, "Cold Front Approaches Texas Ahead of Thanksgiving", g)              # nor Texas alone
    assert not wanted_title(station, "Rude awakening: car crashes into South Dallas home overnight, injuring one | NBC DFW", g)   # the station tag is not a place
    assert not wanted_title(station, "Family of the victim in a Denton home invasion speaks out after their grandpa was shot", g)
    assert wanted_title(station, "DFW gas prices drop ahead of Thanksgiving travel | FOX 4", g)             # DFW in the title itself counts
    assert wanted_title(station, "Warming trend continues through weekend in North Texas", g)             # the region as a whole is
    assert wanted_title(station, "Arlington police release video from Cowboys game arrest", g)
    assert not wanted_title({"name": "City of Arlington"}, "Arlington Eats at Mariano's Hacienda", {"skip_in_title": ["eats at"]})
    team = {"name": "Dallas Cowboys", "require_any_in_title": ["highlights", "recap", "wins", "press conference"]}
    assert wanted_title(team, "Cowboys vs. 49ers highlights | Week 11", g)
    assert not wanted_title(team, "Mic'd up: a day with the rookies", g)
    assert not wanted_title(team, "Cheerleaders behind the scenes", g)


def test_old_videos_are_not_news():
    now = datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc)      # a day later
    assert parse_feed({"name": "City of Fort Worth", "always_relevant": True}, ATOM, now, {"max_age_hours": 12}) == []


def test_wire_channels_only_share_watchlisted_moments():
    from ftworthtv.sources.youtube import wanted_title
    g = {"skip_in_title": ["podcast"], "video_watchlist": ["anthropic", "ipo", "texas"]}
    wire = {"name": "Bloomberg Television", "require_watchlist_in_title": True, "require_any_in_title": ["ipo", "opening bell", "rings"]}
    assert wanted_title(wire, "Anthropic Executive Team Rings Nasdaq Opening Bell", g)
    assert not wanted_title(wire, "Fed holds rates steady as markets wobble", g)            # no watchlist subject
    assert not wanted_title(wire, "Anthropic CEO on the future of AI | full interview", g)  # not an event


def test_a_dallas_institution_is_not_ours_because_the_title_says_north_texas():
    from ftworthtv.sources.youtube import names_our_place
    assert not names_our_place("The Dallas Foundation awards nearly $2.7 million to North Texas nonprofits")
    assert names_our_place("Tarrant Area Food Bank hands out Thanksgiving meals to North Texas families")
    assert names_our_place("North Texas storms knock out power overnight | NBC DFW")
    assert not names_our_place("Dallas City Council approves budget | FOX 4")


def test_a_station_tag_without_spaces_does_not_pass_the_place_gate():
    from ftworthtv.sources.youtube import names_our_place, place_text
    assert place_text("Stuffing takes the top spot as America's favorite Thanksgiving side dish: new report | NBCDFW") == \
        "Stuffing takes the top spot as America's favorite Thanksgiving side dish: new report"
    assert not names_our_place("Stuffing takes the top spot as America's favorite Thanksgiving side dish: new report | NBCDFW")


def test_a_channels_boilerplate_is_cut_from_the_description_and_a_conviction_is_crime():
    from datetime import timedelta
    from ftworthtv.filters import infer_category
    from ftworthtv.sources.youtube import description_lead, parse_feed
    raw = ("An Arlington pastor could face up to 20 years in prison after he was convicted for defrauding followers out of over $6 million dollars. "
           "FOX 4's David Sentendrey has more. Dallas news, weather, sports and traffic from KDFW FOX 4, serving Dallas-Fort Worth, North Texas and "
           "the state of Texas. Subscribe to FOX 4: https://www.youtube.com/fox4news?sub_confirmation=1 Download the FOX LOCAL app: https://www.fox4news.com/apps")
    lead = description_lead(raw)
    assert lead.endswith("David Sentendrey has more.") and "weather" not in lead
    published = (now_utc := __import__("datetime").datetime(2026, 11, 21, 3, 17, 38, tzinfo=__import__("datetime").timezone.utc)).isoformat()
    atom = f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/">
<entry><yt:videoId>EkOdxpeKe_8</yt:videoId><title>Arlington pastor convicted for "classic Ponzi scheme"</title><published>{published}</published>
<media:group><media:description>{raw}</media:description><media:thumbnail url="https://i.ytimg.com/vi/EkOdxpeKe_8/hqdefault.jpg"/></media:group></entry></feed>'''
    stories = parse_feed({"name": "FOX 4 Dallas-Fort Worth", "always_relevant": True}, atom, now_utc + timedelta(hours=1), {"max_age_hours": 12})
    assert len(stories) == 1 and "weather" not in stories[0].summary
    assert infer_category(stories[0]) == "crime"


def test_a_north_texas_person_is_ours_only_when_the_description_names_our_side():
    """Nov 25: WFAA's "North Texas woman will return to the Macy's Thanksgiving Day Parade years after participating" named no
    town; a person from North Texas is from anywhere in the region."""
    from ftworthtv.sources.youtube import wanted_title
    station = {"name": "WFAA", "title_must_name_place": True}
    title = "North Texas woman will return to the Macy's Thanksgiving Day Parade years after participating"
    assert not wanted_title(station, title, {}, "A North Texas woman will return to the Macy's Thanksgiving Day Parade years after "
                                                "participating as a high schooler.")
    assert wanted_title(station, title, {}, "The Keller woman marched with her high school band in 1998.")
    assert not wanted_title(station, "North Texas high school student wins national science prize", {}, "")
    assert wanted_title(station, "North Texas braces for first hard freeze of the season", {}, "")     # the region itself still counts
    assert wanted_title(station, "DFW gas prices drop ahead of Thanksgiving travel | FOX 4", {}, "")
