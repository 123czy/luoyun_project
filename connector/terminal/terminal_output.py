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
from bson import ObjectId

from dao.mongo import MongoDBBase
from dao.user_dao import UserDAO
from entity.message import save_outputmessage

from_user = "6a3512571b8e2234800ce918"
to_user = "6a351445e22f44907b2c5608"

mongo = MongoDBBase()
user_dao = UserDAO()
user = user_dao.get_user_by_id(from_user)
user_name = user["platforms"]["wechat"]["nickname"]

while True:
    time.sleep(1)
    now = int(time.time())
    message = mongo.find_one(
        "outputmessages",
        {
            "platform": "wechat",
            "from_user": from_user,
            "to_user": to_user,
            "status": "pending",
            "expect_output_timestamp": {"$lt": now},  # 预期输出的时间戳秒级
        },
    )

    if message is None:
        continue

    now = int(time.time())
    print(user_name + "：" + message["message"])
    print()

    message["status"] = "handled"
    message["handled_timestamp"] = now

    save_outputmessage(message)
