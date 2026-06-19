# -*- coding: utf-8 -*-
#
# xiaoyun 的问题重写 agent。
# 与 qiaoyun 的差异仅在「栈」：显式走 OpenAICompatibleLLMAgent（不走全局 LuoyunLLMAgent 开关），
# prompt 来自 skill 组装（与 qiaoyun 逐字一致），output_schema 直接复用 qiaoyun（保证一致）。

import sys
sys.path.append(".")

from framework.agent.llmagent.openai_compatible_llmagent import (
    OpenAICompatibleLLMAgent, default_openai_compatible_client,
)
from qiaoyun.agent.qiaoyun_query_rewrite_agent import QiaoyunQueryRewriteAgent
from xiaoyun.skills.library import query_rewrite_system, query_rewrite_userp

_DEFAULT = object()  # 哨兵：区分「未传」与「显式传 None」


class XiaoyunQueryRewriteAgent(OpenAICompatibleLLMAgent):
    default_systemp_template = query_rewrite_system()
    default_userp_template = query_rewrite_userp()
    default_output_schema = QiaoyunQueryRewriteAgent.default_output_schema  # 复用，保证一致

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
