# 验证记录

## 2026-11-12 四项高危修复验证（最新）

用户授权修复审查报告 H01-H04，未执行 Git 操作，未调用真实生成模型，未修改现有工单、订单或知识库内容。

- **后端完整回归：72 passed，11.44秒。** 包含13项无连接测试隔离检查、13项上传入口回归，以及真实专用MySQL库上的API/业务/种子账号/并发与Milvus测试。测试进程清空真实LLM Key，外部模型成功路径仍使用明确的HTTP测试夹具。
- **前端：6 passed；vue-tsc 和 Vite 构建成功；npm audit 0 已知漏洞。** 仍有既有的大于500kB构建块提示，未在安全修复中修改前端布局或打包策略。
- **真实HTTP冒烟通过**：使用实际 `.env` 凭据，在临时本机端口启动当前API，验证四角色登录、客服密码不能登录管理员、旧格式JWT被拒绝；只发送上传请求头、不发送正文，即收到401（未登录）、403（客服无上传角色）、413（声明超限）和429（并发满）。临时API已退出，无业务写入、上传入库、任务入队或模型调用。
- **现有账号已迁移**：四个固定账号全部改用独立随机密码，包括管理员；新值仅写入本地 `.env`。核验旧共享密码对四者均无效，API Key、模型配置、JWT密钥及业务数据库地址保持原值。独立测试DSN另行写入 `.env`。
- **数据库权限实测**：用专用测试账号尝试只读访问业务 users 表，被MySQL拒绝；在建表前校验测试账号没有全局/跨库/角色权限。增加预先缓存业务引擎的进程级回归，确认在建立连接前被拒绝。
- **独立复审**：发现并修复上传鉴权线程在超时后继续持有连接的容量缺口。线程现在自行持有独立的并发额度，HTTP请求超时或取消不能提前释放线程额度；连接读写使用有限socket超时。独立审核人验证了13项上传入口回归，无遗留的本批Critical/Important/Minor问题。

关键回归先确认失败再修复：错误DSN仍尝试创建引擎、客服自建关联工单返回201、共享密码未分离/旧会话仍有效、未登录上传先读取body，以及鉴权超时/取消后产生多个活跃后台线程。均已补充自动化保护。

复现：

```powershell
Set-Location 'D:\agent ai\TicketFlow'
. .\scripts\env.ps1
# 本机首次准备/修复专用测试账号；保留数据，不打印凭据
.\.venv\Scripts\python scripts/prepare_test_db.py
# 后端、前端、构建及npm审计
.\scripts\verify.ps1
# 临时API真实HTTP验证，完成后自动退出；不改业务数据
.\.venv\Scripts\python -B scripts/security_smoke.py
```

新实现/主要修改文件：

| 部分 | 文件 |
| --- | --- |
| 测试隔离 | `backend/app/database_safety.py`、`backend/tests/conftest.py`、`backend/safety_tests/test_database_isolation.py`、`scripts/prepare_test_db.py` |
| 订单权限 | `backend/app/services.py`、`backend/app/api.py`、`backend/tests/test_api.py` |
| 独立凭据与会话撤销 | `backend/app/accounts.py`、`backend/app/auth.py`、`backend/app/seed.py`、`backend/tests/test_seed.py`、`scripts/secure_accounts.py`、`scripts/bootstrap_db.py` |
| 上传入口 | `backend/app/ingress.py`、`backend/app/main.py`、`backend/app/config.py`、`backend/app/db.py`、`backend/tests/test_upload_ingress.py` |
| 配置/验证适配 | `.env.example`、`backend/pyproject.toml`、`scripts/security_smoke.py`、`scripts/browser_smoke.py`、`scripts/ui_upgrade_smoke.py` |
| 说明与原报告状态 | `README.md`、`docs/operations.md`、`docs/verification.md`、`REVIEW_REPORT.md` |

本次没有重做真实LLM质量评测、生产压力/故障恢复测试、外部Nginx部署或Git历史扫描，也没有运行浏览器UI端到端测试。原报告M/L事项保留为后续计划；本次结论仅覆盖授权的四项高危整改，不是整个系统的生产安全认证。

## 2026-11-11 DeepSeek 真实模型联调通过（历史记录）

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
