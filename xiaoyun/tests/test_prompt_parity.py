# -*- coding: utf-8 -*-
#
# Parity 闸门：证明 xiaoyun（skill 组装 + 现代栈）的 prompt 与 qiaoyun（巨型字符串）逐字一致，
# 且 output_schema / _posthandle 为复用（同一对象）。任一不符即 A/B 不再「只比栈」。
#
# 运行：python xiaoyun/tests/test_prompt_parity.py
# （本地用桩替掉未安装的 volcenginesdkarkruntime / dashscope，纯字符串比对，无需网络/Mongo）

import sys
import types
sys.path.append(".")

# --- 本地桩：让 qiaoyun 的 import 链在无 SDK 环境下也能加载 ---
if "volcenginesdkarkruntime" not in sys.modules:
    m = types.ModuleType("volcenginesdkarkruntime")
    m.Ark = lambda *a, **k: object()
    sys.modules["volcenginesdkarkruntime"] = m
if "dashscope" not in sys.modules:
    d = types.ModuleType("dashscope")
    d.TextEmbedding = object()
    sys.modules["dashscope"] = d

from qiaoyun.agent.qiaoyun_query_rewrite_agent import QiaoyunQueryRewriteAgent
from qiaoyun.agent.qiaoyun_chat_response_agent import QiaoyunChatResponseAgent
from qiaoyun.agent.qiaoyun_chat_response_refine_agent import QiaoyunChatResponseRefineAgent
from qiaoyun.agent.qiaoyun_post_analyze_agent import QiaoyunPostAnalyzeAgent

from xiaoyun.agent.xiaoyun_query_rewrite_agent import XiaoyunQueryRewriteAgent
from xiaoyun.agent.xiaoyun_chat_response_agent import XiaoyunChatResponseAgent
from xiaoyun.agent.xiaoyun_chat_response_refine_agent import XiaoyunChatResponseRefineAgent
from xiaoyun.agent.xiaoyun_post_analyze_agent import XiaoyunPostAnalyzeAgent

import inspect

# posthandle_mode:
#   "none"  -> 无自定义 _posthandle
#   "reuse" -> 直接复用 qiaoyun 的 _posthandle（同一对象）
#   "wrap"  -> 包一层（pin bge-m3 写入），但内部委托 qiaoyun 的 _posthandle（关系口径不变）
PAIRS = [
    ("query_rewrite", QiaoyunQueryRewriteAgent, XiaoyunQueryRewriteAgent, "none"),
    ("chat_response", QiaoyunChatResponseAgent, XiaoyunChatResponseAgent, "reuse"),
    ("refine",        QiaoyunChatResponseRefineAgent, XiaoyunChatResponseRefineAgent, "reuse"),
    ("post_analyze",  QiaoyunPostAnalyzeAgent, XiaoyunPostAnalyzeAgent, "wrap"),
]


def main():
    failures = 0
    for name, Q, X, mode in PAIRS:
        # 1. system prompt 逐字一致
        assert X.default_systemp_template == Q.default_systemp_template, f"[{name}] system prompt 不一致"
        # 2. user prompt 逐字一致
        if X.default_userp_template != Q.default_userp_template:
            failures += 1
            print(f"[{name}] ❌ user prompt 不一致")
            # 定位首个差异
            a, b = Q.default_userp_template, X.default_userp_template
            for i, (ca, cb) in enumerate(zip(a, b)):
                if ca != cb:
                    print(f"    首个差异 @ {i}: qiaoyun={ca!r} xiaoyun={cb!r}")
                    print(f"    qiaoyun ...{a[max(0,i-30):i+10]!r}")
                    print(f"    xiaoyun ...{b[max(0,i-30):i+10]!r}")
                    break
            else:
                print(f"    长度不同: qiaoyun={len(a)} xiaoyun={len(b)}")
            continue
        # 3. output_schema 复用（同一对象）
        assert X.default_output_schema is Q.default_output_schema, f"[{name}] output_schema 未复用"
        # 4. _posthandle 关系口径一致
        if mode == "reuse":
            assert X.__dict__["_posthandle"] is Q.__dict__["_posthandle"], f"[{name}] _posthandle 未复用"
            note = "_posthandle 复用"
        elif mode == "wrap":
            # 包装版：必须委托回 qiaoyun 的 _posthandle（关系口径不变），仅 pin 了 embedding
            assert X.__dict__["_posthandle"] is not Q.__dict__["_posthandle"], f"[{name}] 期望包装版"
            src = inspect.getsource(X.__dict__["_posthandle"])
            assert f"{Q.__name__}._posthandle" in src, f"[{name}] 包装未委托 qiaoyun._posthandle"
            note = "_posthandle 包装(pin bge-m3)+委托 qiaoyun 口径"
        else:
            note = "无自定义 _posthandle"
        print(f"[{name}] ✅ system/user prompt 逐字一致 + schema 复用 + {note}")

    if failures:
        print(f"\n❌ {failures} 个 agent prompt 不一致")
        sys.exit(1)
    print("\n✅ 全部 parity 通过：xiaoyun 与 qiaoyun 人设逐字一致，仅底层栈不同。")


if __name__ == "__main__":
    main()
