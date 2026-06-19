# -*- coding: utf-8 -*-
#
# xiaoyun 的回复优化(refine)链。栈换成 OpenAICompatibleLLMAgent；prompt 来自 skill（与 qiaoyun 一致）；
# output_schema 为 None（与 qiaoyun 一致），_posthandle（解析 r1 输出）复用 qiaoyun。

import sys
sys.path.append(".")

from framework.agent.llmagent.openai_compatible_llmagent import (
    OpenAICompatibleLLMAgent, default_openai_compatible_client,
)
from qiaoyun.agent.qiaoyun_chat_response_refine_agent import QiaoyunChatResponseRefineAgent
from xiaoyun.skills.library import refine_system, refine_userp

_DEFAULT = object()


class XiaoyunChatResponseRefineAgent(OpenAICompatibleLLMAgent):
    default_systemp_template = refine_system()
    default_userp_template = refine_userp()
    default_output_schema = QiaoyunChatResponseRefineAgent.default_output_schema  # None

    _posthandle = QiaoyunChatResponseRefineAgent._posthandle

    def __init__(self, context=None, client=default_openai_compatible_client,
                 systemp_template=None, userp_template=None, output_schema=_DEFAULT,
                 default_input=None, max_retries=3, name=None, stream=False,
                 model="deepseek_v3.1", extra_args=None):
        super().__init__(
            context, client,
            systemp_template if systemp_template is not None else self.default_systemp_template,
            userp_template if userp_template is not None else self.default_userp_template,
            self.default_output_schema if output_schema is _DEFAULT else output_schema,
            default_input, max_retries, name, stream, model, extra_args,
        )
