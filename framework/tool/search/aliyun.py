import os
from openai import OpenAI

from conf.config import CONF

_client = None


def is_search_available() -> bool:
    search_conf = CONF.get("search", {}) or {}
    if search_conf.get("enabled") is False:
        return False
    return bool(os.getenv("DASHSCOPE_API_KEY"))


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY is not set (required for aliyun_search / daily news; "
            "main text chat does not need it). Set search.enabled=false in config to skip."
        )
    _client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return _client


def aliyun_search(messages, model="qwq-plus", stream=True, extra_body=None):
    if extra_body is None:
        extra_body = {
            "enable_search": True,
            "search_options": {
                "forced_search": True,
                "enable_source": True,
                "search_strategy": "pro",
            }
        }

    completion = _get_client().chat.completions.create(
        model=model,
        messages=messages,
        stream=stream,
        extra_body=extra_body
    )

    result = ""
    for chunk in completion:
        content = chunk.choices[0].delta.content
        if content is not None:
            result = result + content

    return result
