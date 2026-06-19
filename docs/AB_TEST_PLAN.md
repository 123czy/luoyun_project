# 新角色 vs qiaoyun：X 上的 A/B 实验与实现方案

> 决策前提（用户已定）：
> - 新角色 = **X 影响者**（不是微信私聊）。
> - 首要指标 = **关系推进速度**。
> - 约束：**不改 qiaoyun 现有大脑代码**。
>
> 关键张力：「X 影响者(1对多)」与「关系推进速度(1对1)」不天然兼容。
> 本方案的调和：影响者用公开账号涨粉，**关系深化发生在 reply/DM 的 1对1 线程**，
> A/B 下沉到「单账号 + 按互动用户随机分流」，从而既保留 A/B 严谨性，又契合该指标。

---

## 1. 实验设计

### 1.1 结构：单公开账号 + 按用户随机分流

```
一个公开 X 账号（共享，负责发帖/涨粉，对两组恒定）
        │  入站互动关注者按 user_id 哈希随机分到 A 或 B
   control(A)                treatment(B)
   qiaoyun 现有大脑(零改)        新角色现代栈
        │                          │
   各自处理该用户的 reply/DM 1对1 关系深化
        └─── 比「关系推进速度」(主) + guardrail(副) ───┘
```

- **受控变量**：只有「大脑/栈」不同。发帖内容、账号、涨粉手段对两组**完全相同**。
- **随机化单元**：互动关注者（per-user），不是账号。同一用户固定分到一组（按 user_id 哈希），避免串味。
- **为什么不开两个账号**：① 同人设双账号违反 X 反操纵/仿冒条款；② 分流受众、双倍冷启动；
  ③ 公开发帖质量会变成混淆变量。per-user 分流全部规避。

### 1.2 qiaoyun 如何「零改动」当对照组

靠队列解耦（`entity/message.py` 的 inputmessages/outputmessages）：
- 新增的 X 连接器把分到 A 组用户的互动写进 inputmessages（`platform="x"`）。
- qiaoyun 现有 `qiaoyun_handler.py` 大脑**原样**消费，不动一行 agent 代码。
- 出站 outputmessages 由 X 连接器发回。
→ 「不优化 qiaoyun」承诺成立：只加共享连接器，不碰大脑。

---

## 2. 首要指标的操作化定义

**关系推进速度（主指标）**，在 X 语境重定义：

- 群体：与角色**产生过 ≥1 次互动**的关注者。
- 度量（任选其一为主，建议都埋）：
  - 从首次互动到 `closeness+trustness ≥ T` 的**中位互动轮数 / 中位天数**；
  - 第 N 轮互动后的 `closeness+trustness` **均值**。
- 关系值复用 luoyun relation 状态机。**A、B 必须落同一套数值口径与更新规则**，否则不可比
  （treatment 即便换了栈，relation 的计分逻辑要和 control 对齐——这是实验有效性的硬约束）。

**Guardrail（副指标，防止「优化关系却牺牲影响者本职」）**：

- 粉丝净增、帖子互动率（like/RT/reply）、触达/曝光。
- 判读规则：treatment 主指标显著优 **且** guardrail 不显著劣，才算赢。

**统计**：

- 样本 = 互动关注者数；按用户随机分组、并行采集。
- 预先估最小样本量 / 最短周期（取决于日互动用户量，冷启动期可能很稀疏——见第 6 节风险）。
- 防污染：一个用户只属于一组；公开帖对所有人一致。

---

## 3. Treatment（新角色）现代栈实现 = 落地 MODERNIZATION_ANALYSIS

新角色就是「现代化方案」的活体，逐项对应：

| 维度 | 实现 | 备注 |
|---|---|---|
| 编排 | **保留** luoyun 确定性管道哲学（rewrite→retrieve→respond→analyze） | 热路径上比全自主 tool-loop 更快/省/稳 |
| 工具 | **MCP 化**：`search` / `generate_image` / `retrieve_memory` / `post_tweet` 作为 MCP server | 跨语言，解绑「Python vs TS」，对齐平台 Layer B |
| 记忆-检索 | **reranker + hybrid search** 替手调权重(0.3/0.7) | 召回质量↑、免调参 |
| 记忆-写入 | 自动抽取/巩固层替 `post_analyze` 手动 upsert | 减规则维护 |
| 记忆-结构 | **保留** relation 状态机 + 分类型命名空间 | 护城河；且指标依赖它 |
| 人设 | **Skills 化**：发帖/生活照/危机公关/日程 拆成能力包 | 换角色=换 skill |
| 模型 | 前沿模型 + **prompt caching** + 原生结构化输出 | 替默认 gpt-4-turbo/单轮/function-call hack |

**硬约束**：treatment 的 relation 计分口径 = control 的，确保「关系推进速度」可比。

---

## 4. 共享基础设施（两组都用，但不碰 qiaoyun 大脑）

1. **X 连接器**（新，`connector/x/`）：入站轮询 mentions/replies/DM → 写 inputmessages；
   出站读 outputmessages → 发推/回复/私信。带 user_id→组 的分流路由。
2. **发帖编排**：复用 `daily_agent` 选题/生成/审核思路，发帖对两组恒定（建议由共享逻辑或单一大脑统一发，避免公开内容变成混淆项）。
3. **埋点管线**：relation 快照、互动事件、X 指标拉取 → 落一张实验事件表（含 user_id、组别、时间、relation 值、X 指标）。
4. **隔离**：两组各自的 Mongo 命名空间，记忆不串。

---

## 5. 工程拆解与节奏

| 阶段 | 内容 | 产出/门槛 |
|---|---|---|
| **P0 对照就位** | 共享 X 连接器 + 分流路由 + 埋点；把 qiaoyun 大脑(不改)接上 X | control 能在 X 上跑、数据能采 |
| **P1 处理组** | 新角色现代栈：MCP 工具 + reranker 记忆 + skills 人设 + 前沿模型；对齐 relation 口径 | treatment 能在 X 上跑 |
| **P2 跑实验** | 双组并行 N 周，单账号 per-user 分流 | 收满最小样本量 |
| **决策门** | treatment 关系推进显著优 **且** guardrail 不劣 → 推广现代栈 / 迁移 qiaoyun | 否则迭代或否决 |

---

## 6. 风险与实验有效性陷阱

1. **冷启动（头号风险，呼应 HANDOFF）**：新账号没粉丝→互动关注者稀疏→关系推进样本量不够，
   实验跑不出统计显著。**必须先有破圈/投放让账号有基础流量**，否则实验本身无法成立。
   这是 P2 的前置条件，不是事后优化。
2. **relation 口径漂移**：treatment 换了栈，若 relation 计分逻辑也变，主指标不可比。
   → 把 relation 更新规则抽成两组共用的独立模块，锁死口径。
3. **公开内容混淆**：若 A/B 两组各自发不同的公开帖，涨粉差异会污染关系推进结论。
   → 公开发帖保持对两组一致（建议统一发），只让「1对1 互动处理」分流。
4. **人设一致性**：A/B 比的是「栈」，不是「人设」。两组应同一人设种子；若人设也不同，
   结论变成「栈+人设」联合效应，需在解读时声明。
5. **X 平台合规**：1对1 私信自动化、回复频率要遵守 X 自动化政策与限流，避免封号。
6. **关系状态机是私聊设计**：公开 reply 语境下，数值更新触发条件需重定义（如「公开 reply」与「DM」权重不同）。

---

## 7. 一句话

把 A/B 从「两个账号」下沉到「一个账号 + 按互动用户随机分流」，
是同时满足「新角色上 X」「指标=关系推进速度」「qiaoyun 零改动」三个约束的**唯一干净解**。
最大实操风险不是工程，是**冷启动下的样本量**——没有基础流量，这个实验跑不出结论。

---

## 8. 落地实现（受控因果版）

> 目标已定：要**可信因果证据**（「现代栈更好」），不是产品对比。
> 三条不可妥协的有效性前提，先锁死再写代码。

### 8.0 三条有效性前提（违反任一，结论作废）

1. **同人设**：treatment = qiaoyun 人设 + 现代栈大脑。**不是新人设**。
   否则结论=「栈+人设」联合效应，不可归因到栈。新人设是产品，不是本实验对象。
2. **同公开内容**：舞台账号的公开帖由**单一共享发帖进程**产出，对两组恒定。
   只有「1对1 的 reply/DM 处理」按用户分流。公开内容若按组分叉，涨粉差异会污染结论。
3. **同 relation 口径**：两个大脑更新 closeness/trustness 的**计分规则必须逐位一致**。

### 8.1 拓扑：一个舞台账号 + 后端双脑

```
        舞台 X 账号（单一公开身份 = qiaoyun 人设）
   公开发帖：单一共享进程（恒定）        私信/回复入站
                                              │
                          首见用户 → sticky 分组 hash(user_id+salt)%2
                                ┌─────────────┴─────────────┐
                          A组(control)                  B组(treatment)
                       to_user=qiaoyun_cid           to_user=newbrain_cid
                       qiaoyun 现有大脑(零改)           qiaoyun人设@现代栈
                                └─────────────┬─────────────┘
                          出站 outputmessages：两个 cid 都映射回**同一舞台账号**发出
```

- 已建的 `connector/x/` 复用；新增：①入站分流路由 ②出站「双 cid → 单账号」映射。
- qiaoyun 大脑不动；treatment 用独立 runner 命名空间（如 `newbrain/runner/`）。

### 8.2 分组（sticky，持久化）

新集合 `experiment_assignments`：
```
{ experiment_id, user_id, group: "A"|"B", assigned_at }
```
- 首见用户即分配并落库；之后**永远固定同组**（防污染）。
- 路由：A → inputmessage.to_user = qiaoyun_cid；B → newbrain_cid。

### 8.3 relation 口径锁定（「不改 qiaoyun」下的解法）

- 把 qiaoyun `qiaoyun_post_analyze_agent` 里更新 closeness/trustness/dislike 的规则，
  **逐位复制**进 treatment 大脑（不抽公共模块、不动 qiaoyun）。
- 写一个 parity 单测：同一段对话喂两边，断言 relation 增量完全相等。**这是实验有效性的闸门。**

### 8.4 埋点

新集合 `experiment_events`，每次互动后写一条：
```
{ experiment_id, user_id, group, cid, ts,
  event: "inbound"|"relation_update",
  round_n,                        # 该用户第几轮互动
  closeness, trustness, dislike,  # 更新后的快照
  channel: "reply"|"dm" }
```
- 关系推进 = 由 (user_id, round_n, closeness+trustness) 序列算「达阈 T 的轮数/天数」。
- Guardrail（账号级，两组共享同账号→看**每组用户**的留存/互动衰减，而非账号粉丝数）：
  组内用户的回访率、互动轮数衰减曲线。

### 8.5 判读

- 主指标：达阈 T 的**生存分析**（Kaplan-Meier，未达阈用户做删失），A vs B 比中位轮数；
  或第 N 轮 `closeness+trustness` 均值 + 显著性检验。
- 样本：每组互动用户数；**先估最小样本量**。冷启动期样本稀疏是头号阻塞（见第 6 节）。
- 决策门：B 关系推进显著优 **且** 组内 guardrail 不劣 → 现代栈成立，可铺开/迁 qiaoyun。

### 8.6 工程顺序

1. 舞台账号模式：`connector/x/` 加「入站分流 + 出站双 cid→单账号」。
2. `experiment_assignments` + sticky 分组路由。
3. treatment 大脑：qiaoyun 人设种子 + 现代栈（MCP 工具/reranker 记忆/skills/前沿模型），
   relation 规则逐位复制 + parity 单测。
4. `experiment_events` 埋点（两个大脑 post_analyze 后各写一条）。
5. 单一共享发帖进程（公开内容恒定）。
6. 判读脚本（生存分析）。

→ 1/2/4/5 是**两组共用、不碰 qiaoyun** 的基础设施；3 是 treatment 独立包。
