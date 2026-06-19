# -*- coding: utf-8 -*-
#
# 初始化 xiaoyun 角色（与 qiaoyun 同库 mymongo，靠独立 cid 隔离，不新建数据库）。
#
# 做三件事（幂等）：
#   1. 克隆 qiaoyun 的角色记录 → 新建 xiaoyun（新的 _id；人设字段 nickname/user_info/status 保持一致，
#      只改身份字段 platform id，保证「人设完全一致」+「身份独立」）。
#   2. 把 qiaoyun 的人设 embedding（character_global/photo/private/knowledge/user）按原文 key/value
#      用 **bge-m3** 重新生成，写到 xiaoyun 的 cid 下 —— 保证 xiaoyun 检索/写入在同一向量空间。
#   3. 把 xiaoyun 的 cid 写回 conf/config.json（characters.xiaoyun / aliyun.characters.xiaoyun）。
#
# 用法：
#   export SILICONFLOW_API_KEY=sk-xxx
#   python xiaoyun/role/seed_xiaoyun.py                 # 建角色 + 重算 embedding + 写 config
#   python xiaoyun/role/seed_xiaoyun.py --skip-embeddings   # 只建角色 + 写 config（无需 API key）

import sys
sys.path.append(".")
import json
import copy
import argparse

from pymongo import MongoClient
from bson import ObjectId

from conf.config import CONF

# qiaoyun 角色 cid（人设来源）。如有变化，改这里。
QIAOYUN_CID = "6a3512571b8e2234800ce918"
CONFIG_PATH = "conf/config.json"


def _db():
    uri = "mongodb://%s:%s/" % (CONF["mongodb"]["mongodb_ip"], CONF["mongodb"]["mongodb_port"])
    return MongoClient(uri)[CONF["mongodb"]["mongodb_name"]]


def ensure_character(db) -> str:
    existing = db["users"].find_one({"name": "xiaoyun"})
    if existing:
        print("xiaoyun 角色已存在，复用：", existing["_id"])
        return str(existing["_id"])

    q = db["users"].find_one({"_id": ObjectId(QIAOYUN_CID)})
    if not q:
        raise SystemExit("找不到 qiaoyun 角色记录 cid=%s，请先确认 qiaoyun 已初始化。" % QIAOYUN_CID)

    x = copy.deepcopy(q)
    x.pop("_id", None)
    x["name"] = "xiaoyun"
    # 仅改身份字段，人设字段（nickname / user_info / status）保持与 qiaoyun 一致
    x.setdefault("platforms", {}).setdefault("wechat", {})
    x["platforms"]["wechat"]["id"] = "xiaoyun_wechat_id"
    x["platforms"]["wechat"]["account"] = "xiaoyun_account"
    if "x" in x["platforms"]:
        # X 账号留占位，等你填真实账号
        x["platforms"]["x"] = {
            "id": "xiaoyun_x_id",
            "account": "xiaoyun_x_account",
            "nickname": x["platforms"]["x"].get("nickname", ""),
        }
    new_id = db["users"].insert_one(x).inserted_id
    print("已创建 xiaoyun 角色：", new_id)
    return str(new_id)


def reseed_embeddings(db, xcid: str):
    from framework.tool.embedding.openai_compatible_embedding import embedding_by_openai_compatible

    db["embeddings"].delete_many({"metadata.cid": xcid})  # 幂等
    src = list(db["embeddings"].find({"metadata.cid": QIAOYUN_CID}))
    print("用 bge-m3 重算 %d 条人设 embedding..." % len(src))
    n = 0
    for d in src:
        md = dict(d.get("metadata") or {})
        md["cid"] = xcid
        doc = {
            "key": d["key"],
            "value": d["value"],
            "key_embedding": embedding_by_openai_compatible(d["key"]),
            "value_embedding": embedding_by_openai_compatible(d["value"]),
            "metadata": md,
        }
        db["embeddings"].insert_one(doc)
        n += 1
        if n % 20 == 0:
            print("  ...", n)
    print("完成，共写入 %d 条 xiaoyun embedding（cid=%s）" % (n, xcid))


def write_config_cid(xcid: str):
    c = json.load(open(CONFIG_PATH, encoding="utf-8"))
    c.setdefault("characters", {})["xiaoyun"] = xcid          # 兼容 runner: CONF["characters"]
    c.setdefault("aliyun", {}).setdefault("characters", {})["xiaoyun"] = xcid
    json.dump(c, open(CONFIG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
    print("已写入 config：characters.xiaoyun = aliyun.characters.xiaoyun =", xcid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-embeddings", action="store_true", help="只建角色+写config，不重算 embedding")
    args = ap.parse_args()

    db = _db()
    xcid = ensure_character(db)
    write_config_cid(xcid)
    if args.skip_embeddings:
        print("已跳过 embedding 重算。需要时运行：python xiaoyun/role/seed_xiaoyun.py（带 SILICONFLOW_API_KEY）")
    else:
        reseed_embeddings(db, xcid)
    print("xiaoyun 初始化完成。cid =", xcid)


if __name__ == "__main__":
    main()
