我觉得当前的项目中 /Users/chenziyang/Documents/AI/luoyun_project/doc/部署与启动（qiaoyun）/2 准备各种模型服务.md 这个文档中 ai 的大模型的选择和接入大模型的方式太杂了 能不能在不改变当前的功能和到醒的基础上 支持 openai 的格式并可以使用硅基流动的 api 聚合服务来完成对应的功能？有哪些可以替代没有影响，有哪些不能替代？

可以支持，但要分层处理。我按“保持现有功能和角色调性不变”理解：**文本大模型接入可以统一成 OpenAI-compatible + 硅基流动；多模态和搜索不能全部无感替换。**

**可以低影响替代**
| 当前能力 | 当前入口 | 是否适合硅基流动/OpenAI 格式 |
|---|---|---|
| 文本 Chat / 结构化输出 | [doubao_llmagent.py](/Users/chenziyang/Documents/AI/luoyun_project/framework/agent/llmagent/doubao_llmagent.py:19)、[base_singleroundllmagent.py](/Users/chenziyang/Documents/AI/luoyun_project/framework/agent/llmagent/base_singleroundllmagent.py:178) | 可以。硅基流动支持 `https://api.siliconflow.cn/v1/chat/completions` 和 OpenAI Python SDK 调用。 |
| DeepSeek/R1/V3 类推理、润色链路 | `deepseek_r1`、`deepseek_v3.1` 模型别名 | 可以替成硅基流动同类模型，但角色语气要回放测试。 |
| 图生文/图片理解 | [ark.py](/Users/chenziyang/Documents/AI/luoyun_project/framework/tool/image2text/ark.py:21) | 基本可以，用硅基流动 VLM 的 Chat Completions；需要选定视觉模型并验证 `image_url` 输入。 |

**可替代但不是无影响**
| 当前能力 | 风险 |
|---|---|
| Embedding / 向量召回，[embedding_util.py](/Users/chenziyang/Documents/AI/luoyun_project/util/embedding_util.py:16) | API 可替，硅基流动有 `/v1/embeddings`，但历史 Mongo 向量已经由阿里 `text-embedding-v3` 生成。换模型后新旧向量空间不一致，必须全量重算或双轨迁移。 |
| ASR 音生文，[aliyun_asr.py](/Users/chenziyang/Documents/AI/luoyun_project/framework/tool/voice2text/aliyun_asr.py:167) | 硅基流动有 `/v1/audio/transcriptions`，但当前链路是 WeChat silk -> PCM -> 阿里 NLS 流式识别。能改，但要处理音频格式和识别质量。 |
| TTS 文生音，[voice.py](/Users/chenziyang/Documents/AI/luoyun_project/qiaoyun/tool/voice.py:16) | 硅基流动有 `/v1/audio/speech`，但当前 MiniMax 用混合音色、情绪、PCM 转 silk。功能可替，声音人设会变，不能算无影响。 |

**不建议直接替代**
| 当前能力 | 原因 |
|---|---|
| LibLib 文生图，[image.py](/Users/chenziyang/Documents/AI/luoyun_project/qiaoyun/tool/image.py:15) | 当前依赖 LibLib 的 checkpoint、LoRA、`additionalNetwork` 和异步任务状态。硅基流动图片接口能生图，但很难保持当前角色照片风格、脸、身材和出图控制。 |
| 阿里百炼搜索增强，[aliyun.py](/Users/chenziyang/Documents/AI/luoyun_project/framework/tool/search/aliyun.py:7) | 当前用 `extra_body.enable_search` 做联网搜索。硅基流动普通 Chat Completions 不等价，除非另接搜索服务。 |
| OSS 存储，[oss.py](/Users/chenziyang/Documents/AI/luoyun_project/util/oss.py:1) | 这不是模型服务，负责图片/语音上传和签名 URL，不能被硅基流动替代。 |
| ECloud / 微信 / X 连接器 | 平台通道能力，不属于大模型接入层。 |

我建议文档改成三类：**基础设施必需**（OSS、Mongo、ECloud/微信）、**可统一到 OpenAI-compatible 的模型能力**（文本 LLM、视觉理解、部分 embedding）、**必须保留或单独验收的多模态能力**（LibLib、MiniMax、阿里 NLS、搜索）。

实现上最小改法是新增一个通用 `OpenAICompatibleLLMAgent`，配置 `SILICONFLOW_API_KEY`、`base_url=https://api.siliconflow.cn/v1`，保留现有 `doubao_1.5_pro/deepseek_v3.1` 这些业务别名，只把别名映射到硅基流动模型 ID。另外要先修一下结构化输出解析：当前请求用 `tools/tool_choice`，但解析还在读旧的 `message.function_call`，换标准 OpenAI-compatible 服务后应兼容 `message.tool_calls`。
