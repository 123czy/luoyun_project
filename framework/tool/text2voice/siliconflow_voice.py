# -*- coding: utf-8 -*-
#
# 新角色(treatment)的语音封装，契约与 qiaoyun/tool/voice.py 的 qiaoyun_voice 一致：
#   siliconflow_voice(text, emotion) -> [(url, voice_length_ms), ...]
# 因此可在新角色的 handler 里直接替换调用点，下游 send 逻辑无需改动。
#
# 与 qiaoyun_voice 的差异：
#   - 走硅基流动 TTS（CosyVoice2），不走 MiniMax。
#   - 输出 wav（X 场景不需要微信的 silk），用 stdlib wave 精确算时长，免 ffmpeg。
#   - emotion 为尽力而为（CosyVoice 该端点无结构化情绪），保留入参以兼容接口。

import io
import sys
sys.path.append(".")
import time
import wave
import logging
from logging import getLogger
logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)

from framework.tool.text2voice.siliconflow_tts import siliconflow_t2a

# 中文情绪 -> 标签（当前 CosyVoice 端点不消费，仅保留以兼容接口/未来按情绪选音色）
EMOTION_MAP = {
    "高兴": "happy", "悲伤": "sad", "愤怒": "angry", "害怕": "fearful",
    "惊讶": "surprised", "厌恶": "disgusted", "魅惑": "fearful",
}


def _wav_duration_ms(audio_bytes: bytes) -> int:
    """用标准库解析 wav 时长（毫秒）。失败则按中文语速粗估，保证不抛。"""
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate > 0:
                return int(frames / rate * 1000)
    except Exception as e:
        logger.warning(f"wav duration parse failed, fallback to estimate: {e}")
    return 0


def _upload_wav(audio_bytes: bytes) -> str:
    """上传到 OSS 并返回签名 URL。延迟导入 oss，避免无 OSS 配置时影响 import/单测。"""
    from util.oss import upload_file, bucket
    key = str(int(time.time() * 1000)) + ".wav"
    upload_file(bucket, key, audio_bytes)
    return bucket.sign_url("GET", key, 60 * 60)


def siliconflow_voice_single(text: str, emotion: str = None, voice: str = None):
    audio = siliconflow_t2a(text, voice=voice)
    voice_length = _wav_duration_ms(audio)
    if voice_length == 0:
        # 兜底估算：中文约 4 字/秒
        voice_length = max(1000, int(len(text) / 4 * 1000))
    url = _upload_wav(audio)
    return url, voice_length


def siliconflow_voice(text: str, emotion: str = None, voice: str = None):
    # 情绪映射（尽力而为）
    emotion = EMOTION_MAP.get(emotion)  # 未命中 -> None

    results = []
    text = text.replace("<换行>", "")
    for chunk in split_string(text):
        if not chunk.strip():
            continue
        url, voice_length = siliconflow_voice_single(chunk, emotion=emotion, voice=voice)
        results.append((url, voice_length))
        logger.info("voice url: " + url + " | length(ms): " + str(voice_length))
    return results


def split_string(text, chunk_size=420):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
