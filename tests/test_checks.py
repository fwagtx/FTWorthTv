from datetime import datetime, timezone

from ftworthtv.checks import caption_problems, preflight, source_text, wanted_still_listed
from ftworthtv.models import PostCopy, PostDraft, Story


def _story(**kw):
    base = dict(id="s1", source="Fort Worth Report", source_kind="rss", title="Trinity Metro cuts On-Demand zones",
                summary="Trinity Metro's board approved changes Monday to the On-Demand service. The subsidized rides cost about $28 each, "
                        "Tara Crawford said. Paul David Williams, 70, said he will walk two blocks from the Walmart at 717 W. Berry St.",
                url="https://example.com/story")
    base.update(kw)
    return Story(**base)


def _copy(caption):
    return PostCopy(headline="h", caption=caption, first_comment="Source", category="traffic")


def test_grounded_caption_passes():
    cap = "Trinity Metro's board approved changes Monday to the On-Demand service. The subsidized rides cost about $28 each, Crawford said."
    assert caption_problems(_copy(cap), _story()) == []


def test_invented_number_quote_and_sentence_fail():
    s = _story()
    assert any("number" in p for p in caption_problems(_copy("The rides cost about $45 each."), s))
    assert any("quotation" in p for p in caption_problems(_copy("Williams said, 'I will never ride the bus again in my life.'"), s))
    assert any("sentence" in p for p in caption_problems(_copy("The governor announced a statewide pension overhaul for teachers yesterday."), s))


def test_structured_fields_count_as_source():
    s = _story(source_kind="wanted", summary="", title="WANTED: John Doe",
               extra={"name": "John Doe", "charge": "Aggravated Robbery", "reward": "$2,000", "tip_phone": "817-469-TIPS (8477)"})
    cap = "Fort Worth police are looking for John Doe, wanted for aggravated robbery. Crime Stoppers is offering up to $2,000. Call 817-469-TIPS (8477)."
    assert caption_problems(_copy(cap), s, writer="template") == []
    assert any("number" in p for p in caption_problems(_copy(cap.replace("$2,000", "$5,000")), s, writer="template"))
    assert "aggravated robbery" in source_text(s)


def test_wanted_recheck(monkeypatch):
    from ftworthtv import http

    class R:
        def __init__(self, text):
            self.text = text

    class S:
        def __init__(self, text):
            self.text = text

        def get(self, url, timeout=20, allow_redirects=True):
            return R(self.text)

    s = _story(source_kind="wanted", extra={"name": "John Doe"}, url="https://police.example.gov/most-wanted")
    monkeypatch.setattr(http, "session", lambda: S("<h3>John Doe</h3> Aggravated Robbery"))
    assert wanted_still_listed(s) is None
    monkeypatch.setattr(http, "session", lambda: S("<h3>Someone Else</h3>"))
    assert "no longer listed" in wanted_still_listed(s)


def test_preflight_offline_only_checks_text():
    d = PostDraft(story=_story(), copy=_copy("The subsidized rides cost about $28 each, Crawford said."), writer="template", mode="link", link="https://example.com/story")
    assert preflight(d, network=False) == []
