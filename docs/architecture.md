# TicketFlow 实现架构

## 运行单元

Vue3/TypeScript/Vite/ElementPlus/Pinia/Router → FastAPI → MySQL 持久化任务队列 → 单 Worker。
Worker 独占 Milvus Lite；知识导入、检索测试、工单处理均为数据库任务。使用文件锁防止两个 Worker 同时访问嵌入式向量文件。

FastAPI管理认证、权限、工单、审核、知识发布和配置。Worker管理解析、切块、本地Embedding、Milvus/BM25、RRF、模型调用及规则校验。MySQL是业务事实来源，向量和BM25是可重建的衍生数据。

## 代码地图

| 文件 | 职责 |
|---|---|
| backend/app/config.py | `.env`、SecretStr、数据目录 |
| backend/app/db.py | ORM表、会话和UTC时间 |
| backend/app/auth.py | Argon2密码、JWT、角色依赖 |
| backend/app/api.py | HTTP契约、校验、分页、权限 |
| backend/app/services.py | 事务、审核、发送、上传、版本发布 |
| backend/app/policy.py | 脱敏树、意图优先级、引用/风险校验 |
| backend/app/rag.py | 三格式解析、带来源切块、Embedding、双召回、RRF |
| backend/app/llm.py | OpenAI SDK Chat/Responses适配与结构化输出 |
| backend/app/worker.py | 租约、心跳、恢复、步骤日志、任务执行 |
| backend/app/seed.py | 合成订单、历史工单、FAQ、评测样例 |
| frontend/src/views/ | 五个业务页面及审核抽屉 |

初版按模块文件组织，尚未扩展到设计中的多层目录；随体量拆包，避免空文件夹和空接口。

## RAG

PDF使用pypdf，逐页标记；Markdown跟踪标题树和正文原行号；TXT记录段落及行号。正文、来源标题和文件名脱敏。超长段落优先在句子边界切分，带重叠；ID由版本、序号和内容SHA256生成。

Qwen3-Embedding-0.6B本地SentenceTransformer，查询使用任务指令，文档不加查询指令。归一化1024维向量；Milvus FLAT/COSINE。每个版本保存词法快照JSON，检索时用中文分词与BM25重建小规模词法排序。样例规模不需要独立搜索服务。

两路默认各Top20，向量过滤最低余弦0.4；RRF k=60等权，去除同通道重复ID，最终最多6片段，字符预算6500。相同知识代次用于向量过滤和词法读取；最终结果重新按该版本快照ID校验，避免误用其他版本。

入库原文文件、正文片段、来源、向量、词法快照均可追踪。版本发布只有在全部构建完成后才进行；切换Document.active_version完成发布/回滚。历史回复保存引用原文快照。停用后不进入新检索。

## 工作流与并发

业务状态：new → pending_review → approved → replied；审核还可到escalated、needs_information或退回new。
执行状态：queued → running → succeeded/failed。临时模型连接/限流错误最多自动尝试3次。

任务键唯一，按工单ID+revision去重；Worker每20秒续租，租期3分钟，宕机后恢复过期租约。最终草稿写入使用工单行锁和revision校验，旧任务不能覆盖新工单。用户修改/分配会使旧审核失效。

审核与发送锁住工单、当前订单及知识文档，使用MySQL当前锁定读而非旧REPEATABLE READ快照。依赖锁持有至提交，防止知识发布/订单变化穿过审核窗口。模拟发送在同一数据库事务中完成，重复发送返回既有结果。

## 数据表

users：账号、哈希、角色。
orders：客户关联、商品、金额分、实时状态、事实JSON、revision。
tickets：脱敏咨询、状态、优先级、分配、draft/approved/sent、revision。
knowledge_documents / document_versions / knowledge_chunks：发布指针、版本、来源片段。
jobs：幂等键、执行状态、租约、attempts、步骤、检索与回答结果。
audit_events：审核修改、分配、发布、发送、重试记录。
workflow_configs：不可变配置版本。

初版将对话初始咨询和回复存于工单，执行步骤/检索命中存在任务JSON中，订单商品/物流事实存在订单JSON中；没有为每种嵌套数据单独建表。多轮会话、复杂商品明细、长期高吞吐分析时应按实际需求拆表。

## 安全边界

客服只能访问本人分配工单及关联订单；主管/管理员管理工单和配置；知识管理员管理知识。模型只得到脱敏后的问题、只读订单事实和证据；没有可执行资金/订单工具。所有生成都经引用ID、逐字引文、敏感信息与承诺规则检查，必须人工确认。

模型异常不保存原始响应。Pydantic校验错误统一摘要，避免input_value进入日志。外部知识是不可信资料；提示明确不遵循其中指令，工具权限在服务端实施。

## 扩展

生产扩容可将Milvus Lite替换为服务端Milvus、词法召回改为专门服务、任务队列改为独立Broker。需同时重新评估锁、租约、限流和索引代次；不能仅增加Worker进程数。
