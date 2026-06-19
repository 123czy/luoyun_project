# -*- coding: utf-8 -*-
#
# 现代检索 Agent（新角色 treatment 用，角色无关、可复用）。
#
# 与 qiaoyun/agent/qiaoyun_context_retrieve_agent.py 对比：
#   - 保留：多路「粗召回」——向量(key/value 双 embedding) + 关键词精确匹配，广撒网。
#   - 替换：手调权重(0.3/0.7/bar_min/bar_max)的合并 + 按权重 top_n
#            → 统一交给 reranker 精排（relevance_score 排序），免调参、召回质量更高。
#   - embedding：用 openai_compatible(BGE-M3/Qwen3)，与新角色写入侧同模型同维度。
#
# 返回结构与旧版逐键一致（character_global/character_private/user/character_knowledge/
# character_photo），下游 chat agent 无需改动即可使用。
#
# 重要：本 agent 检索的 embeddings 必须是用同一个 openai_compatible 模型写入的。
# 不要和 qiaoyun 那套(阿里 text-embedding-v3)混用同一批数据。

import sys
sys.path.append(".")

import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from typing import List, Dict, Any

from framework.agent.base_agent import AgentStatus, BaseAgent
from dao.mongo import MongoDBBase
from framework.tool.embedding.openai_compatible_embedding import embedding_by_openai_compatible
from framework.tool.rerank.openai_compatible_rerank import rerank

# 每路向量召回数 / 每个关键词召回数 / 精排后保留数
VECTOR_TOP_K = 8
KEYWORD_LIMIT = 5
RERANK_TOP_N = 6
# 进入 reranker 前的候选上限，控制成本
MAX_CANDIDATES = 50


class ModernContextRetrieveAgent(BaseAgent):
    def __init__(self, context=None, max_retries=3, name=None):
        super().__init__(context, max_retries, name)

    def _execute(self):
        mongo = MongoDBBase()
        q = self.context["query_rewrite"]
        cid = str(self.context["character"]["_id"])
        uid = str(self.context["user"]["_id"])

        return_resp = {
            "character_global": "",
            "character_private": "",
            "user": "",
            "character_knowledge": "",
            "character_photo": "",
        }

        # 角色全局人设（与个人设定共用 CharacterSetting 查询）
        return_resp["character_global"] = self._retrieve_one(
            mongo,
            question=q["CharacterSettingQueryQuestion"],
            keywords=q["CharacterSettingQueryKeywords"],
            metadata_filters={"type": "character_global", "cid": cid},
        )

        # 角色对该用户的个人设定
        return_resp["character_private"] = self._retrieve_one(
            mongo,
            question=q["CharacterSettingQueryQuestion"],
            keywords=q["CharacterSettingQueryKeywords"],
            metadata_filters={"type": "character_private", "cid": cid, "uid": uid},
        )

        # 用户画像
        return_resp["user"] = self._retrieve_one(
            mongo,
            question=q["UserProfileQueryQuestion"],
            keywords=q["UserProfileQueryKeywords"],
            metadata_filters={"type": "user", "cid": cid, "uid": uid},
        )

        # 角色知识/技能
        return_resp["character_knowledge"] = self._retrieve_one(
            mongo,
            question=q["CharacterKnowledgeQueryQuestion"],
            keywords=q["CharacterKnowledgeQueryKeywords"],
            metadata_filters={"type": "character_knowledge", "cid": cid},
        )

        # 角色相册（带频度惩罚 + 照片前缀）
        return_resp["character_photo"] = self._retrieve_one(
            mongo,
            question=q["CharacterPhotoQueryQuestion"],
            keywords=q["CharacterPhotoQueryKeywords"],
            metadata_filters={"type": "character_photo", "cid": cid},
            photo_prefix=True,
            exclude_ids=self.context["conversation"]["conversation_info"].get("photo_history", []),
        )

        yield return_resp

    # ---- 核心：单一类型的「粗召回 → reranker 精排」 ----
    def _retrieve_one(self, mongo, question, keywords, metadata_filters,
                      photo_prefix=False, exclude_ids=None) -> str:
        if question == "空":
            return ""

        candidates = self._recall(mongo, question, keywords, metadata_filters)

        # 频度惩罚：过滤近期已用过的照片
        if exclude_ids:
            exclude = set(str(x) for x in exclude_ids)
            candidates = [c for c in candidates if str(c["_id"]) not in exclude]

        return self._rerank_topn(question, candidates, RERANK_TOP_N, photo_prefix=photo_prefix)

    def _recall(self, mongo, question, keywords, metadata_filters) -> List[Dict[str, Any]]:
        """多路粗召回：向量(key/value) + 关键词(key/value)，按 _id 去重。"""
        candidates: Dict[str, Dict[str, Any]] = {}

        # 1. 向量召回（key_embedding + value_embedding）
        emb = embedding_by_openai_compatible(question)
        for field in ("key_embedding", "value_embedding"):
            for r in mongo.vector_search("embeddings", emb, field, metadata_filters, top_k=VECTOR_TOP_K):
                candidates[str(r["_id"])] = r

        # 2. 关键词精确召回（key + value）
        kw_query_base = {f"metadata.{k}": v for k, v in metadata_filters.items()}
        for keyword in str(keywords).split(","):
            keyword = keyword.strip()
            if not keyword:
                continue
            for field in ("key", "value"):
                q = dict(kw_query_base)
                q[field] = {"$in": [keyword]}
                for r in mongo.find_many("embeddings", q, limit=KEYWORD_LIMIT):
                    candidates[str(r["_id"])] = r

        result = list(candidates.values())
        return result[:MAX_CANDIDATES]

    def _rerank_topn(self, query_text, candidates, n, photo_prefix=False) -> str:
        if not candidates:
            return ""

        docs = [self._format_line(c) for c in candidates]

        try:
            results = rerank(query_text, docs, top_n=n)
            ordered = [candidates[r["index"]] for r in results]
        except Exception as e:
            # reranker 不可用时退化为：向量相似度优先（无相似度的关键词候选排后），不让检索整体失败
            logger.error(f"rerank failed, fallback to similarity order: {e}")
            ordered = sorted(candidates, key=lambda c: c.get("similarity", 0.0), reverse=True)[:n]

        lines = []
        for c in ordered:
            line = self._format_line(c)
            if photo_prefix:
                line = "「照片" + str(c["_id"]) + "」" + line
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _format_line(c) -> str:
        return str(c["key"] + "：" + c["value"]).strip()
