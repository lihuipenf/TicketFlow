# API 概览

实时契约：启动服务后打开 http://127.0.0.1:8000/docs。

前缀 `/api/v1`，登录之外的业务接口均需要 `Authorization: Bearer <token>`。密钥只在服务器 `.env` 使用。

| 方法与路径 | 用途 |
|---|---|
| POST /auth/login; GET /auth/me | 登录/身份 |
| GET /health; GET /system/status | 存活/已认证配置状态 |
| GET, POST /tickets | 分页搜索/创建 |
| GET /tickets/{id} | 详情、订单、处理轨迹与审计 |
| POST /tickets/{id}/runs | 提交处理，body含revision；202返回job |
| POST /tickets/{id}/reviews | revision、action、text；动作approve/reject/escalate/request_information |
| POST /tickets/{id}/send | 已确认版本发送到模拟渠道 |
| POST /tickets/assign/batch | 主管批量分配，ticket_ids、user_id |
| GET /users | 可分配账号列表 |
| GET /orders; GET /orders/{id} | 主管列表/有权限订单详情 |
| GET, POST /knowledge/documents | 文档含版本列表 / multipart上传file及可选document_id |
| GET /knowledge/versions/{id}/chunks | 片段及来源预览 |
| POST /knowledge/versions/{id}/publish | 发布或回滚已构建版本 |
| POST /knowledge/documents/{id}/disable | 停用文档，保留历史 |
| POST /retrieval-tests | query，返回异步job |
| GET /jobs/{id}; POST /jobs/{id}/retry | 任务结果/失败重试 |
| GET, PUT /workflow/config | 读取/发布新配置 |
| GET /analytics/overview | 可见工单统计、最近100任务运行统计 |
| GET /runs; GET /audit-events | 主管执行记录/审计 |

工单列表query参数：q、status、priority、intent、page、page_size（1–100）。响应items与total。

创建示例：`{"subject":"退款咨询","content":"还没发货可以退款吗？","customer_id":"C002","order_id":"TF20260002"}`。

工单处理与审核传入当前revision；并发过期返回409。401需重新登录，403为角色/资源权限不匹配，413超上传大小，415不支持格式，422输入无效。未知服务错误不返回堆栈，附trace_id；普通响应有X-Trace-ID。

不对外提供真实退款、赔付、取消订单执行接口。发送仅向工单的模拟渠道记录字段提交。
