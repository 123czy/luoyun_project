# TS 开发者上手指南

这份文档面向“熟悉 TypeScript 全栈，但不熟 Python”的开发者。目标不是把 Python 从头讲一遍，而是让你能快速回答三个问题：

- 这个项目本质上是什么？
- 一条微信消息从进入到回复，经过哪些代码和数据？
- 我要改角色、改回复逻辑、接新平台或排查问题，应该从哪里下手？

## 1. 先建立心智模型

`luoyun_project` 不是一个典型 Web 后端，也不是 Next.js/Express 那类请求进来同步返回的服务。它更像一个由 MongoDB 驱动的异步机器人系统：

```mermaid
flowchart LR
    A["微信 / ECloud 回调"] --> B["connector/ecloud/ecloud_input.py<br/>Flask 入站"]
    B --> C["MongoDB inputmessages"]
    C --> D["qiaoyun/runner/qiaoyun_runner.py<br/>主 Agent 轮询"]
    D --> E["Agent 链路<br/>重写 / 召回 / 回复 / 总结"]
    E --> F["MongoDB outputmessages"]
    F --> G["connector/ecloud/ecloud_output.py<br/>出站轮询"]
    G --> H["微信 / ECloud 发送"]
```

从 TS 视角看，可以把它理解成：

- `inputmessages` 类似一个入站任务队列。
- `outputmessages` 类似一个延迟发送队列。
- `qiaoyun_runner.py` 类似一个常驻 worker，而不是 HTTP controller。
- `BaseAgent.run()` 返回的是 Python generator 状态流，接近“同步版 observable”，不是 Promise。
- MongoDB 里没有强 schema，代码靠约定读写字段，类似你在 TS 里大量使用 `Record<string, any>`。

## 2. 仓库地图

| 路径 | 作用 | 你最常看的文件 |
| --- | --- | --- |
| `connector/ecloud/` | 当前部署文档主线使用的微信通信层。负责收消息、发消息、适配 ECloud 格式。 | `ecloud_input.py`, `ecloud_output.py`, `ecloud_adapter.py` |
| `connector/gewechat/` | 另一套 GeWeChat 接入尝试。当前代码引用缺失的 `.lib.client` 和 `common.mongo_client`，不要默认把它当主链路。 | `gewechat_connector.py`, `gewechat_channel.py` |
| `qiaoyun/runner/` | 算法层常驻入口。主对话和后台行为都从这里跑。 | `qiaoyun_runner.py`, `qiaoyun_handler.py`, `qiaoyun_background_handler.py` |
| `qiaoyun/agent/` | 角色 Agent 链路：改写问题、召回记忆、生成回复、总结记忆、每日脚本。 | `qiaoyun_chat_agent.py`, `qiaoyun_*_agent.py` |
| `framework/agent/` | Agent 基类和 LLM 调用封装。 | `base_agent.py`, `llmagent/base_singleroundllmagent.py`, `llmagent/doubao_llmagent.py` |
| `qiaoyun/prompt/` | prompt 常量。大量行为不是写在代码里，而是写在这里的 prompt 拼接里。 | `chat_taskprompt.py`, `chat_contextprompt.py`, `system_prompt.py` |
| `dao/` | MongoDB 数据访问层。 | `mongo.py`, `user_dao.py`, `conversation_dao.py`, `lock.py` |
| `entity/` | 消息读写工具。 | `message.py` |
| `qiaoyun/tool/` | 角色相关多模态工具：图片、语音。 | `image.py`, `voice.py` |
| `framework/tool/` | 外部模型和工具封装：搜索、文生图、语音识别、图像理解等。 | `search/aliyun.py`, `text2image/liblib.py`, `image2text/ark.py` |
| `util/` | 通用工具：embedding、OSS、时间、文件转换。 | `embedding_util.py`, `oss.py`, `time_util.py` |
| `conf/` | 配置加载。 | `config.py`, `config.json` |
| `doc/` | 原项目部署、运维、数据结构说明。 | `部署与启动（qiaoyun）/`, `misc/db_schema.md` |
| `docs/` | 当前工作区额外上下文文档，包含 Bot Chain 评估资料。 | `EVALUATION_TASK.md`, `PROJECT_CONTEXT_HANDOFF.md` |

## 3. 运行时进程

生产形态至少有四个组件：

1. MongoDB  
   数据库和轻量队列都靠它。部署文档使用 `mongo:5.0.5`。

2. ECloud 入站服务  
   `connector/ecloud/ecloud_input.py` 是 Flask app，监听 `0.0.0.0:8080`，接收 ECloud 的 `/message` 回调，把微信消息标准化后写入 `inputmessages`。

3. Qiaoyun 算法 worker  
   `qiaoyun/runner/qiaoyun_runner.py` 每秒循环，同时跑：
   - `main_handler()`：处理用户输入。
   - `background_handler()`：处理每日脚本、忙闲状态、主动消息、延迟消息。

4. ECloud 出站 worker  
   `connector/ecloud/ecloud_output.py` 每秒扫描 `outputmessages`，找到 `status=pending` 且到达 `expect_output_timestamp` 的消息，然后调用 ECloud API 发送。

对应启动脚本：

```bash
source connector/ecloud/ecloud_start.sh
source qiaoyun/runner/qiaoyun_start.sh
```

注意：这些脚本会 `export env=aliyun`，再启动进程并 tail 日志。按 Ctrl+C 只会停止 tail，不一定停止后台进程。

## 4. 配置和依赖

### Python 环境

部署文档使用 Python 3.11 + venv：

```bash
python3 -m venv myenv
source myenv/bin/activate
pip3 install -r requirements.txt
```

阿里云 NLS SDK 是本地 vendor 目录，需要单独安装：

```bash
cd framework/tool/voice2text/alibabacloud-nls-python-sdk-dev
pip3 install -r requirements.txt
pip3 install .
```

项目没有 `pyproject.toml`、`setup.py` 或 npm 类似的 scripts。大部分 Python 文件依赖 `sys.path.append(".")`，所以运行命令时必须在仓库根目录执行。

### 配置加载

`conf/config.py` 的逻辑很简单：

```python
with open("conf/config.json") as f:
    conf = json.load(f)
env = os.getenv("env", "dev")
server_conf = conf.get(env) or {}
conf.update(server_conf)
CONF = conf
```

等价 TS 心智模型：

```ts
const base = readJson("conf/config.json")
const env = process.env.env ?? "dev"
export const CONF = { ...base, ...(base[env] ?? {}) }
```

这里有两个容易踩的点：

- 环境变量名是小写 `env`，不是常见的 `NODE_ENV` / `PYTHON_ENV`。
- 当前 `config.json` 顶层有 `aliyun.characters`，启动脚本用 `env=aliyun` 后会把它合并成顶层 `CONF["characters"]`。如果你本地直接跑且没设 `env=aliyun`，读取 `CONF["characters"]` 的地方会报错。

`config.json` 里涉及外部服务配置：MongoDB、ECloud、火山方舟、阿里云 ASR/Embedding/OSS、LibLib、MiniMax。不要把真实 key 写进可提交文件。

## 5. 一条消息的完整链路

### 5.1 入站

入口：`connector/ecloud/ecloud_input.py`

关键步骤：

1. Flask 收到 `POST /message`。
2. 检查 `messageType` 是否在支持列表中：
   - `60001` 私聊文本
   - `60014` 私聊引用
   - `60004` 私聊语音
   - `60002` 私聊图片
3. 通过 `toUser` 找角色用户。找不到角色就跳过。
4. 通过 `fromUser` 找普通用户。找不到就调用 ECloud `getContact` 创建用户。
5. 调用 `connector/ecloud/ecloud_adapter.py` 转成标准消息。
6. 写入 MongoDB `inputmessages`，状态为 `pending`。

语音和图片在入站阶段就会被转文字：

- 语音：下载 silk 文件，调用阿里云 ASR 得到文本。
- 图片：拿图片 URL，调用火山方舟视觉模型得到图像描述。

### 5.2 主对话处理

入口：`qiaoyun/runner/qiaoyun_handler.py`

关键步骤：

1. 从 `inputmessages` 查找目标角色的 `pending` 消息。
2. 找到 user、character、conversation。
3. 对 conversation 加 MongoDB 锁，避免同一会话并发处理。
4. 把该用户到该角色的所有 `pending` 输入置为 `handling`。
5. `context_prepare()` 组装 Agent 上下文，包括：
   - `user`
   - `character`
   - `conversation`
   - `relation`
   - 当日新闻
   - 历史对话字符串
   - 最新输入字符串
6. 检查拉黑、管理员硬指令、角色忙闲状态。
7. 空闲时执行 `QiaoyunChatAgent(context)`。
8. 把 Agent 输出拆成文本、语音或图片，写入 `outputmessages`。
9. 更新 conversation history、relation、输入消息状态。

### 5.3 Agent 链路

入口：`qiaoyun/agent/qiaoyun_chat_agent.py`

主链路按顺序执行：

1. `QiaoyunQueryRewriteAgent`  
   从当前聊天中生成多类检索问题和关键词。

2. `QiaoyunContextRetrieveAgent`  
   基于 query 做向量召回和关键词召回，读取 `embeddings`：
   - `character_global`
   - `character_private`
   - `user`
   - `character_knowledge`
   - `character_photo`

3. `QiaoyunChatResponseAgent`  
   生成结构化回复，核心输出是 `MultiModalResponses`，可能包含 `text` / `voice`。

4. `QiaoyunChatResponseRefineAgent`  
   小概率触发，或当回复涉及扩展内容时较高概率触发，用来细化回复。

5. `QiaoyunPostAnalyzeAgent`  
   对本轮对话做总结，更新长期记忆、用户画像、关系、反感度等。

从 TS 视角看，这不是 LangChain 那类现成 graph，而是手写 orchestration：

```python
c = QiaoyunQueryRewriteAgent(self.context)
for result in c.run():
    if result["status"] == AgentStatus.FINISHED.value:
        self.context["query_rewrite"] = result["resp"]
```

`BaseAgent.run()` 会 yield 多个状态。调用方通常只关心 `status == "finished"` 或中间的 `status == "message"`。

### 5.4 出站

入口：`connector/ecloud/ecloud_output.py`

关键步骤：

1. 每秒查一条 `outputmessages`：
   - `platform = wechat`
   - `status = pending`
   - `expect_output_timestamp < now`
2. 根据 `message_type` 选择 ECloud API：
   - text -> `sendText`
   - voice -> `sendVoice`
   - image -> `sendImage`
3. 成功后标记 `handled`，失败标记 `failed`。

语音回复不是直接发文本。`qiaoyun/tool/voice.py` 会调用 MiniMax TTS，生成 PCM，再转 silk，上传 OSS，最后把签名 URL 交给 ECloud。

图片回复不是实时生成。正常聊天里 photo 会引用已有相册图片 ID，经 `qiaoyun/tool/image.py` 上传/签名后发送。

## 6. 后台行为

入口：`qiaoyun/runner/qiaoyun_background_handler.py`

`background_handler()` 每秒执行一次，但内部通过取模和数据库状态控制实际动作。

主要职责：

- 关系衰减：周期性降低 `closeness` 和 `trustness`。
- 忙闲状态：根据 `dailyscripts` 当前时间段更新角色状态，并把合适的 hold 消息恢复为 pending。
- 每日脚本：如果明天/目标日期没有 `dailynews`，执行 `QiaoyunDailyAgent`。
- 主动消息：按概率给关系较好的用户安排 future action。
- 延迟消息：到点执行 `conversation_info.future.action`。

每日 Agent 的工作比较重：

1. 搜索当天新闻和兴趣话题。
2. 学习进 `dailynews` 和知识库。
3. 生成一天的活动脚本 `dailyscripts`。
4. 抽取部分活动生成图片和朋友圈文案。
5. 把图片和文案发给管理员审核。

## 7. MongoDB 数据模型

详细 schema 在 `doc/misc/db_schema.md`，这里给你开发时最需要的版本。

### `users`

既存普通用户，也存角色用户。角色用户满足 `is_character=True`。

常用字段：

- `_id`
- `name`
- `platforms.wechat.id`
- `platforms.wechat.account`
- `platforms.wechat.nickname`
- `user_info.description`
- `user_info.status`

### `conversations`

会话状态。它承担了聊天历史、当前输入、相册使用历史、未来主动消息计划。

常用字段：

- `talkers`
- `platform`
- `chatroom_name`
- `conversation_info.chat_history`
- `conversation_info.input_messages`
- `conversation_info.photo_history`
- `conversation_info.future`

### `relations`

用户和角色之间的关系画像。

常用字段：

- `uid`
- `cid`
- `user_info`
- `character_info`
- `relationship.closeness`
- `relationship.trustness`
- `relationship.dislike`
- `relationship.status`

### `inputmessages`

入站消息队列。

关键状态：

- `pending`：待处理。
- `handling`：正在处理。
- `hold`：角色忙或睡觉，暂存。
- `handled`：处理完成。
- `failed`：处理失败。

### `outputmessages`

出站消息队列。

关键字段：

- `expect_output_timestamp`：模拟打字/语音延迟，到点才发。
- `status`
- `message_type`
- `message`
- `metadata.url`
- `metadata.voice_length`

### `embeddings`

长期记忆和图片库。

关键字段：

- `key`
- `value`
- `key_embedding`
- `value_embedding`
- `metadata.type`
- `metadata.uid`
- `metadata.cid`
- `metadata.url`
- `metadata.file`

常见 `metadata.type`：

- `character_global`
- `character_private`
- `user`
- `character_knowledge`
- `character_photo`

注意：`QiaoyunPostAnalyzeAgent` 里有一个拼写问题：写入角色知识时使用了 `chatacter_knowledge`，而召回侧查的是 `character_knowledge`。如果你要修记忆链路，这里是优先检查点。

## 8. Python 代码阅读速查

### import 和运行目录

大量文件开头都有：

```python
import sys
sys.path.append(".")
```

这表示它依赖仓库根目录在 Python import path 中。不要在子目录里直接执行脚本，否则 `from dao.mongo import MongoDBBase` 这类 import 可能失败。

### dict 就是主要数据结构

项目里几乎没有 Pydantic / dataclass / TypedDict。上下文大多是嵌套 dict：

```python
context["conversation"]["conversation_info"]["future"]["action"]
```

这类似 TS 中没有类型保护的深层对象访问。改字段名时要全局 `rg`，否则很容易出现运行时 KeyError。

### class 很薄，状态放实例上

Agent 类通常继承 `BaseAgent` 或 `DouBaoLLMAgent`，重写：

- `_prehandle()`
- `_execute()`
- `_posthandle()`
- `_error_handler()`

主逻辑一般在 `_execute()`。LLM Agent 的 prompt template、输出 schema 也作为类属性写在具体 Agent 文件里。

### generator 是核心控制流

`BaseAgent.run()` 不是返回最终值，而是 yield 状态：

```python
for result in agent.run():
    status = result["status"]
    resp = result["resp"]
```

你可以把它理解成一个同步状态机。`AgentStatus.MESSAGE` 用来中途把消息交给外层发送，`AgentStatus.FINISHED` 表示这个 agent 完成。

### async 只用于常驻循环

`qiaoyun_runner.py` 用 `asyncio.gather()` 同时跑两个无限循环，但内部多数业务代码还是同步 I/O。这里的 async 主要是为了让两个 while loop 轮流执行，不代表整条链路是非阻塞架构。

## 9. 常见改动入口

### 改角色人设

优先看：

- `qiaoyun/role/prepare_character.py`
- `qiaoyun/role/qiaoyun/role_basics.txt`
- `qiaoyun/role/qiaoyun/role_settings.txt`
- `qiaoyun/role/qiaoyun/role_settings_advanced.txt`

注意：`prepare_character.py` 会把角色信息和预制图片写入 MongoDB。改文件不等于线上数据自动更新，需要重新执行脚本或写迁移逻辑。

### 改聊天风格或回复约束

优先看：

- `qiaoyun/prompt/chat_taskprompt.py`
- `qiaoyun/prompt/chat_contextprompt.py`
- `qiaoyun/prompt/chat_noticeprompt.py`
- `qiaoyun/agent/qiaoyun_chat_response_agent.py`

如果要改输出结构，要同步改：

- `QiaoyunChatResponseAgent.default_output_schema`
- `qiaoyun/runner/qiaoyun_handler.py` 中消费 `MultiModalResponses` 的逻辑

### 改记忆召回

优先看：

- `qiaoyun/agent/qiaoyun_query_rewrite_agent.py`
- `qiaoyun/agent/qiaoyun_context_retrieve_agent.py`
- `qiaoyun/agent/qiaoyun_post_analyze_agent.py`
- `util/embedding_util.py`
- `dao/mongo.py`

如果新增一种记忆类型，需要同时改：

- 总结写入
- query rewrite schema
- context retrieve 召回
- prompt context 展示
- `doc/misc/db_schema.md`

### 新增输入消息类型

改动点通常是：

1. `connector/ecloud/ecloud_input.py` 的 `supported_message_types`。
2. `connector/ecloud/ecloud_adapter.py` 增加 ECloud -> 标准消息转换。
3. `qiaoyun/util/message_util.py` 增加标准消息 -> prompt 字符串。
4. 如果会生成新输出类型，再改 `qiaoyun_handler.py` 和 `ecloud_output.py`。

### 接新平台

建议沿着 `BaseConnector` 的形状做：

- 入站：平台消息 -> 标准 `inputmessages`
- 出站：标准 `outputmessages` -> 平台 API

尽量不要把平台字段散落进 Agent。Agent 应该继续只理解标准消息和 `context`。

### 改主动消息或日常行为

优先看：

- `qiaoyun/runner/qiaoyun_background_handler.py`
- `qiaoyun/agent/background/`
- `qiaoyun/agent/daily/`

关键参数在 `qiaoyun_background_handler.py` 顶部：

- `descrease_frequency`
- `proactive_frequency`
- `proactive_chance`

## 10. 本地启动参考

完整跑通依赖外部服务，不是纯本地项目。你至少需要：

- MongoDB
- Python 3.11 venv
- `requirements.txt`
- 阿里云 NLS SDK 本地安装
- `qiaoyun/temp`
- `conf/config.json` 配好 MongoDB、角色 ID 和外部 API
- 必要环境变量：`env=aliyun`、`ARK_API_KEY`、`DASHSCOPE_API_KEY`、`MINIMAX_API_KEY`、OSS/ASR 相关 key

基础准备：

```bash
python3 -m venv myenv
source myenv/bin/activate
pip3 install -r requirements.txt
mkdir -p qiaoyun/temp
```

初始化角色：

```bash
python3 qiaoyun/role/prepare_character.py
python3 dao/get_special_users.py
```

启动：

```bash
source connector/ecloud/ecloud_start.sh
source qiaoyun/runner/qiaoyun_start.sh
```

开发时更建议先只跑局部脚本或单个 Agent 的 `__main__` 调试，不要一上来启动整套外部通信链路。

## 11. 排查问题的顺序

### 消息没进来

查：

- ECloud 回调是否打到 `/message`
- `connector/ecloud/ecloud.log`
- `inputmessages` 是否新增
- `users` 里是否存在目标角色
- `characters` 配置是否指向正确角色 `_id`

### 消息进来了但不回复

查：

- `inputmessages.status`
- `qiaoyun/runner/qiaoyun_runner.log`
- `relations.relationship.status` 是否是 `繁忙` / `睡觉`
- `locks` 集合是否有未释放锁
- `conversation_info.future` 是否影响主动消息逻辑

### Agent 报错

优先看：

- 是否设置 `env=aliyun`
- `CONF["characters"]` 是否存在
- `ARK_API_KEY` / `DASHSCOPE_API_KEY` 是否存在
- prompt `.format(**context)` 是否缺字段
- LLM structured output 是否能被 JSON 解析

### 输出消息不发送

查：

- `outputmessages.status`
- `expect_output_timestamp` 是否已经小于当前时间
- `metadata.url` 是否存在且未过期
- ECloud API 返回码
- 语音失败时是否 fallback 到 text

## 12. 已知技术债和风险点

这些不是立刻要改，但上手时要知道：

- 没有自动化测试、lint、类型检查配置。
- 没有 `pyproject.toml` 或标准包结构，运行目录很重要。
- 配置和启动脚本里有真实 secret 风险，建议迁移到 `.env` 或部署平台 secret。
- `ecloud_input.py` 用 Flask `debug=True`，生产环境要关闭。
- ECloud API host 在 `connector/ecloud/ecloud_api.py` 硬编码。
- GeWeChat 目录依赖缺失，不应作为当前稳定接入主线。
- 数据库字段没有 schema 保护，字段名 typo 会静默制造数据孤岛。
- `MongoDBLockManager.release_lock()` 有些异常路径可能在 `conversation_id` 未赋值时被调用，排查异常时留意日志。
- 主循环每秒轮询 MongoDB，随着用户量增长需要更正式的队列、索引和 worker 管理。

## 13. 第一天建议阅读顺序

1. `README.md`  
   先理解项目目标和能力范围。

2. `doc/misc/db_schema.md`  
   建立数据模型。

3. `connector/ecloud/ecloud_input.py` 和 `connector/ecloud/ecloud_output.py`  
   看平台消息如何进出系统。

4. `qiaoyun/runner/qiaoyun_runner.py`  
   看两个常驻 worker 如何并行。

5. `qiaoyun/runner/qiaoyun_handler.py`  
   看主对话如何消费 `inputmessages`。

6. `qiaoyun/agent/qiaoyun_chat_agent.py`  
   看 Agent 链路的总编排。

7. `framework/agent/base_agent.py` 和 `framework/agent/llmagent/base_singleroundllmagent.py`  
   看 Agent 状态机和 LLM 调用封装。

8. `qiaoyun/prompt/`  
   理解行为主要由 prompt + JSON schema 约束。

9. `qiaoyun/runner/qiaoyun_background_handler.py`  
   最后再看主动消息、每日脚本和朋友圈相关逻辑。

## 14. 对 TS 全栈开发者的改造建议

如果你后续要把它接入 Bot Chain / Launchpad / MCP 这类 TS 侧系统，最稳的边界是“把 luoyun 当作一个 agent worker”，不要先重写内部 Agent：

- 保留 `inputmessages` / `outputmessages` 作为内部队列。
- 在外部写一个 TS adapter，把平台事件转标准消息。
- 把链上钱包、x402 收费、收益归集做成独立服务，通过工具调用或消息 metadata 接入。
- 逐步把 prompt、Agent schema、Mongo document schema 类型化，而不是一次性迁移全项目。

第一阶段最值得补的是工程安全网：

- 给 `ecloud_adapter.py`、`message_util.py`、`QiaoyunContextRetrieveAgent` 加单元测试。
- 给 Mongo document 定义 Pydantic model 或 TypedDict。
- 把 secret 从 `config.json` 和 shell script 挪走。
- 加一个最小的“文本输入 -> 文本输出”离线 smoke test，绕开微信和外部多模态。
