# -*- coding: utf-8 -*-
#
# 硅基流动 TTS 提供方调用（新角色 treatment 用），与 minimax.py 平行存在、互不影响。
# 走 OpenAI 兼容的 /v1/audio/speech，默认 CosyVoice2。
#
# 说明（诚实标注）：CosyVoice 在该端点没有 MiniMax 那种结构化 emotion 参数，
# 情绪控制弱于 MiniMax —— 这是「换 TTS 声音人设会变」的已知代价。

import sys
sys.path.append(".")

import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from conf.config import CONF
from framework.agent.llmagent.openai_compatible_llmagent import build_openai_compatible_client

_client = build_openai_compatible_client()


def _tts_conf() -> dict:
    return CONF.get("tts", {}) or {}


def siliconflow_t2a(text: str, voice: str = None, model: str = None,
                    speed: float = None, response_format: str = None) -> bytes:
    """
    文本 -> 音频字节。返回原始音频字节（默认 wav，含头）。
    """
    conf = _tts_conf()
    model = model or conf.get("model", "FunAudioLLM/CosyVoice2-0.5B")
    voice = voice or conf.get("voice", "FunAudioLLM/CosyVoice2-0.5B:anna")
    speed = speed if speed is not None else conf.get("speed", 1.0)
    response_format = response_format or conf.get("response_format", "wav")

    resp = _client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        response_format=response_format,
        speed=speed,
    )
    # openai SDK 的二进制响应：优先 .read()，兜底 .content
    if hasattr(resp, "read"):
        return resp.read()
    return resp.content


if __name__ == "__main__":
    # 冒烟测试：export SILICONFLOW_API_KEY 后运行
    audio = siliconflow_t2a("你好，我是新角色，很高兴认识你。")
    with open("framework/tool/text2voice/test_siliconflow.wav", "wb") as f:
        f.write(audio)
    print("bytes:", len(audio))
