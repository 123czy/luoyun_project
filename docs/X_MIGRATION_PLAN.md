# 朋友圈 → X 迁移改造计划

> 目标：把 luoyun 现有的「微信私聊 + 朋友圈广播」虚拟人，改造成能在 X（及后续 TG/Discord）
> 上**自主发帖 + 应对公开互动 + 涨粉**的影响者 agent。
> 本文档落到具体代码行，区分「直接换 / 复用 / 新增」。

---

## 0. 关键架构事实：队列解耦

luoyun 的 connector 与大脑之间**没有直接调用**，全靠 MongoDB 两张表中转：

```
入站:  gewechat/ecloud 收消息  → 写 inputmessages 表
大脑:  handler 轮询 inputmessages → 跑 agent 链 → 写 outputmessages 表
出站:  connector 读 outputmessages → 发出去
```

- 入站表结构见 `entity/message.py`（platform / from_user / to_user / message / status）。
- 大脑入口 `qiaoyun/runner/qiaoyun_handler.py:49` 只认 `inputmessages`，**从不碰微信**。

**推论：加 X = 加一个 connector（平台 ↔ 队列翻译）+ 补「开放图」能力。对话大脑链路基本不动。**

---

## A. 直接换 / 复用 —— 出站（小改）

| 改造点 | 现状代码 | 动作 |
|---|---|---|
| **发布最后一公里** | `qiaoyun/runner/qiaoyun_hardcode_handler.py:50` `Ecloud_API.snsSendImage({wId, content, paths})` | 新建 `connector/x/x_api.py`，实现 `post_tweet(text, media_paths) -> tweet_id`，替换这一行。**这就是你说的「换发布 API」，确实只是一行。** |
| **内容引擎** | `qiaoyun/agent/daily/qiaoyun_daily_agent.py`（选题→搜索→文生图→PYQPost） | **几乎不动**，整套保留。这是迁移里最值钱、最难、最该留的部分。 |
| **人工审核** | daily_agent 把候选推给管理员 → 管理员发 `朋友圈 <pid>` 硬指令发布 | 直接复用。满足 HANDOFF 第 6 节「早期不要无人值守 + 人工兜底」。 |
| **媒体托管** | `qiaoyun/tool/image.py` `upload_image` → OSS 出 url 给 ecloud | X 改走 X media upload endpoint，在 x_api.py 里封装。 |

---

## B. 新增 —— 出站的「开放图」特性

朋友圈是「闭合关系图」（只有好友看到），X 是「开放关系图」（算法分发、可裂变）。
以下是开放图专属、朋友圈从未需要解决的：

- **B1 平台格式化层**：朋友圈是「图 + 长文案」；X 要文本优先、thread、hashtag、@、≤280 字符。
  - 在 `qiaoyun/prompt/image_prompt.py:23` 的 `PYQPost` 旁加一个 `XPost` 字段；或加独立 formatter，把 PYQPost → tweet/thread。
- **B2 纯文本帖**：当前每条朋友圈都**强制走文生图**（`daily_agent` 必生图，贵且慢）。
  X 大量是对热点的纯文字快评——让内容引擎支持「无图短帖」，省成本也更像真人影响者。
- **B3 发布排程器**：手动逐条硬指令 → 「审核队列 + 定时发布」，支持一天多条、挑最佳时段。

---

## C. 新增 —— 入站（luoyun 完全没有的一侧）

朋友圈是「发完不管」，不处理评论。X 上一条爆帖会招来大量陌生人回复。

- **C1 X 入站连接器**：轮询 mentions / replies / quote-tweets → 写入 `inputmessages`
  （复用现有 schema，`platform="x"`）。
  **做好这一步，现有 `qiaoyun/agent/qiaoyun_chat_agent.py` 对话链几乎能原样回复公开评论**，
  因为大脑只认队列、不认平台。
- **C2 陌生人轻关系分层**：现在每个用户一条 relation + embedding 记忆
  （`qiaoyun/agent/qiaoyun_context_retrieve_agent.py`）。公开场陌生人海量，人人建 embedding
  会把向量库撑爆。要加「匿名/轻关系」层，只有**持续互动**的才升级为有记忆的 relation。
  改 `qiaoyun/runner/context.py` 的 `context_prepare` + relation 创建逻辑。
- **C3 筛选 + 限流**：不是每条 @ 都回。按粉丝量 / 是否 KOL / 内容相关度排优先级；遵守 X API 限流。

---

## D. 新增 —— 增长闭环（破圈的真正核心）

朋友圈没有「涨粉」概念，luoyun 零分析。这是「破圈吸粉」真正发生的地方。

- **D1 数据采集**：定时拉自己帖子的 impression / like / RT / 粉丝增量，入库。
- **D2 反馈优化**：把表现回流到 `daily_agent` 的选题（哪些话题/风格涨粉）。
  对应 HANDOFF 提的「多臂老虎机把每小时收入/增长转成奖励信号」。
- **D3 公开自养仪表盘**（HANDOFF 第 6 节补充建议）：收入进 / 推理成本出 / 净额，链上可查。
  跨到链上 Layer B，先占位。

---

## E. 账号 / 鉴权 / 运维

- **E1 X API 接入**：开发者账号、OAuth、API 费用与限流。
  ⚠️ 2025–26 的 X API 准入与定价是实打实的坑，**先算成本再动手**。
  config.json 仿现有 `ecloud` 段，加一个 `x` 段（key/secret/token）。
- **E2 媒体上传**：见 A 表最后一行。

---

## 完全不动的部分（护城河）

- `framework/agent/*` 编排核心
- 记忆体多路召回 `qiaoyun_context_retrieve_agent.py`
- relation 状态机核心（closeness/trustness/dislike + decay）
- 日程模拟 `qiaoyun_daily_script_agent.py` / `qiaoyun_daily_agent.py`
- 文生图 / TTS / ASR 工具
- query_rewrite → retrieve → response 对话链

---

## 落地节奏

| 阶段 | 范围 | 说明 |
|---|---|---|
| **P0 能跑** | A + C1 + E | X 上自主发帖（沿用审核）+ 被动回 @。大脑全复用，工作量最小。 |
| **P1 破圈** | B + C2 + C3 + D1 + D2 | 开放图格式、陌生人处理、增长闭环。**吸粉真正发生在这里。** |
| **P2 自养** | D3 + 接平台 Layer B | 钱包 / x402 / 仪表盘。 |

**一句话**：A 是「换发布 API」，真的小；真正的工程量在 C、D（开放图的入站与增长闭环）。
但大脑零改动，所以整体远轻于「重做渠道层」。
