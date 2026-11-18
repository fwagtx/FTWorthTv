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

    def publish(self, draft: PostDraft) -> PublishResult:
        s = self.settings
        when = draft.scheduled_at or (datetime.now(timezone.utc) + timedelta(minutes=5))
        local = when.astimezone(s.tz)
        media = [u for u in [self.media_url(draft)] if u]
        networks = list(s.metricool_networks)
        if not media and "instagram" in networks:
            log.warning("Instagram needs an image; dropping it for this post (set MEDIA_BASE_URL)")
            networks = [n for n in networks if n != "instagram"]
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
            body["facebookData"] = {"type": "POST"}
        if "instagram" in networks:
            body["instagramData"] = {"type": "POST"}
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
        return PublishResult(ok=True, publisher=self.name, post_id=post_id, url=url,
                             detail=f"scheduled for {local.strftime('%Y-%m-%d %H:%M %Z')} on {', '.join(networks)}")
