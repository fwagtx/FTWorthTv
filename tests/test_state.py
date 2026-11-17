from datetime import datetime, timedelta, timezone

from ftworthtv.models import ImageAsset, PostCopy, PostDraft, PublishResult, Story
from ftworthtv.state import State


def _draft(tmp_path, sid="abc"):
    story = Story(id=sid, source="Fort Worth Report", source_kind="rss", title="T", summary="S", url="https://x/t")
    copy = PostCopy(headline="H", caption="C", category="food")
    image = ImageAsset(path=tmp_path / "card.jpg", credit="Photo: X via Pexels", license="pexels", provider="pexels", photo_id="pexels-1")
    return PostDraft(story=story, copy=copy, writer="template", image=image)


def test_record_roundtrip_and_prune(tmp_path):
    path = tmp_path / "state" / "posted.json"
    state = State(path)
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    state.record(_draft(tmp_path), PublishResult(ok=True, publisher="facebook", post_id="1_2"), now, "2026-11-19")
    state.save()
    reloaded = State(path)
    assert reloaded.has("abc") and reloaded.posts_on("2026-11-19") == 1 and reloaded.total_posts == 1
    assert reloaded.photo_recently_used("pexels-1") and not reloaded.photo_recently_used("pexels-2")
    assert reloaded.last_post_at == now
    assert reloaded.prune(now + timedelta(days=60)) == 1
    assert not reloaded.has("abc")
