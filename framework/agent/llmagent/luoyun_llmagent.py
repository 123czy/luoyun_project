# -*- coding: utf-8 -*-
#
# qiaoyun 统一 LLM 入口：按 conf.llm.provider 在火山方舟与 OpenAI 兼容服务之间切换。
#
#   - ark               → DouBaoLLMAgent + doubao_models（ep-xxxx），需 ARK_API_KEY
#   - openai_compatible → OpenAICompatibleLLMAgent + siliconflow_models，需 SILICONFLOW_API_KEY
#
# 业务别名（doubao_1.5_pro / deepseek_v3.1 等）在各 Agent 中保持不变。

import sys
sys.path.append(".")

from conf.config import CONF
from framework.agent.llmagent.doubao_llmagent import DouBaoLLMAgent, doubao_client
from framework.agent.llmagent.openai_compatible_llmagent import (
    OpenAICompatibleLLMAgent,
    default_openai_compatible_client,
)

_VALID_PROVIDERS = ("ark", "openai_compatible")


def get_llm_provider() -> str:
    provider = (CONF.get("llm", {}) or {}).get("provider", "ark")
    if provider not in _VALID_PROVIDERS:
        raise ValueError(
            f"Invalid conf.llm.provider={provider!r}; expected one of {_VALID_PROVIDERS}"
        )
    return provider


def get_default_llm_client():
    if get_llm_provider() == "openai_compatible":
        return default_openai_compatible_client
    return doubao_client


def get_llm_agent_class():
    if get_llm_provider() == "openai_compatible":
        return OpenAICompatibleLLMAgent
    return DouBaoLLMAgent


LuoyunLLMAgent = get_llm_agent_class()
default_llm_client = get_default_llm_client()
