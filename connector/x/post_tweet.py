#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI helper to post a tweet or reply directly via X API."""
import argparse
import json
import sys

sys.path.append(".")

from connector.x.x_api import XAPI, XAPIError


def main():
    parser = argparse.ArgumentParser(description="Post a tweet or reply on X")
    parser.add_argument("text", nargs="?", default="", help="tweet text")
    parser.add_argument(
        "--reply-to",
        dest="reply_to",
        help="tweet id to reply to",
    )
    parser.add_argument(
        "--image-url",
        dest="image_url",
        action="append",
        default=[],
        help="image url to upload and attach; can be repeated",
    )
    args = parser.parse_args()

    api = XAPI()
    try:
        media_ids = []
        for image_url in args.image_url:
            media_ids.append(api.upload_media_from_url(image_url))

        result = api.create_tweet(
            text=args.text,
            in_reply_to_tweet_id=args.reply_to,
            media_ids=media_ids or None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except XAPIError as exc:
        print(str(exc), file=sys.stderr)
        hint = exc.portal_hint()
        if hint:
            print("\n" + hint, file=sys.stderr)
            client_id = (exc.response or {}).get("client_id")
            if client_id:
                print(
                    f"\n当前 App ID = {client_id} 未开通 v2。"
                    "若已挂到 Project 仍失败，请在 Project 内「新建 App」（不要继续用 Standalone 旧 App），"
                    "用新 App 的四组密钥更新 conf/config.json。",
                    file=sys.stderr,
                )
        print("\n诊断: python3 connector/x/verify_setup.py", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
