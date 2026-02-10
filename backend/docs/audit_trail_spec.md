# 审计链路与可追溯性规范

## 统一审计字段

| 字段 | 说明 |
|------|------|
| id | 主键 |
| user_id | 操作人（可选，未登录为 null） |
| action | 操作类型：login, logout, upload, delete, review, compare, chat, export, llm_call |
| resource_type | 资源类型：contract, review, comparison, chat |
| resource_id | 资源 ID |
| provider | LLM 提供商（仅 llm_call） |
| model | 模型名（仅 llm_call） |
| tokens_input, tokens_output, duration_ms, cost | 调用统计（仅 llm_call） |
| ip_address | 请求 IP |
| user_agent | User-Agent 截断 |
| extra_data | 扩展数据（含 trace_id, input_summary, purpose 等；禁止敏感原文） |
| success | 是否成功 |
| error_message | 错误信息（若有） |
| created_at | 时间戳 |

## 保留与清理

- 审计日志保留 1 年（DATA_RETENTION_DAYS=365）。
- 到期自动清理由定时任务执行。

## 取证导出流程

1. 管理员或合规角色调用 `GET /api/audit/export?from=...&to=...&format=csv|json`。
2. 服务端按时间范围筛选，生成文件并返回（或写存储后返回下载链接）。
3. 导出内容仅包含上述字段，不含请求/响应正文。
