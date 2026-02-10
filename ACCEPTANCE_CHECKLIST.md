# 合同哨兵 重型版 验收清单

## 部署验收
- [ ] `docker-compose up -d` 一键启动全部服务（含 Grafana 栈）
- [ ] `/health` 返回 `{"status": "healthy"}`
- [ ] `/api/health/detail` 显示 database=healthy, redis=healthy/unavailable
- [ ] Grafana 可访问 (`http://localhost:3001`, admin/sentinel123)
- [ ] Grafana 数据源（Prometheus/Loki/Tempo）已自动配置
- [ ] Grafana dashboard "Contract Sentinel - Overview" 已预置

## 法律助手 (assistant)
- [ ] 四种模式可切换：法律问答 / 案件分析 / 合同审查 / 文书起草
- [ ] 流式输出正常（SSE token 逐字显示）
- [ ] 来源卡片展示：官方（绿色锁图标）/ 参考（黄色地球图标）
- [ ] 脚注 [S1] [S2] 在正文中渲染为可视 badge
- [ ] 验证状态 badge 显示（验证通过 / 部分降级 / 待人工复核）
- [ ] 无官方源时自动降级并提示"未命中官方法规源"
- [ ] DOCX 导出按钮可用（含 sources 附录）
- [ ] 文件上传（PDF/Word/图片）正常解析
- [ ] 会话管理正常（新建/切换/删除）

## 合同审核 (review)
- [ ] SSE 流水线完整（文档解析→结构化→规则→法规检索→深度审核→修改建议）
- [ ] 风险项可展开查看详情
- [ ] run_id 在 SSE 事件中返回
- [ ] verification_decision 在完成事件中返回
- [ ] 导出 Word/PDF 正常

## 批阅/批注 (redline)
- [ ] 批注版 Word 生成正常
- [ ] run_id 在 SSE 事件中返回
- [ ] ClauseLocateVerify 生效：定位失败时进入人工复核
- [ ] verification_decision 在完成事件中返回

## 审阅工作台 (oversight)
- [ ] 侧边栏出现"审阅工作台"入口
- [ ] 运行列表正常加载（按功能/状态筛选）
- [ ] 展开详情：来源/验证结果/事件时间线全部可见
- [ ] 通过/驳回操作正常
- [ ] 备注可输入并保存
- [ ] 审批动作写入审计日志

## 可观测性 (Observability)
- [ ] OpenTelemetry 初始化日志出现（或"disabled"提示）
- [ ] SSE 事件带 run_id
- [ ] Pipeline runs 写入 pipeline_runs 表
- [ ] Pipeline events 写入 pipeline_events 表
- [ ] Provenance sources 写入 provenance_sources 表
- [ ] Verification results 写入 verification_results 表
- [ ] Grafana Tempo 可追踪 traces（需 OTEL_EXPORTER_OTLP_ENDPOINT 配置）

## 安全加固
- [ ] Markdown 链接：仅 http/https 协议渲染为可点击链接
- [ ] Markdown 链接：javascript: / data: 等协议被过滤为纯文本
- [ ] SSE 不泄露 AI 模型名称
- [ ] 免责声明在助手输出末尾存在
- [ ] 搜索结果缓存生效（Redis 可用时走 Redis，否则内存 LRU）

## 数据库
- [ ] 新增表存在：pipeline_runs, pipeline_events, provenance_sources, verification_results, approval_tasks
- [ ] Alembic 迁移脚本可执行

## 存储
- [ ] 默认 LocalBackend 可用
- [ ] StorageBackend 抽象层存在（S3Compatible 为占位）

## 性能基准（参考）
- [ ] 法律助手 QA 端到端 < 120s
- [ ] AgentSearch 检索 + 抓取 < 30s
- [ ] 审核 SSE 流水线 < 180s
