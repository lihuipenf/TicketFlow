# TicketFlow

本地部署的电商客服智能工单工作台：咨询接入 → 脱敏 → 意图/优先级规则 → 订单只读查询 → Qwen Embedding / Milvus Lite / BM25 / RRF → LLM 回复建议 → 引用校验 → 人工确认 → 模拟渠道发送。

**项目路径：`D:\agent ai\TicketFlow`。2026-11-11 已配置 DeepSeek 官方接口，真实本地 RAG → DeepSeek 回复生成 → 引用校验联调通过，生成工单保留待人工审核。**

## 在当前电脑启动

依赖、独立 MySQL 数据库、模型缓存和初始知识已准备好。PowerShell 中执行：

```powershell
Set-Location 'D:\agent ai\TicketFlow'
.\scripts\dev.ps1
```

- 工作台：<http://127.0.0.1:5173>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>
- 账号：`admin`、`supervisor`、`agent`、`knowledge`，分别对应管理员、主管、客服、知识管理员。
- 本地模拟账号初始密码统一读取项目 `.env` 的 `ADMIN_PASSWORD`。脚本不会打印密码，勿将 `.env` 发到聊天或提交 Git。
- `agent` 只可查看分配给自己的工单；管理员可批量分配。`knowledge` 进入知识管理页面。
- 独立 MySQL 使用 `127.0.0.1:3307`，数据位于项目 `data/mysql`；不会修改原有 `MySQL80` 服务。

启动脚本发现 8000/5173 被占用会停止并提示，不会抢占别的服务。停止本脚本启动的 API、Worker 和前端：

```powershell
.\scripts\stop.ps1
```

MySQL 保留运行，所有数据保留。修改 `.env` 后先停止再启动 API/Worker，配置才会重新加载。单独调试时可用三个终端：

```powershell
# 终端1，项目根目录
. .\scripts\env.ps1
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 终端2
. .\scripts\env.ps1
Set-Location backend
..\.venv\Scripts\python -m app.worker

# 终端3，项目根目录
. .\scripts\env.ps1
Set-Location frontend
npm run dev
```

## 模型配置

当前本地使用 DeepSeek（已验证），`.env.example` 保留无密钥示例：

```dotenv
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=在本地填写你的有效DeepSeek密钥
LLM_API_MODE=chat
```

服务商的 Key 必须与接口地址匹配。DeepSeek Key 不能用于阿里云百炼地址。2026-11-11 真实工单检索6个片段、生成4条有效引用，用量2663 tokens，模型调用约8秒；工单标题为“真实模型联调：未发货退款（2026-11-11）”。

如切换到阿里云百炼，可编辑 `.env` 配置如下；不要改 `.env.example` 中的占位符作为实际密钥：

```dotenv
LLM_PROVIDER=qwen
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-plus
LLM_API_KEY=在本地填写你的有效密钥
LLM_API_MODE=chat
```

Base URL 需匹配账户地域和服务商。DeepSeek/OpenAI 可更改 provider、base_url 和实际可用 model ID；OpenAI Responses 路径使用 `LLM_API_MODE=responses`。具体模型及账户是否支持 JSON 输出、接口参数，需要真实凭据联调。`codex` 不是本项目内置的通用模型 ID。

重启后选择一个未回复工单，点击“运行智能处理”。缺少 Key 会保留真实检索证据并显示错误，不会生成假回复。模型返回的引用 ID 和引文须通过校验，随后客服编辑、确认，再点击“发送到模拟渠道”。订单或知识版本变化会阻止旧草稿审核/发送。P0 需要主管确认。

## 功能与操作

1. **工单中心**：分页、搜索、状态/优先级筛选、批量分配、创建工单、执行/重试处理、查看轨迹与引用、人工审核/升级/请求补充/发送。
2. **知识库**：上传 PDF/Markdown/TXT，后台解析与向量化；预览来源片段；构建完成后发布；上传新版本、回滚、停用。
3. **检索实验室**：真实 Qwen 查询向量、Milvus 召回、BM25 候选、RRF 融合、耗时及来源展示，不消耗外部生成模型 API。
4. **流程配置**：固定工作流的可视化、两路 Top K、最终片段数、相似度阈值、切块/重叠/上下文字符预算、P1 关键词；配置版本随任务保存。
5. **运行日志**：阶段耗时、任务成功率、实际模型 Token、意图与状态图表、审计记录、失败重试。
6. **模拟订单**：50 条订单及实时状态查询。历史工单500条、FAQ20条；浏览器验证额外创建的工单保留并带“浏览器联调”标题。

示例：客户 `C002`，订单 `TF20260002`，咨询“订单还没发货，可以申请退款吗？”；请勿使用不属于客户的订单，系统会拒绝关联。

## 验证

```powershell
Set-Location 'D:\agent ai\TicketFlow'
.\scripts\doctor.ps1
.\scripts\verify.ps1

# API、Worker、前端运行时，执行真实 RAG 小样本评测
.\.venv\Scripts\python scripts/evaluate_rag.py

# 当前电脑专用浏览器测试环境（不创建或修改工单）
. .\scripts\env.ps1
& 'D:\CodexData\tools\webapp-testing\.venv\Scripts\python.exe' scripts/ui_upgrade_smoke.py
& 'D:\CodexData\tools\webapp-testing\.venv\Scripts\python.exe' scripts/ui_detail_races.py
# 可选：真实本地向量与 BM25 检索，会新增一条检索任务，不调用回复模型
& 'D:\CodexData\tools\webapp-testing\.venv\Scripts\python.exe' scripts/ui_retrieval_smoke.py
```

新版界面验证使用现有待审核工单，覆盖五个页面、快捷搜索、状态筛选、移动布局、权限和编辑保护；不自动生成、审核或发送回复。旧 `scripts/browser_smoke.py` 保留初次交付时“未配置 Key”的历史场景，不适用于当前已配置真实 Key 的环境。完整成功生成→审核→发送的业务路径另有自动化集成测试；其中只有外部模型 HTTP 响应和检索边界使用明确的测试夹具，生产代码没有伪造模型后备。

后端测试连接独立 `ticketflow_test` 库，自动隔离真实 LLM 凭据，避免测试意外调用付费接口。`TEST_DATABASE_URL` 可覆盖；测试会创建测试表与少量并发验证数据，不应指向业务库。首次准备本机测试库：

```powershell
.\.venv\Scripts\python scripts/prepare_test_db.py
```

详细结果见 [docs/verification.md](docs/verification.md)，评测原始结果和截图在忽略 Git 的 `data/verification/`。

## 从干净环境安装

当前实测 Python 3.12、Node 26、MySQL 8.0.40、Windows。需要现有 MySQL 实例及其专用数据库/用户，或安装 MySQL 后按下面独立实例方式准备。所有包缓存与模型权重放 D 盘。

```powershell
. .\scripts\env.ps1
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python -m pip install -e backend
Set-Location frontend
npm ci
Set-Location ..
```

通用部署：复制 `.env.example` 为 `.env`，填写专用 `DATABASE_URL`、至少32字符随机 JWT_SECRET、至少12字符 ADMIN_PASSWORD。不要覆盖已有 `.env`。

当前电脑的独立实例引导（**仅首次、没有 `.env` 且没有已有数据目录时**）：

```powershell
New-Item -ItemType Directory -Force data/mysql,data/logs | Out-Null
& 'D:/mysql/bin/mysqld.exe' --no-defaults --initialize-insecure '--basedir=D:/mysql' '--datadir=D:/agent ai/TicketFlow/data/mysql' '--log-error=D:/agent ai/TicketFlow/data/logs/mysql-init.log'
.\scripts\mysql.ps1
.\.venv\Scripts\python scripts/bootstrap_db.py
.\.venv\Scripts\python scripts/prepare_test_db.py
```

引导只连接3307，将初始空密码账户改为随机密码，生成应用专用用户和忽略 Git 的 `.env`。不要对已有 MySQL 数据目录重复初始化。

迁移和种子数据：

```powershell
Set-Location backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m app.seed --knowledge
Set-Location ..
.\scripts\dev.ps1
```

初始化幂等，不覆盖已存在的模拟订单/工单。运行 Worker 后等待知识构建完成，在知识库页面点击“发布版本”。模型首次下载可能较慢；CPU 能运行，硬件影响速度。

## 项目边界

- 单企业、单 Worker 的本地业务系统。订单、客户渠道为模拟系统，未接入淘宝/京东/真实退款支付接口。
- 意图和优先级第一版使用可解释规则；LLM负责带证据回复生成。可扩展分类模型，不把规则结果冒充 LLM 分类。
- 文档切块采用标题/段落/句子边界及**字符预算**，不是语义聚类或精确 Token 切块。模型输入有长度上限。
- 扫描 PDF、图片及复杂表格 OCR 不在第一版；无文字页明确报错，需要先 OCR。
- 证据充分度是启发式评分，不是答案正确概率；引用逐字匹配不等于语义真实性，仍需人工复核。
- 脱敏覆盖常见手机号、邮箱、身份证号、显式地址字段；真实客户上线前应补充业务专用敏感信息识别与脱敏评测。
- 生产上线还需企业身份、密码管理、HTTPS/限流、备份恢复、业务 SLA、真实渠道适配与容量测试；本地共享初始演示密码不适用于生产。
- 不自动退款、不自动赔付、不自动修改订单，不执行文档或模型中的指令。

架构和数据说明：[docs/architecture.md](docs/architecture.md)。API说明：[docs/api.md](docs/api.md)。运行维护：[docs/operations.md](docs/operations.md)。

## 浅色工作台与交互升级

已接入 `motion-v@2.12.0`，使用 UI UX Pro Max、Impeccable 与 Vue Interaction Toolkit 的设计约束，统一登录、工单、知识库、流程、日志、订单页面。整体采用浅色界面与绿色主操作，支持 Ctrl / Command + K 搜索页面和工单、状态快捷筛选、手机卡片与批量选择、审核证据页签、流程修改提示和撤销。共享元素动效遵循系统减少动态效果的偏好。

设计规范见 [DESIGN.md](DESIGN.md)，升级范围、文件和验证方法见 [docs/ui-upgrade.md](docs/ui-upgrade.md)。启动后访问 http://127.0.0.1:5173；运行 `scripts/dev.ps1` 可启动本地服务。
