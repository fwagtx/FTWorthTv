from ftworthtv.examples import example_stories
from ftworthtv.filters import filter_stories
from ftworthtv.models import PostCopy
from ftworthtv.state import State
from ftworthtv.writer import build_system_prompt, finalize, template_copy, write_copy


def test_template_writer_covers_every_kind(settings, now, tmp_path):
    kept, _ = filter_stories(example_stories(settings, now), settings, State(tmp_path / "s.json"), now)
    kinds_seen = set()
    for story in kept:
        copy, writer = write_copy(story, settings, now)   # no ANTHROPIC_API_KEY in tests -> template
        assert writer == "template"
        assert not copy.skip
        assert copy.caption and len(copy.caption) < 900
        assert "http" not in copy.caption and "#" not in copy.caption
        assert "{photo_credit}" in copy.first_comment and story.url in copy.first_comment
        assert copy.hashtags == []                                   # dallas style: no hashtags on Facebook
        assert len(copy.headline) <= 120
        assert "Follow us" not in copy.caption                        # no follow line, like the Dallas captions
        body = copy.caption.split("\n\nFollow us")[0]
        assert "📍" not in body and "•" not in body and len(body) <= 420
        kinds_seen.add(story.source_kind)
    assert {"rss", "nws_alert", "event", "event_roundup"} <= kinds_seen


def test_alert_template_mentions_end_time(settings, now, tmp_path):
    kept, _ = filter_stories(example_stories(settings, now), settings, State(tmp_path / "s.json"), now)
    alert = next(s for s in kept if s.source_kind == "nws_alert")
    copy = template_copy(alert, settings, now)
    assert copy.caption.startswith("The National Weather Service has issued a Severe Thunderstorm Warning for Tarrant, TX until")
    assert copy.caption.rstrip().endswith("🚨")
    settings.brand["caption"]["style"] = "detailed"
    copy = template_copy(alert, settings, now)
    assert copy.caption.startswith("⚠️ Severe Thunderstorm Warning")


def test_finalize_strips_urls_and_hashtags_and_fills_defaults(settings, now, tmp_path):
    settings.brand["caption"]["hashtags"] = True
    kept, _ = filter_stories(example_stories(settings, now), settings, State(tmp_path / "s.json"), now)
    story = kept[0]
    raw = PostCopy(headline="A very long headline that keeps going and going well past sixty characters.", caption="Hook #FortWorth https://x.y/z\n\n\n\nmore",
                   first_comment="", hashtags=["#one", "two", "#one"], category="food")
    out = finalize(raw, story, settings)
    assert "http" not in out.caption and "#" not in out.caption and "\n\n\n" not in out.caption
    assert out.hashtags[:2] == ["#one", "#two"] and len(out.hashtags) <= 8
    assert story.url in out.first_comment and "{photo_credit}" in out.first_comment
    assert len(out.headline) <= 121


def test_system_prompt_carries_brand(settings):
    prompt = build_system_prompt(settings)
    assert settings.brand["page_name"] in prompt and settings.brand["handle"] in prompt and "{photo_credit}" in prompt



def test_dallas_caption_shapes(settings, now, tmp_path):
    from ftworthtv.models import Story
    from ftworthtv.writer import dallas_caption, finalize, template_copy
    s = Story(id="x", source="Fort Worth Report", source_kind="rss", title="New barbecue joint opens on Magnolia Avenue in Near Southside",
              summary="A family-run smokehouse opened its doors on Magnolia Avenue this week. Lines wrapped around the block.", url="https://x/y", category="food")
    assert dallas_caption(s, settings, now, "food") == ["New barbecue joint opens on Magnolia Avenue in Near Southside. A family-run smokehouse opened its doors on Magnolia Avenue this week.",
                                                        "Lines wrapped around the block."]
    t = Story(id="t", source="FOX 4", source_kind="rss", title="Crash shuts down northbound I-35W near downtown Fort Worth during morning rush",
              summary="All northbound lanes were closed after a multi-vehicle crash.", url="https://x/z", category="traffic")
    assert dallas_caption(t, settings, now, "traffic") == ["Crash shuts down northbound I-35W near downtown Fort Worth during morning rush. All northbound lanes were closed after a multi-vehicle crash."]
    w = Story(id="w", source="Fort Worth Police Department", source_kind="wanted", title="WANTED: Sample Person", summary="", url="https://x/w", category="crime",
              extra={"agency": "Fort Worth Police Department", "name": "Sample Person", "charge": "Aggravated Robbery", "reward": "$2,000", "tip_phone": "817-469-TIPS (8477)"})
    lines = dallas_caption(w, settings, now, "crime")
    assert lines[0].startswith("Fort Worth police are looking for Sample Person, wanted for aggravated robbery.")
    out = finalize(template_copy(t, settings, now), t, settings)
    assert "Follow us" not in out.caption and out.hashtags == [] and out.caption.endswith("🚨")


def test_submitted_clip_credit_matches_dallas_shape(settings, now):
    from ftworthtv.models import Story
    from ftworthtv.writer import dallas_caption
    s = Story(id="c", source="Submission", source_kind="rss", title="Large fire on I-35W and Western Center this afternoon", summary="",
              url="", category="breaking", extra={"credit": "IG/ username"})
    assert dallas_caption(s, settings, now, "breaking") == ["Large fire on I-35W and Western Center this afternoon"]
    from ftworthtv.writer import finalize, template_copy
    out = finalize(template_copy(s, settings, now), s, settings)
    assert "via" not in out.caption and "IG/ username" in out.first_comment        # credit lives in the first comment now


def test_claude_code_writer_parses_headless_output(settings, now, tmp_path, monkeypatch):
    import json, os, stat
    from ftworthtv.models import Story
    from ftworthtv.writer import write_copy
    fake = tmp_path / "claude"
    inner = {"skip": False, "skip_reason": "", "category": "food", "headline": "New BBQ on Magnolia", "caption": "New barbecue spot just opened on Magnolia Avenue",
             "first_comment": "Source: Fort Worth Report https://x/y\n{photo_credit}", "hashtags": [], "image_query": "Texas barbecue plate", "location": "Fort Worth, TX"}
    fake.write_text("#!/bin/sh\nprintf '%s' '" + json.dumps({"type": "result", "subtype": "success", "result": json.dumps(inner)}).replace("'", "'\"'\"'") + "'\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    settings.claude_code_oauth_token = "sk-ant-oat01-test"
    settings.writer = "auto"
    story = Story(id="s", source="Fort Worth Report", source_kind="rss", title="New barbecue joint opens on Magnolia Avenue", summary="", url="https://x/y", category="food")
    copy, writer = write_copy(story, settings, now)
    assert writer == "claude-code" and copy.caption.startswith("New barbecue spot just opened on Magnolia Avenue")
    assert "Follow us" not in copy.caption
    settings.writer = "template"
    _, writer = write_copy(story, settings, now)
    assert writer == "template"


def test_all_caps_titles_are_tidied(settings, now):
    from ftworthtv.models import Story
    from ftworthtv.writer import dallas_caption
    s = Story(id="g", source="Fort Worth Business Press", source_kind="rss", title="GOODWILL NORTH CENTRAL TEXAS ANNOUNCES NEW HASLET STORE AND DONATION CENTER", summary="", url="https://x/g", category="business")
    assert dallas_caption(s, settings, now, "business") == ["Goodwill North Central Texas Announces New Haslet Store And Donation Center"]


def test_topic_image_queries(settings, now):
    from ftworthtv.models import Story
    from ftworthtv.writer import template_copy
    s = Story(id="p", source="CultureMap", source_kind="rss", title="Fort Worth Parade of Lights 2026: street closures, parking & more", summary="", url="https://x/p", category="events")
    assert template_copy(s, settings, now).image_query == "Fort Worth Parade of Lights"
    c = Story(id="c", source="NBC 5", source_kind="rss", title="Cowboys trade football for food service in Thanksgiving tradition", summary="", url="https://x/c", category="sports")
    assert template_copy(c, settings, now).image_query == "category:AT&T Stadium"
