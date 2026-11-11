# TicketFlow 视觉与交互升级 · 2026-11-11

用户选择：更明亮简洁，以浅色工作台为主。沿用 Vue 3、Vite、Element Plus，新增项目依赖 `motion-v@2.12.0`，使用已安装的 UI UX Pro Max、Impeccable、Vue Interaction Toolkit 技能。没有为此次升级引入额外 UI 框架或动画引擎。

## 界面与操作

- 登录及全局框架：白色侧栏与顶部导航、浅灰内容区、绿色操作重点；统一字体、留白、边框、对比度和焦点样式。
- 快捷搜索：Ctrl / Command + K，按权限搜索页面和工单；支持方向键、Enter、Escape、输入法组词保护、防抖与过期请求取消。工单结果直接打开审核详情。
- 工单：真实状态计数和快捷切换，默认每页 12 条，可改为 24 / 48 条；手机卡片保留主管批量选择分配。审核详情分为回复、证据、轨迹，增加复制回复；确认与发送仍是不同操作。
- 知识库：文件选择与拖入上传、格式与大小提示、知识版本和来源预览；检索实验室保留真实向量、BM25、RRF 结果，RRF 排序分数不表示准确率。
- 流程：可选择节点查看职责；未发布修改提示、撤销、离开时保护，保存期间禁止修改表单。
- 日志与订单：统一数据表和图表颜色，保留实际统计口径与模拟数据标识。
- 动效：侧栏选中背景、队列下划线、流程节点共享元素过渡；页面短淡入淡出。MotionConfig 设置 reducedMotion=user，CSS 与图表也适配减少动态效果。
- 手机：折叠导航具备焦点限制和返回、关闭时 inert，卡片列表与可达分页，五个页面无整页横向溢出。

## 主要文件

| 文件 | 用途 |
|---|---|
| PRODUCT.md / DESIGN.md | 产品边界与浅色工作台设计约束 |
| frontend/src/App.vue / style.css | 登录、导航、全局布局与 Element Plus 主题 |
| frontend/src/main.ts | 按需注册 Element Plus，保留中文语言配置 |
| frontend/src/navigation.ts | 权限导航、关键词匹配、键盘快捷键 |
| frontend/src/components/CommandPalette.vue | 页面与工单快捷搜索 |
| frontend/src/components/StatusTabs.vue / BrandMark.vue | 状态切换动效、品牌标记 |
| frontend/src/components/Chart.vue | 图表文字颜色与减少动态效果支持 |
| frontend/src/views/*.vue | 五个业务页面的视觉和交互升级 |
| frontend/tests/navigation.test.ts / status-tabs.test.ts | 角色、搜索、输入法快捷键、零计数和筛选测试 |
| scripts/ui_upgrade_smoke.py | 真实服务上的只读 UI 验证 |
| scripts/ui_detail_races.py | 隔离模拟 API 的两项详情请求竞争回归 |
| scripts/ui_retrieval_smoke.py | 真实本地混合检索的界面验证 |

## 验证结果

- 后端 pytest：32 项通过；前端 Vitest：6 项通过；TypeScript 检查及 Vite 生产构建通过；npm audit 0 个已知漏洞。
- 浏览器：登录、五个页面、状态筛选、12 条分页、已有草稿和证据、快捷搜索键盘操作、流程修改撤销和离开保护、手机批量选择、导航焦点、可达分页、角色跳转和无结果状态通过，无 JS 异常。
- 正常动态效果模式：采样确认状态选中下划线发生真实共享元素位移；系统减少动态效果模式下复测了页面功能。
- 异步回归：取消详情导航后旧请求不能重新打开抽屉；A 工单的过期轮询不能覆盖 B 工单编辑内容。模拟请求中移除防护会复现失败，当前代码通过。
- 真实本地混合检索：本次命中 6 个证据、20 个向量候选、14 个 BM25 候选，检索报告 1894 ms（不含排队时间）。结果及三个检索页签验证通过，未调用回复模型。
- 本轮没有生成新回复、确认或发送现有草稿。UI 检索验证只新增检索任务记录。
- Element Plus 改为按需注册后，主入口 JS 约从 1.21 MB 降至 0.66 MB（构建原始大小，gzip 约 403 KB → 231 KB）；仍有大于 500 KB 的 Element Plus 主入口和 ECharts 日志页 chunk 提示。图表按页面加载，尚未做按组件 CSS 分包或大规模性能基准。
- Impeccable 手动扫描仅报告 Inter 字体偏好警告；已移除未加载的 Inter 候选，使用系统字体。界面已实际检查桌面与手机截图。

截图：`data/verification/ui-upgrade/after/`，包括 tickets-preview.png、login.png、ticket-review.png、knowledge-retrieval.png、workflow.png、logs.png 和各手机页面。

## 运行与复测

PowerShell 在项目根目录执行：

```powershell
Set-Location 'D:\agent ai\TicketFlow'
. ./scripts/env.ps1
./scripts/dev.ps1
# 浏览器：http://127.0.0.1:5173
./scripts/verify.ps1
& 'D:\CodexData\tools\webapp-testing\.venv\Scripts\python.exe' scripts/ui_upgrade_smoke.py
& 'D:\CodexData\tools\webapp-testing\.venv\Scripts\python.exe' scripts/ui_detail_races.py
# 可选：新增检索测试任务，只使用本地嵌入和索引
& 'D:\CodexData\tools\webapp-testing\.venv\Scripts\python.exe' scripts/ui_retrieval_smoke.py
```

真实 UI 脚本从本地 .env 读取演示登录密码，不打印凭据。只读 UI 脚本需要至少一份现有待审核草稿和已初始化知识库；当前演示环境满足此条件。竞争回归脚本只需 Vite，不连接后端或读取 .env。旧 browser_smoke.py 是缺少 API Key 时的历史脚本，请使用上述新版命令。

升级前前端备份保留在 `D:\CodexData\temp\TicketFlow-before-ui-20261111-142201.zip`。未删除业务数据或迁移备份。

实现参考：[MotionConfig](https://motion.dev/docs/vue-motion-config)、[共享元素布局过渡](https://motion.dev/docs/vue-layout-animations)。
