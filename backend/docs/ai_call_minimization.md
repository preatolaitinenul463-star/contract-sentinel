# AI 调用隔离与数据最小化规范

## 原则
- 所有发往外部 LLM 的文本必须经脱敏管道（`mask_text_for_llm_input`）。
- 每次调用记录 `trace_id`、输入摘要（长度/哈希）、用途，写入审计日志。
- LLM 返回的条款引用、建议等需经 `mask_llm_output` 再落库或展示。

## 审计字段（每次 LLM 调用）
- trace_id: 唯一追踪 ID（UUID 或 request_id）
- purpose: review | compare | assistant
- input_summary: 字符数或 hash，不落原文
- provider, model, tokens_input, tokens_output, duration_ms

## 输出再脱敏
- 助理回复：写入 ChatMessage 前对 content 做 mask_llm_output。
- 审核结果：risk_items 的 clause_text、suggestion 写入 ReviewResult 前做 mask_llm_output。
- 对比结果：changes 中的 original_text、new_text、analysis 可做 mask_llm_output。
