# -*- coding: utf-8 -*-
#
# 新角色(treatment)用的 reranker：硅基流动 /v1/rerank（BGE-reranker-v2-m3）。
#
# 作用：替代当前 qiaoyun 召回里手调权重(0.3/0.7 + key/value 双路 merge)的打分方式。
# 用法（新角色检索流程里）：
#   1. 先用向量/关键词粗召回一批候选（保留 luoyun 多路召回的「广撒网」）；
#   2. 把候选文本丢给 rerank()，按 relevance_score 取 top_n —— 免手调参，质量更高。
#
# 注意：/v1/rerank 不在 OpenAI SDK 里，是独立 HTTP 端点，这里用 requests 直连。

import os
import sys
sys.path.append(".")

import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from typing import List, Dict, Any
import requests

from conf.config import CONF


def _provider_conf() -> dict:
    return CONF.get("openai_compatible", {}) or {}


def _resolve_api_key() -> str:
    conf = _provider_conf()
    env_name = conf.get("api_key_env", "SILICONFLOW_API_KEY")
    return os.getenv(env_name) or conf.get("api_key") or ""


def _default_model() -> str:
    return (CONF.get("rerank", {}) or {}).get("model", "BAAI/bge-reranker-v2-m3")


def rerank(query: str, documents: List[str], model: str = None, top_n: int = None) -> List[Dict[str, Any]]:
    """
    对候选文档按与 query 的相关性重排。
    返回: [{"index": 原始下标, "relevance_score": float, "document": {...}|str}, ...]，已按分数降序。
    """
    if not documents:
        return []

    conf = _provider_conf()
    base_url = conf.get("base_url", "https://api.siliconflow.cn/v1").rstrip("/")
    url = base_url + "/rerank"

    body = {
        "model": model or _default_model(),
        "query": query,
        "documents": documents,
        "return_documents": True,
    }
    if top_n is not None:
        body["top_n"] = top_n

    resp = requests.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {_resolve_api_key()}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def rerank_top_n(query: str, documents: List[str], top_n: int, model: str = None) -> List[str]:
    """便捷封装：直接返回重排后 top_n 的文本列表。"""
    results = rerank(query, documents, model=model, top_n=top_n)
    out = []
    for r in results:
        doc = r.get("document")
        out.append(doc.get("text") if isinstance(doc, dict) else (doc if doc is not None else documents[r["index"]]))
    return out


if __name__ == "__main__":
    # 冒烟测试：export SILICONFLOW_API_KEY 后运行
    docs = ["猫是一种宠物", "今天上海下雨", "她喜欢研读犯罪心理学", "精酿啤酒的酿造工艺"]
    print(rerank_top_n("角色的爱好是什么", docs, top_n=2))
