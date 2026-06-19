# luoyun 现代化评估：哪些保留，哪些已有更好实现

> luoyun 是 2023–2024 年的设计。两年里 agent 生态出现了几个标准化的范式转变：
> **MCP（工具/资源协议）、Skills（按需加载的能力包）、托管/自编辑记忆层、原生结构化输出、reranker、prompt caching**。
> 本文逐组件判断：**保留 / 重构 / 替换**，并说明理由。
>
> 总基调:**luoyun 的架构与领域设计大多超前、依然成立；过时的主要是「实现机制」**
> ——当年只能手搓的地方，现在有了标准件或托管方案。不要被「重写一切」带跑。

---

## 速览表

| 组件 | luoyun 现状 | 现代做法 | 判定 |
|---|---|---|---|
| Agent 编排 | 自研 `BaseAgent`，生成器 + 固定链式调用 | 工具循环 / 标准 runtime；但确定性管道对生产对话仍更优 | **保留（哲学）+ 瘦身** |
| 工具调用 | Python 函数硬编码顺序调用 | **MCP server** 暴露工具/资源 | **重构为 MCP** |
| 人设 / Prompt | 巨型模板字符串散在 `qiaoyun/prompt/*.py` | **Skills**：按需加载、渐进披露的能力包 | **重构为 Skill** |
| 记忆召回 | 手写多路召回 + 手调权重(0.3/0.7) + top_n | 内置 hybrid search + **reranker 模型** | **替换检索实现，保留设计** |
| 记忆写入 | `post_analyze` 手动 upsert | 自动抽取 / 自编辑 / 巩固的记忆层 | **重构** |
| 关系状态机 | closeness/trustness/dislike + decay | 通用记忆库**给不了**这种结构化领域状态 | **保留（护城河）** |
| 日程模拟 | 自研 daily script 引擎 | 无对应标准件，仍属差异化 | **保留** |
| 结构化输出 | function-call hack 模拟 schema | API 原生 **structured outputs / JSON schema 严格模式** | **替换** |
| 模型层 | 默认 `gpt-4-turbo`、单轮、国产 provider | 前沿模型 + **prompt caching** + 需要时多轮 | **替换默认 + 加缓存** |
| HITL 审核 | 候选推管理员 + 手动发布 | 仍是公开门面 agent 的最佳实践 | **保留** |
| 并发 / 队列 | MongoDB 轮询 + Mongo 锁 | 够用；可选工作流引擎，非重点 | **保留** |

---

## 一、保留（设计超前，概念仍是 SOTA）

这些是 luoyun 的真正价值，通用框架/新栈**反而给不了**，是「部分复用」里该抢救的核心。

1. **关系状态机**（`closeness / trustness / dislike` + 随时间 decay + 忙闲状态）。
   现代记忆库（Letta/MemGPT 式、各家 memory 工具）做的是「事实记忆」，
   **没有**这种领域化的情感/信任结构化状态。这是人设「有灵魂」的关键，保留。
2. **日程 / 生活模拟引擎**（`qiaoyun_daily_script_agent.py`）。角色有自己的一天、忙闲影响应答节奏——
   差异化设计，无标准件可替，保留。
3. **多路召回的记忆「设计」**（向量 key+value 双路 + 关键词 + 分类型命名空间
   character_global/private/user/knowledge/photo）。**设计思路依然先进**，只是实现该换（见下）。
4. **确定性管道哲学**：固定 query_rewrite → retrieve → respond → analyze，而非让模型自由 tool-loop。
   对**延迟/成本敏感的高频对话热路径**，确定性管道通常比自主循环**更优**（可预测、更便宜、更快）。
   别盲目改成全自主 agent。保留这个哲学。
5. **人工兜底审核流**：公开影响者发错=品牌事故，HITL 仍是最佳实践，保留并升级吞吐（见 X 计划 B3）。

---

## 二、重构（思路对，实现机制过时）

### 2.1 工具 → MCP（对本项目优先级最高）

- **现状**：搜索、文生图、语音、记忆检索都是 Python 函数被硬编码顺序调用，彼此不可组合、不可被外部 agent 复用。
- **现代**：用 **MCP server** 暴露这些能力（`search`、`generate_image`、`retrieve_memory`、
  未来平台的 `launch_token`/`get_earnings`/`pay_inference`）。
- **为什么对本项目尤其关键**：HANDOFF 第 5 节**已经明确**「把平台 MCP 工具做成插件」。
  把 luoyun 的能力先 MCP 化，就能：
  ① 与平台 Layer B 工具同协议组合；② 被 ElizaOS / Claude / 任意 MCP runtime 复用——
  正好解开「luoyun(Python) vs ElizaOS(TS)」的语言绑死：**MCP 是跨语言的，大脑用什么写都能调。**

### 2.2 人设 / Prompt → Skills

- **现状**：人格与行为逻辑是巨型 prompt 字符串，写死在每个 agent 里，跨角色/跨平台无法复用。
- **现代**：**Skill** 范式——把「发社交帖」「生成生活照」「日程模拟」「危机公关话术」拆成独立、
  可按需加载、渐进披露的能力包。换角色 = 换 skill 组合，而不是改 Python。

### 2.3 记忆写入 → 自动巩固

- **现状**：`qiaoyun_post_analyze_agent` 对话后手动 upsert 记忆。
- **现代**：自动抽取 + 去重 + 巩固（consolidation）+ 自编辑的记忆层。
  可在保留 luoyun 分类型命名空间的前提下，把「写什么、何时合并」交给记忆层而非手写规则。

---

## 三、替换（已被标准件取代）

1. **结构化输出**：`framework/agent/llmagent/base_singleroundllmagent.py` 用 function-call 模拟
   `output_schema` ——当年的 workaround。现在各家 API 有**原生 structured outputs / JSON schema 严格模式**，
   更稳、更省。直接替换。
2. **手调召回权重**：`context_retrieve_agent` 里 `0.3 / 0.7 / bar_min / bar_max` 的魔法数字手动加权，
   正是 **reranker 模型**（cross-encoder，如 BGE/Qwen/Cohere reranker）要解决的问题。
   用 reranker 替掉 `merge_results_embedding` 的手算逻辑，召回质量更高且免调参。
   向量库的 **hybrid search**（向量+关键词内置融合）也可替掉手写的双路 merge。
3. **默认模型 / 单轮**：默认 `gpt-4-turbo`、只支持单轮。换前沿模型（人设/长上下文/指令遵循显著更强），
   对巨型静态人设 prompt 上 **prompt caching** 砍成本；需要工具时支持多轮。
4. **Embedding provider**：当前 aliyun。可评估当前最佳 embedding + rerank 组合（非紧急，锁定不算问题）。

---

## 四、对决策的影响

- **MCP 化是「解绑语言之争」的关键一步**：先把 luoyun 能力 MCP 化，
  「大脑用 ElizaOS 还是自研、用 Python 还是 TS」就从「二选一重写」降级为「换个 MCP 客户端」。
  → 建议无论走哪条路，**第一优先级是把 luoyun 的工具与记忆 MCP 化**。
- **保留的是领域设计（关系/日程/人设/确定性管道），替换的是通用机制
  （检索权重/结构化输出/模型/工具协议）。** 这条线划清楚，就不会「为了现代化把护城河一起拆了」。

---

## 落地优先级（与 X 迁移合并看）

| 优先级 | 动作 | 收益 |
|---|---|---|
| P0 | 工具/记忆 **MCP 化**；结构化输出换原生 | 解绑语言、对齐平台方向、稳定性 |
| P0 | 默认模型升级 + prompt caching | 人设质量↑、成本↓ |
| P1 | 召回换 reranker / hybrid search | 记忆质量↑、免手调参 |
| P1 | Prompt → Skills 化 | 多角色/多平台复用 |
| P2 | 记忆写入换自动巩固层 | 减少手写规则维护 |
| —  | 关系状态机 / 日程 / HITL / 确定性管道 | **不动，是护城河** |
