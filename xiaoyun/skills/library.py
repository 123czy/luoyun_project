# -*- coding: utf-8 -*-
#
# xiaoyun 的技能库 + 各 agent 的 prompt 组装。
#
# 关键：每个技能直接引用 qiaoyun 的 prompt 常量（单一来源），组装顺序逐字复刻 qiaoyun 各
# agent 的 default_userp_template，从而保证「人设完全一致」。parity 由 tests 断言守护。

from qiaoyun.prompt.system_prompt import *      # SYSTEMPROMPT_*
from qiaoyun.prompt.chat_taskprompt import *    # TASKPROMPT_*
from qiaoyun.prompt.chat_contextprompt import * # CONTEXTPROMPT_*
from qiaoyun.prompt.chat_noticeprompt import *  # NOTICE_*

from xiaoyun.skills.base import Skill, compose, SkillRegistry

registry = SkillRegistry()


def _s(name, text, desc=""):
    return registry.register(Skill(name, text, desc))


# ---- 系统 / 人设技能 ----
SYS_PERSONA = _s("system.persona", SYSTEMPROMPT_小说越狱, "角色人设 + 越狱系统提示")
SYS_PERSONA_NOJSON = _s("system.persona_nojson", SYSTEMPROMPT_小说越狱_nojson, "无 JSON 版系统提示（优化链用）")

# ---- 任务技能 ----
TASK_NOVEL = _s("task.novel_writing", TASKPROMPT_小说书写任务)
TASK_NOVEL_NOJSON = _s("task.novel_writing_nojson", TASKPROMPT_小说书写任务_nojson)
TASK_SEMANTIC = _s("task.semantic", TASKPROMPT_语义理解)
TASK_SEMANTIC_REQ = _s("task.semantic_req", TASKPROMPT_语义理解_推理要求)
TASK_WECHAT = _s("task.wechat_chat", TASKPROMPT_微信对话)
TASK_WECHAT_REQ_TEXT = _s("task.wechat_chat_req_text", TASKPROMPT_微信对话_推理要求_纯文本)
TASK_WECHAT_REFINE = _s("task.wechat_chat_refine", TASKPROMPT_微信对话_优化)
TASK_SUMMARY = _s("task.summary", TASKPROMPT_总结)
TASK_SUMMARY_REQ = _s("task.summary_req", TASKPROMPT_总结_推理要求)

# ---- 上下文技能 ----
CTX_TIME = _s("context.time", CONTEXTPROMPT_时间)
CTX_NEWS = _s("context.news", CONTEXTPROMPT_新闻)
CTX_CHAR_INFO = _s("context.character_info", CONTEXTPROMPT_人物信息)
CTX_CHAR_PROFILE = _s("context.character_profile", CONTEXTPROMPT_人物资料)
CTX_USER_PROFILE = _s("context.user_profile", CONTEXTPROMPT_用户资料)
CTX_CHAR_KNOWLEDGE = _s("context.character_knowledge", CONTEXTPROMPT_人物知识和技能)
CTX_CHAR_PHOTO = _s("context.character_photo", CONTEXTPROMPT_人物手机相册)
CTX_CHAR_STATUS = _s("context.character_status", CONTEXTPROMPT_人物状态)
CTX_CURRENT_GOAL = _s("context.current_goal", CONTEXTPROMPT_当前目标)
CTX_RELATION = _s("context.relation", CONTEXTPROMPT_当前的人物关系)
CTX_HISTORY = _s("context.history", CONTEXTPROMPT_历史对话)
CTX_LATEST = _s("context.latest_message", CONTEXTPROMPT_最新聊天消息)
CTX_LATEST_BOTH = _s("context.latest_message_both", CONTEXTPROMPT_最新聊天消息_双方)
CTX_DRAFT_REPLY = _s("context.draft_reply", CONTEXTPROMPT_初步回复)

# ---- 注意事项技能 ----
NOTICE_SEGMENT = _s("notice.segmented", NOTICE_常规注意事项_分段消息)
NOTICE_GEN = _s("notice.generation", NOTICE_常规注意事项_生成优化)
NOTICE_EMPTY = _s("notice.empty_input", NOTICE_常规注意事项_空输入处理)
NOTICE_REFINE_GEN = _s("notice.refine_generation", NOTICE_优化注意事项_生成优化)


# ===== 各 agent 的 prompt 组装（顺序逐字复刻 qiaoyun） =====

def query_rewrite_system():
    return compose([SYS_PERSONA])


def query_rewrite_userp():
    return compose([
        "## 你的任务", TASK_NOVEL,
        "", TASK_SEMANTIC, TASK_SEMANTIC_REQ,
        "", "## 上下文", CTX_TIME,
        "", CTX_NEWS,
        "", CTX_CHAR_INFO,
        "", CTX_CHAR_STATUS,
        "", CTX_CURRENT_GOAL,
        "", CTX_RELATION,
        "", CTX_HISTORY,
        "", CTX_LATEST,
    ])


def chat_response_system():
    return compose([SYS_PERSONA])


def chat_response_userp():
    return compose([
        "## 你的任务", TASK_NOVEL,
        "", TASK_WECHAT, TASK_WECHAT_REQ_TEXT,
        "", "## 上下文", CTX_TIME,
        "", CTX_NEWS,
        "", CTX_CHAR_INFO,
        "", CTX_CHAR_PROFILE,
        "", CTX_USER_PROFILE,
        "", CTX_CHAR_KNOWLEDGE,
        "", CTX_CHAR_PHOTO,
        "", CTX_CHAR_STATUS,
        "", CTX_CURRENT_GOAL,
        "", CTX_RELATION,
        "", CTX_HISTORY,
        "", CTX_LATEST,
        "", "## 注意事项", NOTICE_SEGMENT, NOTICE_GEN, NOTICE_EMPTY,
    ])


def refine_system():
    return compose([SYS_PERSONA_NOJSON])


def refine_userp():
    return compose([
        "## 你的任务", TASK_NOVEL_NOJSON,
        "", TASK_WECHAT_REFINE,
        "", "## 上下文", CTX_TIME,
        "", CTX_NEWS,
        "", CTX_CHAR_INFO,
        "", CTX_CHAR_PROFILE,
        "", CTX_USER_PROFILE,
        "", CTX_CHAR_KNOWLEDGE,
        "", CTX_CHAR_PHOTO,
        "", CTX_CHAR_STATUS,
        "", CTX_CURRENT_GOAL,
        "", CTX_RELATION,
        "", CTX_HISTORY,
        "", CTX_LATEST,
        "", CTX_DRAFT_REPLY,
        "", "## 注意事项", NOTICE_REFINE_GEN,
    ])


def post_analyze_system():
    return compose([SYS_PERSONA])


def post_analyze_userp():
    return compose([
        "## 你的任务", TASK_NOVEL,
        "", TASK_SUMMARY, TASK_SUMMARY_REQ,
        "", "## 参考上下文", CTX_TIME,
        "", CTX_CHAR_INFO,
        "", CTX_CHAR_PROFILE,
        "", CTX_USER_PROFILE,
        "", CTX_CHAR_KNOWLEDGE,
        "", CTX_CHAR_STATUS,
        "", CTX_CURRENT_GOAL,
        "", CTX_RELATION,
        "", CTX_HISTORY,
        "", CTX_LATEST_BOTH,
    ])
