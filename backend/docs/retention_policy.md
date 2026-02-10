# 数据保留与自动清理策略

## TTL 规则

| 数据 | 保留期限 | 说明 |
|------|----------|------|
| 合同 (contracts) | DATA_RETENTION_DAYS（默认 365 天） | 按 created_at 过期删除 |
| 审核结果 (review_results) | 同上 | 随合同或独立按 created_at |
| 对比结果 (comparison_results) | 同上 | 按 created_at |
| 聊天会话与消息 (chat_sessions, chat_messages) | 同上 | 按 created_at |
| RAG 文档与片段 (rag_documents, rag_chunks) | 同上 | 按 last_crawled_at / created_at |
| 审计日志 (audit_logs) | 同上 | 按 created_at |

## 清理作业

- 执行入口：`python -m app.tasks.retention`（或由 cron / 托管平台定时任务调用）。
- 建议频率：每日一次。
- 逻辑：查询各表 created_at（或等效时间字段）早于 (now - DATA_RETENTION_DAYS) 的记录并删除；审计表按 created_at 清理。
