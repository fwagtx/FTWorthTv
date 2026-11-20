from pathlib import Path

from ftworthtv import http
from ftworthtv.sources import submissions

CSV = """Timestamp,Credit (name or handle),Caption (what happened),Where,Video link,Consent (yes/no),Approved (yes/no)
2026-11-19 14:02,@keller_mom,"Hail the size of quarters hitting our street tonight. Kids thought it was snow!",Keller,https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456/view?usp=sharing,yes,yes
2026-11-19 14:30,Joe R.,Fire on the west side,Fort Worth,https://drive.google.com/file/d/1ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543/view,no,yes
2026-11-19 15:00,Ana,Crash on I-30,Arlington,https://drive.google.com/open?id=1QqWwEeRrTtYyUuIiOoPpAaSsDdFfGgHh,yes,
2026-11-19 15:10,Sam,"Panther Island fireworks from the river. Beautiful night.",Fort Worth,https://example.com/clips/fireworks.mp4,Yes,YES
,,,,,,
"""


def test_rows_columns_and_drive_links():
    rows = submissions.parse_rows(CSV)
    assert [r["credit"] for r in rows] == ["@keller_mom", "Joe R.", "Ana", "Sam"]
    assert submissions.drive_file_id(rows[0]["video"]) == "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456"
    assert submissions.drive_file_id(rows[2]["video"]) == "1QqWwEeRrTtYyUuIiOoPpAaSsDdFfGgHh"
    assert submissions.drive_file_id(rows[3]["video"]) is None and submissions.download_urls(rows[3]["video"]) == [rows[3]["video"]]
    assert submissions.download_urls(rows[0]["video"])[0].startswith("https://drive.usercontent.google.com/download?id=1AbCdEf")
    assert submissions.truthy("YES") and submissions.truthy(" x ") and not submissions.truthy("") and not submissions.truthy("no")


def test_only_consented_and_approved_clips_are_fetched_once(monkeypatch, settings, now):
    settings.offline = False
    settings.sources["submissions"] = {"enabled": True, "csv_url": "https://docs.google.com/spreadsheets/d/sheet/export?format=csv", "max_mb": 50}
    fetched = []

    class R:
        text = CSV

    def fake_download(url, dest, **kw):
        fetched.append(url)
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\x00" * 30_000)
        return Path(dest)

    monkeypatch.setattr(http, "get", lambda url, **kw: R())
    monkeypatch.setattr(http, "download", fake_download)
    stories = submissions.fetch(settings, now)
    assert [s.extra["credit"] for s in stories] == ["@keller_mom", "Sam"]        # no consent -> no; not approved -> no
    hail = stories[0]
    assert hail.source_kind == "submission" and hail.id == "submission:1AbCdEfGhIjKlMnOpQrStUvWxYz0123456"
    assert hail.title == "Hail the size of quarters hitting our street tonight." and hail.extra["where"] == "Keller"
    assert Path(hail.extra["video_path"]).exists() and hail.always_relevant and hail.image_policy == "none"
    assert len(fetched) == 2
    # a second run finds the clips on disk and does not download again; a posted one is not offered again
    from ftworthtv.state import State
    st = State(settings.state_path)
    st.data.setdefault("posted", {})[hail.id] = {"at": now.isoformat()}
    st.save()
    again = submissions.fetch(settings, now)
    assert [s.extra["credit"] for s in again] == ["Sam"] and len(fetched) == 2


def test_sheet_that_is_not_shared_is_reported_not_parsed(monkeypatch, settings, now):
    settings.offline = False
    settings.sources["submissions"] = {"enabled": True, "csv_url": "https://docs.google.com/spreadsheets/d/x/export?format=csv"}

    class R:
        text = "<!DOCTYPE html><html><head><title>Sign in</title></head></html>"

    monkeypatch.setattr(http, "get", lambda url, **kw: R())
    assert submissions.fetch(settings, now) == []


def test_a_viewer_clip_becomes_a_native_video_post(settings, now):
    from ftworthtv.pipeline import run
    clip = settings.out_dir / "submissions" / "abc.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"\x00" * 30_000)
    row = {"credit": "@keller_mom", "caption": "Hail the size of quarters hitting our street tonight. Kids thought it was snow!",
           "where": "Keller", "video": "https://drive.google.com/file/d/abc/view", "consent": "yes", "approved": "yes", "when": ""}
    story = submissions.row_story(row, now, clip, "Fort Worth")
    report = run(settings, now=now, stories=[story], publisher_name="dryrun")
    assert len(report.drafts) == 1 and report.results[0].ok
    draft = report.drafts[0]
    assert draft.mode == "video" and draft.video_path and draft.video_path.exists() and draft.video_path.name == "clip.mp4"
    assert draft.writer == "template" and "Hail the size of quarters" in draft.copy.caption
    assert "\n\nKeller\n\nVideo: @keller_mom" in draft.copy.caption          # the page style strips emoji from captions
    assert "🎥 @keller_mom" in draft.first_comment_text() and "{photo_credit}" not in draft.first_comment_text()
    import json
    meta = json.loads((draft.video_path.parent / "post.json").read_text())
    assert meta["mode"] == "video" and meta["video"].endswith("clip.mp4")


def test_a_viewer_photo_becomes_a_photo_post_with_their_picture(monkeypatch, settings, now):
    settings.offline = False
    settings.sources["submissions"] = {"enabled": True, "csv_url": "https://docs.google.com/spreadsheets/d/x/export?format=csv"}
    csv = ("Credit,Caption,Where,Video or photo link,Kind,Consent,Approved\n"
           "Maria G.,\"Double rainbow over the Stockyards after the storm.\",Fort Worth,https://drive.google.com/file/d/1PhOtOiD000000000000000000000/view,photo,yes,yes\n")

    class R:
        text = csv
    monkeypatch.setattr(http, "get", lambda url, **kw: R())
    monkeypatch.setattr(http, "download", lambda *a, **k: (_ for _ in ()).throw(AssertionError("photos are not downloaded by the source")))
    stories = submissions.fetch(settings, now)
    assert len(stories) == 1
    s = stories[0]
    assert s.image_policy == "source_image" and s.image_url.startswith("https://drive.usercontent.google.com/download?id=1PhOtOiD")
    assert s.image_credit == "Photo: Maria G." and s.extra.get("photo") and "video_path" not in s.extra
    from ftworthtv.writer import write_copy
    copy, writer = write_copy(s, settings, now, force_template=True)
    assert "Photo: Maria G." in copy.caption and "Video" not in copy.caption


def test_photo_judge_drops_an_off_subject_provider_photo(monkeypatch, settings):
    from ftworthtv.images import judge
    monkeypatch.setattr(judge, "available", lambda s: True)
    calls = []

    class P:
        stdout = '{"result": "No"}'
    def fake_run(cmd, **kw):
        calls.append(cmd); return P()
    monkeypatch.setattr(judge.subprocess, "run", fake_run)
    assert judge.photo_fits(settings, headline="Anthropic's IPO is the largest ever", summary="", title="Nasdaq MarketSite.jpg", alt="", credit="x") is False
    P.stdout = '{"result": "yes, it shows the podium"}'
    assert judge.photo_fits(settings, headline="h", summary="", title="t", alt="", credit="c") is True
    monkeypatch.setattr(judge, "available", lambda s: False)
    assert judge.photo_fits(settings, headline="h", summary="", title="t", alt="", credit="c") is None
