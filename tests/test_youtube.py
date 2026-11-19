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
