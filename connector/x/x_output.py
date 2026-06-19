# -*- coding: utf-8 -*-
import asyncio
import logging
import sys
import time
import traceback

sys.path.append(".")

from connector.x.x_adapter import std_to_x_tweet
from connector.x.x_api import XAPI, XAPIError
from dao.mongo import MongoDBBase
from dao.user_dao import UserDAO
from entity.message import save_outputmessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLATFORM = "x"


async def run_output_loop():
    while True:
        await asyncio.sleep(1)
        await output_handler()


async def main():
    await run_output_loop()


async def output_handler():
    mongo = MongoDBBase()
    user_dao = UserDAO()
    message = None

    try:
        now = int(time.time())
        message = mongo.find_one(
            "outputmessages",
            {
                "platform": PLATFORM,
                "status": "pending",
                "expect_output_timestamp": {"$lt": now},
            },
        )
        if message is None:
            return

        logger.info("sending x message: %s", message)

        character = user_dao.get_user_by_id(message["from_user"])
        if character is None:
            raise RuntimeError("character not found: " + str(message["from_user"]))

        tweet_payload = std_to_x_tweet(message)
        if message["message_type"] == "voice" and not tweet_payload["text"]:
            tweet_payload["text"] = message.get("message", "")

        api = XAPI()
        media_ids = []
        for media_url in tweet_payload.get("media_urls", [])[:4]:
            media_ids.append(api.upload_media_from_url(media_url))

        resp = api.create_tweet(
            text=tweet_payload.get("text"),
            in_reply_to_tweet_id=tweet_payload.get("in_reply_to_tweet_id"),
            media_ids=media_ids or None,
        )

        tweet_id = (resp.get("data") or {}).get("id")
        message["status"] = "handled"
        message["handled_timestamp"] = int(time.time())
        message.setdefault("metadata", {})
        message["metadata"]["tweet_id"] = tweet_id
        message["metadata"]["media_ids"] = media_ids
        message["metadata"]["x_response"] = resp
        save_outputmessage(message)
        logger.info("tweet sent: %s", tweet_id)

    except XAPIError as exc:
        logger.error("x output api error: %s", exc)
        if message is not None:
            message["status"] = "failed"
            message["handled_timestamp"] = int(time.time())
            message.setdefault("metadata", {})
            message["metadata"]["x_error"] = str(exc)
            save_outputmessage(message)
    except Exception:
        logger.error(traceback.format_exc())
        if message is not None:
            message["status"] = "failed"
            message["handled_timestamp"] = int(time.time())
            save_outputmessage(message)


if __name__ == "__main__":
    asyncio.run(main())
