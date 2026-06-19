# -*- coding: utf-8 -*-
#
# 新角色(treatment)用的 embedding：走 OpenAI 兼容的 /v1/embeddings，默认硅基流动 BGE-M3。
#
# 与 qiaoyun 用的 util/embedding_util.embedding_by_aliyun 平行存在、互不影响：
#   - qiaoyun 继续用阿里 text-embedding-v3（1024 维），冻结不动。
#   - 新角色用本模块（BGE-M3 1024 维 / 可选 Qwen3-Embedding 更高维）。
#
# 重要不变量：同一套数据的「写入」与「检索」必须用同一个模型/维度。
# 新角色的写入和检索都应调用本模块，不要和 aliyun 那套混用。
#
# 更高维选项：把 conf.embedding.model 换成 "Qwen/Qwen3-Embedding-8B"（4096 维）即可，
# 无需改任何 schema —— 当前检索是 Python 暴力余弦(dao/mongo.py vector_search)，维度无关。

import sys
sys.path.append(".")

import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from typing import List, Union

from conf.config import CONF
from framework.agent.llmagent.openai_compatible_llmagent import build_openai_compatible_client

# 复用 LLM 那套 OpenAI 兼容客户端构造（同 base_url / 同 key / import 安全）
_client = build_openai_compatible_client()


def _default_model() -> str:
    return (CONF.get("embedding", {}) or {}).get("model", "BAAI/bge-m3")


def embedding_by_openai_compatible(text: Union[str, List[str]], model: str = None) -> List[float]:
    """
    返回单条文本的 embedding 向量（List[float]）。
    与 embedding_by_aliyun 的签名/返回保持一致，便于新角色直接替换调用点。
    """
    model = model or _default_model()
    resp = _client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


def embedding_batch(texts: List[str], model: str = None) -> List[List[float]]:
    """批量 embedding，返回与输入等长的向量列表。"""
    model = model or _default_model()
    resp = _client.embeddings.create(model=model, input=texts)
    # 按 index 排序，保证与输入顺序对齐
    ordered = sorted(resp.data, key=lambda d: d.index)
    return [d.embedding for d in ordered]


if __name__ == "__main__":
    # 冒烟测试：export SILICONFLOW_API_KEY 后运行
    vec = embedding_by_openai_compatible("你好，我是一个虚拟人。")
    print("model:", _default_model())
    print("dim:", len(vec))
