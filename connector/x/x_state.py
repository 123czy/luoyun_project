# -*- coding: utf-8 -*-
import sys

sys.path.append(".")

from dao.mongo import MongoDBBase

COLLECTION = "connector_state"


def get_state(key, default=None):
    mongo = MongoDBBase()
    doc = mongo.find_one(COLLECTION, {"_id": key})
    if not doc:
        return default
    return doc.get("value", default)


def set_state(key, value):
    mongo = MongoDBBase()
    mongo.get_collection(COLLECTION).update_one(
        {"_id": key},
        {"$set": {"value": value}},
        upsert=True,
    )
