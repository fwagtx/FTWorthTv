"""Schedule through Metricool's public API (needs the API add-on). Lets Metricool handle Facebook + Instagram publishing."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from ..models import PostDraft, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)
API = "https://app.metricool.com/api/v2/scheduler/posts"


class MetricoolError(RuntimeError):
    pass


class MetricoolPublisher(Publisher):
    name = "metricool"

    def __init__(self, settings):
        super().__init__(settings)
        if not (settings.metricool_user_token and settings.metricool_user_id and settings.metricool_blog_id):
            raise MetricoolError("METRICOOL_USER_TOKEN, METRICOOL_USER_ID and METRICOOL_BLOG_ID are required")

    def media_url(self, draft: PostDraft) -> str | None:
        """Metricool needs a PUBLIC URL for media. We serve committed images from MEDIA_BASE_URL (e.g. raw.githubusercontent.com)."""
        from .base import public_media_url
        return public_media_url(draft, self.settings)

    @staticmethod
    def wait_public(url: str, *, tries: int = 12, pause: float = 5.0) -> bool:
        """raw.githubusercontent.com can lag a few seconds behind a push; Metricool fetches the image at once."""
        import time
        for _ in range(tries):
            try:
                if requests.head(url, timeout=20, allow_redirects=True).status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(pause)
        return False

    def publish(self, draft: PostDraft) -> PublishResult:
        s = self.settings
        when = draft.scheduled_at or (datetime.now(timezone.utc) + timedelta(minutes=5))
        local = when.astimezone(s.tz)
        media = [u for u in [self.media_url(draft)] if u]
        for u in media:
            if not self.wait_public(u):
                return PublishResult(ok=False, publisher=self.name, detail=f"image not reachable at {u}")
        networks = list(s.metricool_networks)
        is_video = draft.mode == "video" and bool(media)
        if not media and "instagram" in networks:
            log.warning("Instagram needs an image; dropping it for this post (set MEDIA_BASE_URL)")
            networks = [n for n in networks if n != "instagram"]
        if is_video and "instagram" in networks and not self.instagram_takes_video(draft):
            networks = [n for n in networks if n != "instagram"]   # the clip goes to Facebook; Reels only for portrait clips, when enabled
        text = draft.caption_text()
        if draft.mode in ("link", "share") or not media:   # Metricool has no share type: the post URL goes in the text as a link preview
            text += f"\n\n{draft.link or draft.story.url}"
        body = {
            "providers": [{"network": n} for n in networks],
            "publicationDate": {"dateTime": local.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": str(s.tz)},
            "text": text,
            "media": media,
            "mediaAltText": [draft.copy.headline] if media else [],
            "autoPublish": bool(s.metricool_autopublish),
            "draft": False,
            "firstCommentText": draft.first_comment_text(),
            "shortener": False,
            "descendants": [],
            "smartLinkData": {"ids": []},
            "hasNotReadNotes": False,
        }
        if "facebook" in networks:
            body["facebookData"] = {"type": "POST"}             # an mp4 in an ordinary post is a Facebook video post
        if "instagram" in networks:
            body["instagramData"] = {"type": "REEL" if is_video else "POST"}
        if not networks:
            return PublishResult(ok=False, publisher=self.name, detail="no network takes this post")
        try:
            resp = requests.post(API, params={"blogId": s.metricool_blog_id, "userId": s.metricool_user_id},
                                 headers={"X-Mc-Auth": s.metricool_user_token, "Content-Type": "application/json"},
                                 json=body, timeout=90)
            payload = resp.json() if resp.content else {}
            if not resp.ok:
                raise MetricoolError(f"HTTP {resp.status_code}: {str(payload)[:300]}")
        except (requests.RequestException, ValueError, MetricoolError) as exc:
            return PublishResult(ok=False, publisher=self.name, detail=str(exc))
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        post_id = str(data.get("id")) if isinstance(data, dict) and data.get("id") else None
        url = data.get("plannerUrl") if isinstance(data, dict) else None
        detail = f"scheduled for {local.strftime('%Y-%m-%d %H:%M %Z')} on {', '.join(networks)}"
        story_id = self.publish_story(draft, local, networks)
        if story_id:
            detail += f"; story {story_id}"
        return PublishResult(ok=True, publisher=self.name, post_id=post_id, url=url, detail=detail)

    def instagram_takes_video(self, draft: PostDraft) -> bool:
        """Instagram gets a native clip only as a Reel, only when brand.video.instagram is on, and only portrait clips: a
        square radar loop or a landscape phone clip would be padded or cropped there, so it stays a Facebook video."""
        cfg = self.settings.brand.get("video", {}) or {}
        if not cfg.get("instagram", False):
            log.info("Instagram skipped for the clip (video.instagram is off); Facebook gets it")
            return False
        from ..images.video import is_portrait
        if not draft.video_path or not is_portrait(draft.video_path):
            log.info("Instagram skipped for the clip: not portrait")
            return False
        return True

    def publish_story(self, draft: PostDraft, post_local: datetime, networks: list[str]) -> str | None:
        """The same post as a Story a couple of minutes after the feed post (no caption: stories carry none)."""
        s = self.settings
        cfg = s.brand.get("stories", {}) or {}
        if not cfg.get("enabled", True) or not draft.story_path:
            return None
        from .base import public_url_for
        url = public_url_for(draft.story_path, s)
        wanted = [n for n in (cfg.get("networks") or ["facebook", "instagram"]) if n in networks]
        if not url or not wanted or not self.wait_public(url):
            log.warning("story skipped for %s (no public image or no story network)", draft.story.title[:60])
            return None
        when = post_local + timedelta(minutes=int(cfg.get("delay_minutes", 2)))
        body = {
            "providers": [{"network": n} for n in wanted],
            "publicationDate": {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": str(s.tz)},
            "text": "",
            "media": [url],
            "mediaAltText": [draft.copy.headline],
            "autoPublish": bool(s.metricool_autopublish),
            "draft": False,
            "firstCommentText": "",
            "shortener": False,
            "descendants": [],
            "smartLinkData": {"ids": []},
            "hasNotReadNotes": False,
        }
        if "facebook" in wanted:
            body["facebookData"] = {"type": "STORY"}
        if "instagram" in wanted:
            body["instagramData"] = {"type": "STORY"}
        try:
            resp = requests.post(API, params={"blogId": s.metricool_blog_id, "userId": s.metricool_user_id},
                                 headers={"X-Mc-Auth": s.metricool_user_token, "Content-Type": "application/json"},
                                 json=body, timeout=90)
            payload = resp.json() if resp.content else {}
            if not resp.ok:
                raise MetricoolError(f"HTTP {resp.status_code}: {str(payload)[:300]}")
        except (requests.RequestException, ValueError, MetricoolError) as exc:
            log.warning("story for %s failed: %s", draft.story.title[:60], exc)
            return None
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        return str(data.get("id")) if isinstance(data, dict) and data.get("id") else "ok"
