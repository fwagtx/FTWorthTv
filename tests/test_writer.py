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
        assert 5 <= len(copy.hashtags) <= 8 and all(t.startswith("#") for t in copy.hashtags)
        assert len(copy.headline) <= 64
        assert "Follow @FortWorthTexasTV" in copy.caption or "Tickets" in copy.caption
        kinds_seen.add(story.source_kind)
    assert {"rss", "nws_alert", "event", "event_roundup"} <= kinds_seen


def test_alert_template_mentions_end_time(settings, now, tmp_path):
    kept, _ = filter_stories(example_stories(settings, now), settings, State(tmp_path / "s.json"), now)
    alert = next(s for s in kept if s.source_kind == "nws_alert")
    copy = template_copy(alert, settings, now)
    assert copy.caption.startswith("⚠️ Severe Thunderstorm Warning")
    assert "until" in copy.caption and "PM" in copy.caption or "AM" in copy.caption


def test_finalize_strips_urls_and_hashtags_and_fills_defaults(settings, now, tmp_path):
    kept, _ = filter_stories(example_stories(settings, now), settings, State(tmp_path / "s.json"), now)
    story = kept[0]
    raw = PostCopy(headline="A very long headline that keeps going and going well past sixty characters.", caption="Hook #FortWorth https://x.y/z\n\n\n\nmore",
                   first_comment="", hashtags=["#one", "two", "#one"], category="food")
    out = finalize(raw, story, settings)
    assert "http" not in out.caption and "#" not in out.caption and "\n\n\n" not in out.caption
    assert out.hashtags[:2] == ["#one", "#two"] and len(out.hashtags) <= 8
    assert story.url in out.first_comment and "{photo_credit}" in out.first_comment
    assert len(out.headline) <= 65


def test_system_prompt_carries_brand(settings):
    prompt = build_system_prompt(settings)
    assert "Fort Worth Texas TV" in prompt and "@FortWorthTexasTV" in prompt and "{photo_credit}" in prompt
