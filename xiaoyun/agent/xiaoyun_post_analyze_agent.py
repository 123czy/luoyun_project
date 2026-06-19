# -*- coding: utf-8 -*-
#
# xiaoyun 的对话后分析 agent（总结 → 写入记忆 + 更新关系画像）。
# 栈换成 OpenAICompatibleLLMAgent；prompt 来自 skill（与 qiaoyun 一致）；output_schema 复用 qiaoyun。
#
# 关于 _posthandle：
#   - 关系口径（realname/hobbyname/description/purpose/attitude/dislike 的更新逻辑）必须与 qiaoyun
#     **逐位一致** → 直接复用 qiaoyun 的 _posthandle（按引用），不复制逻辑、不会漂移。
#   - 但记忆写入的 embedding 必须 **pin 成 bge-m3**（与 xiaoyun 检索侧同空间），独立于全局
#     conf.embedding.provider。做法：在调用 qiaoyun 的 _posthandle 期间，临时把
#     util.embedding_util.embedding 覆盖成 bge-m3，调用结束即还原（同步执行，事件循环内原子，安全）。

import sys
sys.path.append(".")

import util.embedding_util as _eu
from framework.agent.llmagent.openai_compatible_llmagent import (
    OpenAICompatibleLLMAgent, default_openai_compatible_client,
)
from framework.tool.embedding.openai_compatible_embedding import embedding_by_openai_compatible
from qiaoyun.agent.qiaoyun_post_analyze_agent import QiaoyunPostAnalyzeAgent
from xiaoyun.skills.library import post_analyze_system, post_analyze_userp

_DEFAULT = object()


def _bge_embedding(text, model=None):
    """pin 到 openai_compatible(bge-m3)，与 xiaoyun 检索侧同模型同维度。"""
    return embedding_by_openai_compatible(text, model=model)


class XiaoyunPostAnalyzeAgent(OpenAICompatibleLLMAgent):
    default_systemp_template = post_analyze_system()
    default_userp_template = post_analyze_userp()
    default_output_schema = QiaoyunPostAnalyzeAgent.default_output_schema

    def __init__(self, context=None, client=default_openai_compatible_client,
                 systemp_template=None, userp_template=None, output_schema=_DEFAULT,
                 default_input=None, max_retries=3, name=None, stream=False,
                 model="doubao_1.5_pro", extra_args=None):
        super().__init__(
            context, client,
            systemp_template if systemp_template is not None else self.default_systemp_template,
            userp_template if userp_template is not None else self.default_userp_template,
            self.default_output_schema if output_schema is _DEFAULT else output_schema,
            default_input, max_retries, name, stream, model, extra_args,
        )

    def _posthandle(self):
        # 复用 qiaoyun 的 _posthandle（关系口径逐位一致），但记忆写入 pin 成 bge-m3
        original = _eu.embedding
        _eu.embedding = _bge_embedding
        try:
            QiaoyunPostAnalyzeAgent._posthandle(self)
        finally:
            _eu.embedding = original
