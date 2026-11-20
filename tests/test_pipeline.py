import json

from ftworthtv.examples import example_stories
from ftworthtv.pipeline import in_quiet_hours, run
from ftworthtv.queue import load_draft, publish_run


def test_offline_dry_run_end_to_end(settings, now):
    settings.max_posts = 3
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    assert report.candidates >= 15
    assert len(report.drafts) == 3 and all(r.ok for r in report.results)
    assert report.drafts[0].story.source_kind == "nws_alert"          # severe weather first
    assert report.drafts[1].scheduled_at is not None                    # later posts are spaced out
    for draft in report.drafts:
        assert draft.image and draft.image.path.exists()
        folder = draft.image.path.parent
        assert (folder / "post.json").exists() and (folder / "caption.txt").exists()
    assert (report.run_dir / "preview.html").exists() and (report.run_dir / "report.json").exists()
    assert (settings.out_dir / "latest-preview.html").exists()
    assert not settings.state_path.exists()                             # dry runs never touch the real memory
    assert (report.run_dir / "state-after-dry-run.json").exists()


def test_two_phase_publish_reloads_drafts(settings, now):
    settings.max_posts = 2
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    folder = report.drafts[0].image.path.parent
    draft = load_draft(folder)
    assert draft and draft.story.title == report.drafts[0].story.title and draft.image.path.exists()
    results = publish_run(report.run_dir, settings, "dryrun")
    assert len(results) == 2 and all(r.ok for _, r in results)


def test_quiet_hours_only_allow_urgent(settings, now):
    from datetime import datetime, timezone
    late = datetime(2026, 11, 20, 8, 30, tzinfo=timezone.utc)  # 2:30am Central
    assert in_quiet_hours(late.astimezone(settings.tz), [23, 6])
    report = run(settings, now=late, stories=example_stories(settings, late), publisher_name="dryrun")
    assert all(d.story.is_urgent for d in report.drafts) and len(report.drafts) == 1


def test_link_mode_for_news(settings, now):
    settings.brand["posting"]["news_photo_mode"] = "link"
    settings.max_posts = 3
    report = run(settings, now=now, stories=[s for s in example_stories(settings, now) if s.source_kind == "rss"], publisher_name="dryrun")
    assert report.drafts and all(d.mode == "link" and d.link for d in report.drafts)
    data = json.loads((report.run_dir / "report.json").read_text())
    assert data["posts"][0]["mode"] == "link"


def test_outlet_story_without_a_verified_photo_becomes_a_link_post(settings, now):
    from datetime import timedelta
    from ftworthtv.models import Story
    story = Story(id="l1", source="FOX 4 Dallas-Fort Worth", source_kind="rss", title="Fort Worth country club expels Bo French after social media controversies",
                  summary="A Fort Worth country club has expelled Bo French, the Tarrant County Republican chairman, after a series of social media posts.",
                  url="https://www.fox4news.com/news/fort-worth-country-club-bo-french", published=now - timedelta(hours=1), category_hint="politics", extra={"scope": "local"})
    settings.max_posts = 1
    report = run(settings, now=now, stories=[story], publisher_name="dryrun")
    d = report.drafts[0]
    assert d.mode == "link" and d.link == story.url and d.image is None      # Facebook shows FOX 4's own photo in the preview
    assert any("link post" in n for n in report.notes)


def test_session_manifest_and_record(settings, now):
    import json as _json
    from ftworthtv.session import build_manifest, record_posted
    settings.max_posts = 2
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    rows = build_manifest(report.run_dir, settings, branch="renders/test-1", repo="me/repo", start=now)
    live = [r for r in rows if not r.get("skip")]
    assert len(live) == 2 and live[0]["image_url"].startswith("https://raw.githubusercontent.com/me/repo/renders/test-1/out/runs/")
    assert live[0]["metricool"]["post"]["media"] == [live[0]["image_url"]] and live[0]["metricool"]["post"]["facebookData"] == {"type": "POST"}
    assert live[0]["metricool"]["story"]["facebookData"] == {"type": "STORY"} and live[1]["at"] > live[0]["at"]
    n = record_posted(report.run_dir, settings, {live[0]["story_id"]: {"post_id": "123", "story_post_id": "124", "at": now.isoformat()}})
    assert n == 1
    from ftworthtv.state import State
    assert State(settings.state_path).has(live[0]["story_id"])
    rows2 = build_manifest(report.run_dir, settings, branch="renders/test-1", repo="me/repo", start=now)
    assert any(r.get("skip") == "already posted" for r in rows2)


def test_session_manifest_uses_the_brand_networks(settings, now):
    from ftworthtv.session import build_manifest
    settings.brand.setdefault("posting", {})["networks"] = ["facebook", "instagram"]
    settings.max_posts = 1
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    live = [r for r in build_manifest(report.run_dir, settings, branch="renders/t", repo="me/repo", start=now) if not r.get("skip")]
    nets = [p["network"] for p in live[0]["metricool"]["post"]["providers"]]
    assert nets == ["facebook", "instagram"] and live[0]["metricool"]["post"]["instagramData"]["type"] == "POST"
