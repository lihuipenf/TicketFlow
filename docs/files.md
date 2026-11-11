# 交付文件清单

根目录：README.md、AGENTS.md、.env.example、.gitignore。实际.env仅存本地且被Git忽略。

## 后端

- backend/pyproject.toml、requirements.lock.txt：依赖与本机验证版本锁。
- backend/alembic.ini、migrations/env.py、migrations/versions/0001_initial.py：数据库迁移。
- backend/app/main.py、api.py：FastAPI入口与业务接口。
- backend/app/config.py、db.py、auth.py：配置、数据库表及认证权限。
- backend/app/services.py：工单、任务、审核、发送、知识发布事务。
- backend/app/rag.py：文档解析、来源切块、Qwen、Milvus、BM25、RRF。
- backend/app/llm.py、policy.py：供应商适配、脱敏、意图优先级和引用校验。
- backend/app/worker.py：持久化执行、租约、心跳、重试、日志。
- backend/app/seed.py：50订单、20FAQ、500历史工单及文档样例初始化。
- backend/tests/：健康、API、RAG、业务、Worker、种子、真实Milvus、脱敏和MySQL并发测试。

## 前端

- frontend/package.json、package-lock.json、vite.config.ts、tsconfig.json、index.html。
- frontend/src/App.vue、style.css：登录、导航、响应式工作台。
- frontend/src/main.ts、router.ts、api.ts、stores/session.ts：入口、路由、接口和会话。
- frontend/src/views/Tickets.vue：工单列表、详情、审核工作台。
- frontend/src/views/Knowledge.vue：知识管理、片段、版本和检索实验室。
- frontend/src/views/Workflow.vue：流程可视化与配置。
- frontend/src/views/Logs.vue：统计图表、任务轨迹、审计。
- frontend/src/views/Orders.vue：模拟订单。
- frontend/src/components/StatusBadge.vue、Chart.vue：状态与图表。
- frontend/tests/status.test.ts：审核与发送状态语义验证。

## 脚本与样例

- scripts/env.ps1：D盘临时/缓存环境。
- scripts/mysql.ps1、bootstrap_db.py、prepare_test_db.py：独立数据库启动/首次初始化/测试库。
- scripts/dev.ps1、stop.ps1、doctor.ps1、verify.ps1：启停、检查、验证。
- scripts/browser_smoke.py、evaluate_rag.py：浏览器业务验证、真实检索评测。
- fixtures/knowledge/：Markdown政策、TXT物流说明、两页PDF审核流程。
- fixtures/evaluation/retrieval.json：20条改写问题与标注章节。
- docs/architecture.md、api.md、operations.md、verification.md：架构、接口、运行维护、验证证据。

## 本地生成产物（忽略Git）

data/mysql、uploads、milvus、bm25、logs、verification；.venv；frontend/node_modules、dist。
模型权重在D:/CodexData/caches/huggingface，未复制进代码仓库。
