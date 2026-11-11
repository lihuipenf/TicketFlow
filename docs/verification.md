# 验证记录

## 2026-11-11 DeepSeek 真实模型联调通过（最新）

用户明确 Key 来自 DeepSeek 后，将本地 `.env` 的 provider/base_url/model/api_mode 改为 deepseek / https://api.deepseek.com / deepseek-flash / chat，保留原Key。重启API和Worker，重试同一模拟工单，完整处理成功。

- 工单：`9abc30ae6c114e9cb91c42bf630b09a3`，标题“真实模型联调：未发货退款（2026-11-11）”。
- 任务：`af3149cd14d64686a69b7dd60e6169aa`，最终 succeeded。
- 真实Qwen/Milvus/BM25混合检索6片段；DeepSeek真实生成回复，4条引用通过ID和原文校验，其中包含PDF第1页来源。
- 模型调用8060ms；模型生成及校验节点8808ms；重启后首次检索包含冷加载耗时25032ms，不代表热运行延迟。
- 实际用量：prompt 1384、completion 1279（含reasoning 836）、total 2663 tokens。
- 工单保留pending_review，sent_text为空，等待用户人工确认。
- 后端完整测试再次运行：32 passed；测试进程显式清空真实LLM凭据，仅测试夹具可注入测试凭据。
- 原始脱敏记录：`data/verification/deepseek-live-2026-11-11.json`，不含密钥。此前阿里云地址鉴权失败记录保留。

官方接入依据：https://api-docs.deepseek.com/ ，JSON输出：https://api-docs.deepseek.com/guides/json_mode/ 。

## 2026-11-11 真实模型联调补充

本地 `.env` 已配置API Key，重启后的API确认读取到配置。创建了“真实模型联调：未发货退款（2026-11-11）”工单，订单查询与真实混合检索完成，命中6片段。

外部模型调用返回 HTTP 401、`invalid_api_key`，服务商提示 `Incorrect API key provided`。因此本次未生成回复，未审核或发送；真实模型联调仍未通过。需要用户在本地更换与当前阿里云接口匹配且有效的Key，之后重试。

工单ID：`9abc30ae6c114e9cb91c42bf630b09a3`；任务ID：`af3149cd14d64686a69b7dd60e6169aa`。忽略Git的本地记录：`data/verification/live-model-2026-11-11.json`。记录未包含密钥。

日期：2026-11-09（Asia/Shanghai）。所有结论基于实际运行，不把测试夹具当真实模型输出。

## 模块验证

| 阶段 | 结果 |
|---|---|
| 骨架 | Python虚拟环境、专用MySQL3307、Alembic迁移成功；健康检查与鉴权2项通过 |
| RAG基础 | PDF页码、Markdown章节行号、长文本切块、中文BM25、RRF、脱敏、引用验证；累计11项通过 |
| 业务与模型适配 | 归属权限、幂等任务、审批状态、过期草稿、未构建版本、SDK结构化响应；累计19项通过 |
| Worker与API | 租约恢复、缺少Key失败、HTTP业务流程、配置权限；累计24项通过 |
| 模拟数据 | 50订单/20FAQ/500历史工单、关联一致性、重复初始化；累计25项通过 |
| 回归修复 | 文档元数据/辅助字段脱敏、非法模型响应摘要、MySQL并发、Milvus释放重开；累计31项通过 |
| 完整业务成功路径 | 测试专用外部响应夹具经真实SDK解析，生成→引用验证→审核→模拟发送；累计32项通过 |
| 前端 | 状态组件测试通过，vue-tsc与Vite生产构建通过 |
| 依赖 | npm audit：0个已知漏洞（本次运行结果，后续需持续检查） |
| 浏览器 | 登录、建单、脱敏、真实RAG、缺少Key报错、检索、配置、日志、订单、移动视口均通过；无JS异常 |
| 启停与角色 | dev.ps1→stop.ps1→dev.ps1实际验证；重启后浏览器全流程再次通过，知识管理员进入知识库且不显示主管日志入口 |

## 真实RAG评测

真实本地Qwen3-Embedding-0.6B，1024维，CPU；真实Milvus Lite持久化与BM25；20条独立改写的样例问题，期望来源为FAQ章节。属于小样本开发回归集，并非企业真实数据上的泛化证明。

| 策略 | Recall@6 | MRR@6 |
|---|---:|---:|
| 向量 | 1.000 | 0.975 |
| BM25 | 0.950 | 0.802 |
| 等权RRF混合 | 1.000 | 0.867 |

本组样例混合召回覆盖全部标注来源，但排序不如纯向量。不可据此宣称混合检索总是更好；下一步应使用真实业务标注集调整权重、分词、阈值，并评估是否引入reranker。

该次20条检索每条约1.35–1.78秒，不含队列等待和首次模型冷加载。原始数据：`data/verification/rag-evaluation.json`。

## 修复与复审

- 集合释放/重连后显式load：先以真实Milvus测试复现失败，再修复，通过重开检索测试。
- MySQL REPEATABLE READ旧快照与审核期间订单变化：两个独立数据库会话复现；修复为锁定当前读并持锁到提交。
- Pydantic错误泄露input_value、来源标题/文件名以及辅助字段漏脱敏：三个测试复现后修复。
- 独立代码审查报告的3项Important问题均已修复并通过针对性复审。

## 明确未验证及限制

- 初次交付（2026-11-09）时用户选择后续配置API Key。2026-11-11已补齐上述DeepSeek真实调用和引用验证；大规模回答质量、生产容量和实际费用账单仍未评测。
- 生成成功路径的自动化集成测试使用明确的外部HTTP响应夹具；生产代码不提供假LLM后备。
- 扫描PDF OCR、真实电商平台、支付退款、多租户、生产容量及灾备恢复不在本次验证范围。
- Vite构建有大于500KB的chunk提示（ElementPlus入口及日志图表）；构建成功，路由和图表已按页面懒加载，可进一步按组件拆分。
- 浏览器测试额外创建的工单及失败过程记录保留，未删除业务或迁移备份。历史种子工单仍精确500条。

## 复现命令

根目录执行 `scripts/verify.ps1`。服务运行时执行 `scripts/evaluate_rag.py`、`scripts/ui_upgrade_smoke.py`、`scripts/ui_detail_races.py` 和可选 `scripts/ui_retrieval_smoke.py`，详细命令见README。后端测试使用独立ticketflow_test数据库。


## 2026-11-11 浅色 UI 升级验证

已升级五个业务页面与登录/导航，项目接入 motion-v 2.12.0。后端 32 项、前端 6 项、生产构建和 npm audit 均通过。新增只读浏览器验证、隔离 API 的两项详情竞争回归、真实本地混合检索界面验证；未新增 LLM 生成调用，也未审核或发送现有草稿。手机覆盖批量选择、导航焦点与分页可达性，流程支持撤销和离开保护。完整文件、证据、限制和复测命令见 [ui-upgrade.md](ui-upgrade.md)。

旧 `scripts/browser_smoke.py` 保留初次缺 Key 场景，当前已配置真实 Key，运行新版 UI 脚本。
