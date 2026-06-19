# -*- coding: utf-8 -*-
import os
import time

import sys

sys.path.append(".")

import traceback
import logging
from logging import getLogger

logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)
import json

from dao.mongo import MongoDBBase
from dao.user_dao import UserDAO

from_user = "6a351445e22f44907b2c5608"
to_user = "6a3512571b8e2234800ce918"


mongo = MongoDBBase()
user_dao = UserDAO()
user = user_dao.get_user_by_id(from_user)
user_name = user["platforms"]["wechat"]["nickname"]

while True:
    input_text = input(user_name + "：")
    now = int(time.time())
    message = {
        "input_timestamp": now,  # 输入时的时间戳秒级
        "handled_timestamp": now,  # 处理完毕时的时间戳秒级
        "status": "pending",  # 标记处理状态：pending待处理，handled处理完毕，canceled不处理，failed处理失败
        "from_user": from_user,  # 来源uid
        "platform": "wechat",  # 来源平台
        "chatroom_name": None,  # 如果有值，则来自群聊；否则是私聊
        "to_user": to_user,  # 目标用户；群聊时，值为None
        "message_type": "text",  # 包括：
        "message": input_text,  # 实际消息，格式另行约定
        "metadata": {},
    }

    id = mongo.insert_one("inputmessages", message)
    print("sent.")
