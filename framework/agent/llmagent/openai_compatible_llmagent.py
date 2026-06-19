# -*- coding: utf-8 -*-
#
# 通用 OpenAI 兼容大模型 Agent。
# 与 DouBaoLLMAgent 等价，但走标准 OpenAI Python SDK，默认对接硅基流动(SiliconFlow)
# 的 API 聚合服务（base_url=https://api.siliconflow.cn/v1）。
#
# 设计目标（见 docs/model_trans.md）：
#   - 保留现有业务别名（doubao_1.5_pro / deepseek_v3.1 / deepseek_r1 / doubao_1.6_pro），
#     只把别名映射到 OpenAI 兼容服务的真实模型 ID（CONF["siliconflow_models"]）。
#   - 不影响现有功能：qiaoyun agent 通过 luoyun_llmagent 按 conf.llm.provider 切换本类或 DouBaoLLMAgent。
#
# 用法：qiaoyun agent 统一 from framework.agent.llmagent.luoyun_llmagent import LuoyunLLMAgent
# 即可，其余参数（systemp/userp/output_schema/model 别名）保持不变。
#
# 环境变量：export SILICONFLOW_API_KEY="sk-xxxx"
#   （也可在 conf/config.json 的 openai_compatible.api_key 直接填，env 优先）

import os
import sys
sys.path.append(".")

import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from openai import OpenAI
from framework.agent.llmagent.base_singleroundllmagent import BaseSingleRoundLLMAgent
from conf.config import CONF


def _provider_conf() -> dict:
    return CONF.get("openai_compatible", {}) or {}


def build_openai_compatible_client(base_url: str = None, api_key: str = None, api_key_env: str = None) -> OpenAI:
    """根据配置/环境变量构造一个 OpenAI 兼容客户端（默认指向硅基流动）。"""
    conf = _provider_conf()
    base_url = base_url or conf.get("base_url", "https://api.siliconflow.cn/v1")
    if api_key is None:
        env_name = api_key_env or conf.get("api_key_env", "SILICONFLOW_API_KEY")
        api_key = os.getenv(env_name) or conf.get("api_key") or None
    if not api_key:
        # 占位 key，保证 import 不崩；真正发起请求时若 key 缺失会返回明确的鉴权错误。
        logger.warning(
            "OpenAI-compatible api_key not configured "
            "(set env SILICONFLOW_API_KEY or conf.openai_compatible.api_key). "
            "Client built with a placeholder; live calls will fail until a key is provided."
        )
        api_key = "EMPTY"
    return OpenAI(base_url=base_url, api_key=api_key)


# 模块级默认客户端，复用连接，行为与 doubao_client 对齐
default_openai_compatible_client = build_openai_compatible_client()


class OpenAICompatibleLLMAgent(BaseSingleRoundLLMAgent):
    """单轮 OpenAI 兼容大模型 Agent，默认对接硅基流动。"""

    # 业务别名 -> 真实模型 ID 的映射表所在的 CONF key
    model_alias_conf_key = "siliconflow_models"

    def __init__(
        self,
        context=None,
        client=default_openai_compatible_client,
        systemp_template="",
        userp_template="",
        output_schema=None,
        default_input=None,
        max_retries=3,
        name=None,
        stream=False,
        model="doubao_1.5_pro",
        extra_args=None,
    ):
        super().__init__(
            context, client, systemp_template, userp_template, output_schema,
            default_input, max_retries, name, stream, model, extra_args,
        )
        # 保留业务别名：把别名映射到 OpenAI 兼容服务的真实模型 ID
        alias_map = CONF.get(self.model_alias_conf_key, {}) or {}
        if model in alias_map:
            self.model = alias_map[model]


# 简单冒烟测试：export SILICONFLOW_API_KEY 后运行
#   python framework/agent/llmagent/openai_compatible_llmagent.py
if __name__ == "__main__":
    context = {}
    c = OpenAICompatibleLLMAgent(
        context,
        userp_template="{input}",
        default_input={"input": "你好，请用一句话自我介绍。"},
        model="doubao_1.5_pro",
    )
    for response in c.run():
        print(response)
