# -*- coding: utf-8 -*-
import json
import logging
import mimetypes
import sys
from urllib.parse import urlparse

import requests
from requests_oauthlib import OAuth1

sys.path.append(".")

from conf.config import CONF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = "https://api.twitter.com/2"
UPLOAD_BASE = "https://upload.twitter.com/1.1"
ACCOUNT_ACTIVITY_BASE = "https://api.twitter.com/1.1/account_activity"
MAX_TWEET_LENGTH = 280
SIMPLE_UPLOAD_LIMIT = 5 * 1024 * 1024


class XAPIError(Exception):
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}

    @property
    def reason(self):
        return self.response.get("reason")

    def portal_hint(self):
        if self.reason == "client-not-enrolled":
            return (
                "当前 App 未 enrolled 到 X API v2。\n"
                "2026 年起新开发者已不能靠旧版「Apps in Free (DEPRECATED)」发推。\n"
                "请改用 Pay-Per-Use 开发者控制台：\n"
                "  1. 打开 https://console.x.com 并用 @crazycozy777 登录\n"
                "  2. 完成 Pay-Per-Use 开通（绑定支付方式）\n"
                "  3. 购买少量 Credits（发推约 $0.015/条）\n"
                "  4. 在 console 里创建 Project + App（不要继续用 developer.x.com 里 DEPRECATED 的 Free App）\n"
                "  5. App 权限设为 Read and write，生成新的 OAuth 1.0a 四件套\n"
                "  6. 更新 conf/config.json 的 x 段\n"
                "  7. 机器人/自动化用途可能触发额外审核，按控制台提示提交 use case\n"
                "旧 portal: https://developer.x.com/en/portal/dashboard 里的 Free App 无法修复此错误。"
            )
        return None


class XAPI:
    """X (Twitter) API client using OAuth 1.0a User Context."""

    def __init__(self, config=None):
        self.config = config or CONF.get("x", {})
        self._auth = OAuth1(
            self.config["api_key"],
            self.config["api_secret"],
            self.config["access_token"],
            self.config["access_token_secret"],
        )

    def _request(
        self,
        method,
        url,
        params=None,
        json_body=None,
        data=None,
        files=None,
        timeout=30,
    ):
        response = requests.request(
            method,
            url,
            auth=self._auth,
            params=params,
            json=json_body,
            data=data,
            files=files,
            timeout=timeout,
        )
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"raw": response.text}

        if response.status_code >= 400:
            raise XAPIError(
                f"X API error {response.status_code}: {payload}",
                status_code=response.status_code,
                response=payload,
            )
        return payload

    def _v2_request(self, method, path, params=None, json_body=None, timeout=30):
        return self._request(
            method,
            f"{API_BASE}{path}",
            params=params,
            json_body=json_body,
            timeout=timeout,
        )

    def verify_credentials_v1(self):
        """v1.1 fallback; works for some standalone apps when v2 is not enrolled."""
        return self._request(
            "GET",
            "https://api.twitter.com/1.1/account/verify_credentials.json",
            params={"skip_status": "true"},
        )

    def get_me(self, allow_v1_fallback=False):
        try:
            return self._v2_request(
                "GET",
                "/users/me",
                params={"user.fields": "id,username,name"},
            )
        except XAPIError as exc:
            if not allow_v1_fallback or exc.reason != "client-not-enrolled":
                raise
            logger.warning("v2 /users/me unavailable (%s), trying v1.1 verify_credentials", exc.reason)
            payload = self.verify_credentials_v1()
            return {
                "data": {
                    "id": str(payload.get("id_str") or payload.get("id")),
                    "username": payload.get("screen_name"),
                    "name": payload.get("name"),
                },
                "_source": "v1.1",
                "_warning": (
                    "v2 未开通，当前仅 v1.1 验证成功；发推仍需在门户将 App 挂到 Project 并重新生成密钥"
                ),
            }

    def create_tweet(self, text=None, in_reply_to_tweet_id=None, media_ids=None):
        body = {}
        text = (text or "").strip()
        if text:
            if len(text) > MAX_TWEET_LENGTH:
                text = text[: MAX_TWEET_LENGTH - 1] + "…"
            body["text"] = text

        if media_ids:
            body["media"] = {"media_ids": [str(media_id) for media_id in media_ids]}

        if not body.get("text") and not body.get("media"):
            raise XAPIError("tweet must include text or media")

        if in_reply_to_tweet_id:
            body["reply"] = {"in_reply_to_tweet_id": str(in_reply_to_tweet_id)}

        logger.info("creating tweet: %s", body)
        return self._v2_request("POST", "/tweets", json_body=body)

    def get_mentions(self, user_id, since_id=None, max_results=20):
        params = {
            "tweet.fields": (
                "created_at,author_id,conversation_id,in_reply_to_user_id,attachments"
            ),
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "username,name",
            "media.fields": "url,type,preview_image_url",
            "max_results": min(max(max_results, 5), 100),
        }
        if since_id:
            params["since_id"] = str(since_id)

        return self._v2_request("GET", f"/users/{user_id}/mentions", params=params)

    def get_user_by_username(self, username):
        username = username.lstrip("@")
        return self._v2_request(
            "GET",
            f"/users/by/username/{username}",
            params={"user.fields": "id,username,name"},
        )

    def download_url(self, url, timeout=30):
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")

    def upload_media_bytes(self, media_bytes, filename="image.jpg", media_type=None):
        if not media_bytes:
            raise XAPIError("media bytes are empty")

        if media_type is None:
            media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if len(media_bytes) <= SIMPLE_UPLOAD_LIMIT:
            payload = self._request(
                "POST",
                f"{UPLOAD_BASE}/media/upload.json",
                files={"media": (filename, media_bytes, media_type)},
                timeout=60,
            )
        else:
            payload = self._upload_media_chunked(media_bytes, media_type)

        media_id = payload.get("media_id_string") or str(payload.get("media_id", ""))
        if not media_id:
            raise XAPIError(f"media upload missing media_id: {payload}")
        return media_id

    def upload_media_from_url(self, url):
        media_bytes, content_type = self.download_url(url)
        filename = urlparse(url).path.rsplit("/", 1)[-1] or "image.jpg"
        if "." not in filename:
            extension = mimetypes.guess_extension(content_type or "") or ".jpg"
            filename = f"image{extension}"
        return self.upload_media_bytes(media_bytes, filename=filename, media_type=content_type)

    def _upload_media_chunked(self, media_bytes, media_type):
        init_payload = self._request(
            "POST",
            f"{UPLOAD_BASE}/media/upload.json",
            data={
                "command": "INIT",
                "total_bytes": len(media_bytes),
                "media_type": media_type,
            },
            timeout=60,
        )
        media_id = init_payload.get("media_id_string") or str(init_payload["media_id"])

        segment_index = 0
        chunk_size = 4 * 1024 * 1024
        for offset in range(0, len(media_bytes), chunk_size):
            chunk = media_bytes[offset : offset + chunk_size]
            self._request(
                "POST",
                f"{UPLOAD_BASE}/media/upload.json",
                data={
                    "command": "APPEND",
                    "media_id": media_id,
                    "segment_index": segment_index,
                },
                files={"media": (f"chunk-{segment_index}", chunk, "application/octet-stream")},
                timeout=120,
            )
            segment_index += 1

        return self._request(
            "POST",
            f"{UPLOAD_BASE}/media/upload.json",
            data={
                "command": "FINALIZE",
                "media_id": media_id,
            },
            timeout=60,
        )

    def register_webhook(self, webhook_url, environment_name=None):
        environment_name = environment_name or self.config.get("environment_name", "prod")
        return self._request(
            "POST",
            f"{ACCOUNT_ACTIVITY_BASE}/all/{environment_name}/webhooks.json",
            params={"url": webhook_url},
            timeout=30,
        )

    def list_webhooks(self, environment_name=None):
        environment_name = environment_name or self.config.get("environment_name", "prod")
        return self._request(
            "GET",
            f"{ACCOUNT_ACTIVITY_BASE}/all/{environment_name}/webhooks.json",
            timeout=30,
        )

    def subscribe_account_activity(self, webhook_id, environment_name=None):
        environment_name = environment_name or self.config.get("environment_name", "prod")
        return self._request(
            "POST",
            f"{ACCOUNT_ACTIVITY_BASE}/all/{environment_name}/subscriptions.json",
            params={"webhook_id": webhook_id},
            timeout=30,
        )

    def list_subscriptions(self, environment_name=None):
        environment_name = environment_name or self.config.get("environment_name", "prod")
        return self._request(
            "GET",
            f"{ACCOUNT_ACTIVITY_BASE}/all/{environment_name}/subscriptions.json",
            timeout=30,
        )
