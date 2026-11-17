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
