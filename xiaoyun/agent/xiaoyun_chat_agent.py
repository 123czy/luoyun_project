# -*- coding: utf-8 -*-
#
# xiaoyun 前台对话编排：镜像 QiaoyunChatAgent 的流程，但全部换成现代栈：
#   query_rewrite → ModernContextRetrieveAgent(向量粗召回 + reranker 精排) → response
#   → (按概率) refine → 产出 → post_analyze(写记忆 + 更新关系)
# 编排逻辑（顺序、refine 概率、yield MESSAGE）与 qiaoyun 一致，保证 A/B 只比「栈」。

import sys
sys.path.append(".")
import random
import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from framework.agent.base_agent import AgentStatus, BaseAgent
from framework.agent.retrieve.modern_context_retrieve_agent import ModernContextRetrieveAgent

from xiaoyun.agent.xiaoyun_query_rewrite_agent import XiaoyunQueryRewriteAgent
from xiaoyun.agent.xiaoyun_chat_response_agent import XiaoyunChatResponseAgent
from xiaoyun.agent.xiaoyun_chat_response_refine_agent import XiaoyunChatResponseRefineAgent
from xiaoyun.agent.xiaoyun_post_analyze_agent import XiaoyunPostAnalyzeAgent

# 与 qiaoyun 一致的 refine 触发概率
default_refine_chance = 0.12
refine_chance = 0.5


class XiaoyunChatAgent(BaseAgent):
    def __init__(self, context=None, max_retries=3, name=None):
        super().__init__(context, max_retries, name)

    def _execute(self):
        # 清零
        self.context["conversation"]["conversation_info"]["future"]["proactive_times"] = 0

        # 问题重写
        for result in XiaoyunQueryRewriteAgent(self.context).run():
            if result["status"] != AgentStatus.FINISHED.value:
                continue
            self.context["query_rewrite"] = result["resp"]

        # 上下文拉取（现代检索：粗召回 + reranker）
        for result in ModernContextRetrieveAgent(self.context).run():
            if result["status"] != AgentStatus.FINISHED.value:
                continue
            self.context["context_retrieve"] = result["resp"]

        # 回复生成
        for result in XiaoyunChatResponseAgent(self.context).run():
            if result["status"] != AgentStatus.FINISHED.value:
                continue
            logger.info(result["resp"])
            self.resp = result["resp"]
            self.context["MultiModalResponses"] = result["resp"]["MultiModalResponses"]

        # 按概率走优化链
        is_refine = False
        if random.random() < default_refine_chance:
            is_refine = True
        if "ChatCatelogue" in self.resp:
            if self.resp["ChatCatelogue"] == "是" and random.random() < refine_chance:
                is_refine = True

        if is_refine:
            logger.info("refining...")
            for result in XiaoyunChatResponseRefineAgent(self.context).run():
                if result["status"] != AgentStatus.FINISHED.value:
                    continue
                logger.info(result["resp"])
                self.resp["MultiModalResponses"] = result["resp"]
                self.context["MultiModalResponses"] = result["resp"]

        self.status = AgentStatus.MESSAGE
        yield self.resp
        self.status = AgentStatus.RUNNING

        # 对话后分析（写记忆 + 更新关系）
        for result in XiaoyunPostAnalyzeAgent(self.context).run():
            if result["status"] != AgentStatus.FINISHED.value:
                continue
            logger.info(result["resp"])
