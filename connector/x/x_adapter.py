# -*- coding: utf-8 -*-
import re
import time


def strip_bot_mention(text, bot_username):
    if not text:
        return ""
    bot_username = (bot_username or "").lstrip("@")
    if not bot_username:
        return text.strip()

    pattern = re.compile(rf"^@{re.escape(bot_username)}\b\s*", re.IGNORECASE)
    cleaned = pattern.sub("", text.strip())
    return cleaned.strip()


def _parse_created_at(created_at):
    input_timestamp = int(time.time())
    if not created_at:
        return input_timestamp
    try:
        from datetime import datetime

        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%a %b %d %H:%M:%S %z %Y"):
            try:
                dt = datetime.strptime(created_at, fmt)
                return int(dt.timestamp())
            except ValueError:
                continue
    except Exception:
        pass
    return input_timestamp


def _build_image_message(text, media_urls):
    image_urls = [url for url in (media_urls or []) if url]
    if not image_urls:
        return "text", text, {}

    image_text = text or "[图片]"
    metadata = {"url": image_urls[0], "image_urls": image_urls}
    return "image", image_text, metadata


def mention_to_std(
    tweet,
    author,
    character_x_user_id,
    bot_username,
    media_urls=None,
    image_description=None,
):
    tweet_id = str(tweet["id"])
    input_timestamp = _parse_created_at(tweet.get("created_at"))

    text = strip_bot_mention(tweet.get("text", ""), bot_username)
    if not text:
        text = tweet.get("text", "").strip()

    if image_description:
        message_type = "image"
        message = image_description
        metadata = {
            "tweet_id": tweet_id,
            "author_id": tweet.get("author_id"),
            "conversation_id": tweet.get("conversation_id"),
            "in_reply_to_user_id": tweet.get("in_reply_to_user_id"),
            "character_x_user_id": character_x_user_id,
            "url": (media_urls or [None])[0],
            "image_urls": media_urls or [],
        }
    else:
        message_type, message, extra_metadata = _build_image_message(text, media_urls)
        metadata = {
            "tweet_id": tweet_id,
            "author_id": tweet.get("author_id"),
            "conversation_id": tweet.get("conversation_id"),
            "in_reply_to_user_id": tweet.get("in_reply_to_user_id"),
            "character_x_user_id": character_x_user_id,
        }
        metadata.update(extra_metadata)

    return {
        "input_timestamp": input_timestamp,
        "handled_timestamp": None,
        "status": "pending",
        "platform": "x",
        "chatroom_name": tweet_id,
        "message_type": message_type,
        "message": message,
        "metadata": metadata,
    }


def activity_tweet_to_std(tweet, character_x_user_id, bot_username, media_urls=None, image_description=None):
    v2_like = {
        "id": str(tweet.get("id_str") or tweet.get("id")),
        "text": tweet.get("text", ""),
        "author_id": str(tweet.get("user", {}).get("id_str") or tweet.get("user", {}).get("id") or ""),
        "created_at": tweet.get("created_at"),
        "conversation_id": tweet.get("conversation_id"),
        "in_reply_to_user_id": tweet.get("in_reply_to_user_id_str"),
    }
    author = {
        "id": v2_like["author_id"],
        "username": tweet.get("user", {}).get("screen_name"),
        "name": tweet.get("user", {}).get("name"),
    }
    return mention_to_std(
        v2_like,
        author,
        character_x_user_id,
        bot_username,
        media_urls=media_urls,
        image_description=image_description,
    )


def std_to_x_tweet(message):
    text = message.get("message", "")
    metadata = message.get("metadata") or {}
    in_reply_to_tweet_id = metadata.get("in_reply_to_tweet_id")

    if message.get("message_type") == "voice":
        text = metadata.get("voice_text") or text

    media_urls = []
    if message.get("message_type") == "image":
        if metadata.get("url"):
            media_urls.append(metadata["url"])
        for url in metadata.get("image_urls", []):
            if url and url not in media_urls:
                media_urls.append(url)

    return {
        "text": text,
        "in_reply_to_tweet_id": in_reply_to_tweet_id,
        "media_urls": media_urls,
    }
