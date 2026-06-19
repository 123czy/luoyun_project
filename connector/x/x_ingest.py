# -*- coding: utf-8 -*-
import logging
import sys
import traceback

sys.path.append(".")

from conf.config import CONF
from connector.x.x_adapter import activity_tweet_to_std, mention_to_std
from connector.x.x_api import XAPI
from connector.x.x_state import get_state, set_state
from dao.mongo import MongoDBBase
from dao.user_dao import UserDAO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATE_KEY_LAST_MENTION = "x_last_mention_id"
PLATFORM = "x"


def get_character():
    user_dao = UserDAO()
    character_name = CONF.get("x", {}).get("character_name", "qiaoyun")
    characters = user_dao.find_characters({"name": character_name}, limit=1)
    if not characters:
        raise RuntimeError(f"character not found: {character_name}")
    character = characters[0]
    x_info = character.get("platforms", {}).get(PLATFORM)
    if not x_info or not x_info.get("id"):
        raise RuntimeError(
            f"character {character_name} missing platforms.x.id; update prepare_character.py"
        )
    return character, x_info


def is_duplicate_tweet(mongo, tweet_id):
    existing = mongo.find_one(
        "inputmessages",
        {"platform": PLATFORM, "metadata.tweet_id": str(tweet_id)},
    )
    return existing is not None


def get_or_create_user(user_dao, author_id, author=None):
    author = author or {}
    users = user_dao.find_users({f"platforms.{PLATFORM}.id": str(author_id)}, limit=1)
    if users:
        return str(users[0]["_id"])

    username = author.get("username") or author.get("screen_name") or str(author_id)
    nickname = author.get("name") or username

    uid = user_dao.create_user(
        {
            "is_character": False,
            "name": username,
            "platforms": {
                PLATFORM: {
                    "id": str(author_id),
                    "account": username,
                    "nickname": nickname,
                }
            },
            "status": "normal",
            "user_info": {},
        }
    )
    logger.info("created x user %s (%s)", username, uid)
    return uid


def tweet_mentions_bot(tweet, bot_user_id, bot_username):
    bot_user_id = str(bot_user_id)
    bot_username = (bot_username or "").lstrip("@").lower()

    author_id = str(
        tweet.get("author_id")
        or tweet.get("user", {}).get("id_str")
        or tweet.get("user", {}).get("id")
        or ""
    )
    if author_id == bot_user_id:
        return False

    if tweet.get("retweeted_status") or tweet.get("retweeted_status_result"):
        return False

    entities = tweet.get("entities") or {}
    for mention in entities.get("user_mentions", []):
        mention_id = str(mention.get("id_str") or mention.get("id") or "")
        mention_name = (mention.get("screen_name") or "").lower()
        if mention_id == bot_user_id or mention_name == bot_username:
            return True

    text = (tweet.get("text") or "").lower()
    if bot_username and f"@{bot_username}" in text:
        return True

    return False


def _media_map_from_v2_payload(payload):
    media_map = {}
    for media in payload.get("includes", {}).get("media", []):
        media_map[media.get("media_key")] = media
    return media_map


def _photo_urls_from_v2_tweet(tweet, media_map):
    urls = []
    for media_key in (tweet.get("attachments") or {}).get("media_keys", []):
        media = media_map.get(media_key) or {}
        if media.get("type") == "photo":
            url = media.get("url") or media.get("preview_image_url")
            if url:
                urls.append(url)
    return urls


def _photo_urls_from_activity_tweet(tweet):
    urls = []
    entities = tweet.get("extended_entities") or tweet.get("entities") or {}
    for media in entities.get("media", []):
        if media.get("type") == "photo":
            url = media.get("media_url_https") or media.get("media_url")
            if url:
                urls.append(url)
    return urls


def _describe_image_urls(image_urls):
    if not image_urls:
        return None, []
    try:
        from framework.tool.image2text.ark import ark_image2text

        descriptions = []
        for image_url in image_urls:
            descriptions.append(
                ark_image2text("请详细描述图中有什么？输出不要分段和换行。", image_url=image_url)
            )
        return "\n".join(descriptions), image_urls
    except Exception:
        logger.error("image description failed: %s", traceback.format_exc())
        return "[图片]", image_urls


def ingest_tweet_document(
    mongo,
    user_dao,
    tweet,
    author,
    character,
    x_info,
    source="poll",
    media_urls=None,
):
    character_id = str(character["_id"])
    character_x_user_id = str(x_info["id"])
    bot_username = x_info.get("account", "")

    tweet_id = str(tweet.get("id") or tweet.get("id_str"))
    if not tweet_id:
        return False

    author_id = str(
        tweet.get("author_id")
        or author.get("id")
        or tweet.get("user", {}).get("id_str")
        or ""
    )
    if author_id == character_x_user_id:
        return False

    if not tweet_mentions_bot(tweet, character_x_user_id, bot_username):
        return False

    if is_duplicate_tweet(mongo, tweet_id):
        return False

    uid = get_or_create_user(user_dao, author_id, author)

    image_description = None
    if media_urls:
        image_description, media_urls = _describe_image_urls(media_urls)

    if tweet.get("id_str") or tweet.get("user"):
        std = activity_tweet_to_std(
            tweet,
            character_x_user_id,
            bot_username,
            media_urls=media_urls,
            image_description=image_description,
        )
    else:
        std = mention_to_std(
            tweet,
            author,
            character_x_user_id,
            bot_username,
            media_urls=media_urls,
            image_description=image_description,
        )

    std["from_user"] = uid
    std["to_user"] = character_id
    std.setdefault("metadata", {})
    std["metadata"]["source"] = source

    mongo.insert_one("inputmessages", std)
    logger.info("queued %s mention tweet %s from user %s", source, tweet_id, uid)
    return True


def ingest_v2_mentions_payload(payload, source="poll"):
    mongo = MongoDBBase()
    user_dao = UserDAO()
    character, x_info = get_character()
    media_map = _media_map_from_v2_payload(payload)

    users_by_id = {}
    for user in payload.get("includes", {}).get("users", []):
        users_by_id[str(user["id"])] = user

    ingested = 0
    latest_id = get_state(STATE_KEY_LAST_MENTION)
    tweets = sorted(payload.get("data") or [], key=lambda item: int(item["id"]))

    for tweet in tweets:
        tweet_id = str(tweet["id"])
        latest_id = tweet_id
        author_id = str(tweet.get("author_id", ""))
        author = users_by_id.get(author_id, {"id": author_id})
        media_urls = _photo_urls_from_v2_tweet(tweet, media_map)

        if ingest_tweet_document(
            mongo,
            user_dao,
            tweet,
            author,
            character,
            x_info,
            source=source,
            media_urls=media_urls,
        ):
            ingested += 1

    if latest_id and latest_id != get_state(STATE_KEY_LAST_MENTION):
        set_state(STATE_KEY_LAST_MENTION, latest_id)

    return ingested


def ingest_activity_payload(payload, source="webhook"):
    mongo = MongoDBBase()
    user_dao = UserDAO()
    character, x_info = get_character()

    ingested = 0
    tweet_events = payload.get("tweet_create_events") or []
    for tweet in tweet_events:
        author = tweet.get("user") or {}
        media_urls = _photo_urls_from_activity_tweet(tweet)
        if ingest_tweet_document(
            mongo,
            user_dao,
            tweet,
            author,
            character,
            x_info,
            source=source,
            media_urls=media_urls,
        ):
            ingested += 1
            tweet_id = str(tweet.get("id_str") or tweet.get("id"))
            if tweet_id:
                set_state(STATE_KEY_LAST_MENTION, tweet_id)

    return ingested


def poll_mentions_once():
    character, x_info = get_character()
    api = XAPI()
    since_id = get_state(STATE_KEY_LAST_MENTION)
    payload = api.get_mentions(str(x_info["id"]), since_id=since_id)
    return ingest_v2_mentions_payload(payload, source="poll")
