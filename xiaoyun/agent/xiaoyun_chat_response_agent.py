# -*- coding: utf-8 -*-
#
# xiaoyun 的回复生成 agent。栈换成 OpenAICompatibleLLMAgent；prompt 来自 skill（与 qiaoyun 一致）；
# output_schema 与 _posthandle（关系数值更新 + 未来主动消息预订）直接复用 qiaoyun —— 保证
# 「关系推进口径」与 qiaoyun 逐位一致（A/B 有效性的硬约束）。

import sys
sys.path.append(".")

from framework.agent.llmagent.openai_compatible_llmagent import (
    OpenAICompatibleLLMAgent, default_openai_compatible_client,
)
from qiaoyun.agent.qiaoyun_chat_response_agent import QiaoyunChatResponseAgent
from xiaoyun.skills.library import chat_response_system, chat_response_userp

_DEFAULT = object()


class XiaoyunChatResponseAgent(OpenAICompatibleLLMAgent):
    default_systemp_template = chat_response_system()
    default_userp_template = chat_response_userp()
    default_output_schema = QiaoyunChatResponseAgent.default_output_schema

    # 复用 qiaoyun 的关系口径（按引用复用，自动跟随 qiaoyun 的当前实现）
    _posthandle = QiaoyunChatResponseAgent._posthandle

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
