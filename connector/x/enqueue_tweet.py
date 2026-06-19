#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enqueue a standalone tweet into outputmessages for the X connector."""
import argparse
import sys
import time

sys.path.append(".")

from conf.config import CONF
from dao.user_dao import UserDAO
from qiaoyun.util.message_util import send_message


def main():
    parser = argparse.ArgumentParser(description="Enqueue a standalone tweet for x_output")
    parser.add_argument("text", help="tweet text")
    parser.add_argument(
        "--character",
        default=None,
        help="character name, defaults to conf.x.character_name",
    )
    parser.add_argument(
        "--reply-to",
        dest="reply_to",
        help="optional tweet id to reply to",
    )
    parser.add_argument(
        "--image-url",
        dest="image_url",
        action="append",
        default=[],
        help="image url to attach; can be repeated",
    )
    args = parser.parse_args()

    character_name = args.character or CONF.get("x", {}).get("character_name", "qiaoyun")
    user_dao = UserDAO()
    characters = user_dao.find_characters({"name": character_name}, limit=1)
    if not characters:
        raise SystemExit(f"character not found: {character_name}")

    character = characters[0]
    character_id = str(character["_id"])
    metadata = {}
    if args.reply_to:
        metadata["in_reply_to_tweet_id"] = args.reply_to
    if args.image_url:
        metadata["url"] = args.image_url[0]
        metadata["image_urls"] = args.image_url

    message_type = "image" if args.image_url else "text"
    output = send_message(
        platform="x",
        from_user=character_id,
        to_user=character_id,
        chatroom_name=None,
        message=args.text,
        message_type=message_type,
        status="pending",
        expect_output_timestamp=int(time.time()),
        metadata=metadata,
    )
    print(output)


if __name__ == "__main__":
    main()
