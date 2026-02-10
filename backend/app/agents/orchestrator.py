"""Orchestrator - coordinates the agent pipeline (ValueCell 模式).

多 Agent 协作流程：
1. DocIngestAgent: 文档解析（PDF/DOCX/图片 → 文本）
2. ClauseStructAgent: 条款结构化（提取当事人、日期、金额等）
3. RuleEngineAgent: 规则预筛（基于规则包快速检查）
4. LLMReviewAgent: AI深度审核（DeepSeek 分析法律风险）
5. RedlineDraftAgent: 修改建议生成（生成具体修改文本）

各 Agent 职责明确，便于调试和优化。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncIterator
from datetime import datetime

from loguru import logger

from app.providers import get_provider_registry, ChatMessage


class TaskType(str, Enum):
    """Types of tasks the orchestrator can handle."""
    REVIEW = "review"
    COMPARE = "compare"
    ASSISTANT = "assistant"


@dataclass
class AgentStep:
    """Record of a single agent step in the pipeline."""
    agent_name: str
    status: str  # pending, running, completed, error
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tokens_used: int = 0
    result_summary: str = ""


@dataclass
class TaskResult:
    """Result of an orchestrated task."""
    success: bool
    data: Dict[str, Any]
    model_used: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    # 新增：Agent 执行记录
    agent_steps: List[AgentStep] = field(default_factory=list)


class Orchestrator:
    """
    Orchestrator - 协调多 Agent 流水线 (ValueCell 模式)
    
    核心设计思想：
    - 每个 Agent 只负责一个明确的任务
    - Agent 之间通过结构化数据传递信息
    - 规则引擎先行，LLM 后置（节省成本）
    - 完整的执行追踪和日志
    """
    
    def __init__(self):
        self.registry = get_provider_registry()
        # 延迟导入避免循环依赖
        from app.agents.llm_review import LLMReviewAgent
        from app.agents.redline_draft import RedlineDraftAgent
        self.llm_review_agent = LLMReviewAgent()
        self.redline_agent = RedlineDraftAgent()
    
    async def execute(
        self,
        task_type: TaskType,
        context: Dict[str, Any],
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> TaskResult:
        """Execute a task with the appropriate pipeline."""
        start_time = datetime.utcnow()
        
        try:
            if task_type == TaskType.REVIEW:
                result = await self._execute_review(context, provider_id, model)
            elif task_type == TaskType.COMPARE:
                result = await self._execute_compare(context, provider_id, model)
            elif task_type == TaskType.ASSISTANT:
                result = await self._execute_assistant(context, provider_id, model)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result.duration_ms = duration_ms
            return result
            
        except Exception as e:
            logger.exception(f"Task execution failed: {e}")
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return TaskResult(
                success=False,
                data={},
                duration_ms=duration_ms,
                error=str(e),
            )
    
    async def _execute_review(
        self,
        context: Dict[str, Any],
        provider_id: Optional[str],
        model: Optional[str],
    ) -> TaskResult:
        """
        Execute contract review pipeline (ValueCell 模式)
        
        Pipeline:
        1. LLMReviewAgent: 深度分析 → 识别风险
        2. RedlineDraftAgent: 生成修改建议（可选）
        """
        contract_text = context.get("text", "")
        contract_type = context.get("contract_type", "general")
        jurisdiction = context.get("jurisdiction", "CN")
        clauses = context.get("clauses")  # 来自 ClauseStructAgent
        rule_findings = context.get("rule_findings")  # 来自 RuleEngine
        generate_redlines = context.get("generate_redlines", True)
        
        agent_steps = []
        total_tokens_input = 0
        total_tokens_output = 0
        
        # ============================================
        # Step 1: LLM Review Agent - 深度审核
        # ============================================
        step1 = AgentStep(agent_name="LLMReviewAgent", status="running", start_time=datetime.utcnow())
        agent_steps.append(step1)
        
        try:
            review_result = await self.llm_review_agent.review(
                contract_text=contract_text,
                contract_type=contract_type,
                jurisdiction=jurisdiction,
                clauses=clauses,
                rule_findings=rule_findings,
                provider_id=provider_id or "deepseek",
                model=model or "deepseek-chat",
            )
            
            step1.status = "completed"
            step1.end_time = datetime.utcnow()
            step1.tokens_used = review_result.tokens_input + review_result.tokens_output
            step1.result_summary = f"发现 {len(review_result.risk_items)} 个风险项"
            
            total_tokens_input += review_result.tokens_input
            total_tokens_output += review_result.tokens_output
            
            # 转换风险项格式
            risk_items = []
            for item in review_result.risk_items:
                risk_items.append({
                    "severity": item.severity,
                    "name": item.name,
                    "description": item.description,
                    "clause_text": item.clause_text,
                    "suggestion": item.suggestion,
                    "legal_basis": item.legal_basis,
                    "confidence": item.confidence,
                    "source": "llm",
                })
            
        except Exception as e:
            step1.status = "error"
            step1.end_time = datetime.utcnow()
            step1.result_summary = str(e)
            logger.error(f"LLM Review failed: {e}")
            
            return TaskResult(
                success=False,
                data={},
                error=str(e),
                agent_steps=agent_steps,
            )
        
        # ============================================
        # Step 2: Redline Draft Agent - 生成修改建议
        # ============================================
        redlines = []
        modified_contract = contract_text
        
        if generate_redlines and risk_items:
            step2 = AgentStep(agent_name="RedlineDraftAgent", status="running", start_time=datetime.utcnow())
            agent_steps.append(step2)
            
            try:
                # 只对高风险和中风险生成修改建议
                high_medium_risks = [r for r in risk_items if r["severity"] in ("high", "medium")]
                
                if high_medium_risks:
                    redline_result = await self.redline_agent.generate_redlines(
                        contract_text=contract_text,
                        risk_items=high_medium_risks[:5],  # 最多处理5个
                        contract_type=contract_type,
                        jurisdiction=jurisdiction,
                        provider_id=provider_id or "deepseek",
                        model=model or "deepseek-chat",
                    )
                    
                    step2.status = "completed"
                    step2.end_time = datetime.utcnow()
                    step2.tokens_used = redline_result.tokens_input + redline_result.tokens_output
                    step2.result_summary = f"生成 {len(redline_result.redlines)} 处修改"
                    
                    total_tokens_input += redline_result.tokens_input
                    total_tokens_output += redline_result.tokens_output
                    
                    # 转换 redlines 格式
                    for rl in redline_result.redlines:
                        redlines.append({
                            "original": rl.original_text,
                            "modified": rl.modified_text,
                            "change_type": rl.change_type,
                            "reason": rl.reason,
                        })
                    
                    modified_contract = redline_result.modified_contract
                else:
                    step2.status = "skipped"
                    step2.result_summary = "无需生成修改建议"
                    
            except Exception as e:
                step2.status = "error"
                step2.end_time = datetime.utcnow()
                step2.result_summary = str(e)
                logger.warning(f"Redline generation failed: {e}")
        
        # ============================================
        # 汇总结果
        # ============================================
        return TaskResult(
            success=True,
            data={
                "risk_items": risk_items,
                "summary": review_result.summary,
                "overall_risk_level": review_result.overall_risk_level,
                "redlines": redlines,
                "modified_contract": modified_contract if redlines else None,
            },
            model_used=review_result.model_used,
            tokens_input=total_tokens_input,
            tokens_output=total_tokens_output,
            agent_steps=agent_steps,
        )
    
    async def _execute_compare(
        self,
        context: Dict[str, Any],
        provider_id: Optional[str],
        model: Optional[str],
    ) -> TaskResult:
        """Execute contract comparison pipeline."""
        text_a = context.get("text_a", "")
        text_b = context.get("text_b", "")
        
        chat_client = self.registry.get_chat_client(provider_id, model)
        
        system_prompt = """你是一位专业的法务合同对比专家。
请对比以下两份合同的差异，并分析变更带来的风险影响。

输出格式要求（JSON）：
{
  "changes": [
    {
      "change_type": "added/removed/modified",
      "clause_type": "条款类型",
      "original_text": "原文（如适用）",
      "new_text": "新文（如适用）",
      "risk_impact": "increased/decreased/neutral",
      "analysis": "变更影响分析"
    }
  ],
  "summary": "主要变更摘要",
  "key_changes": ["关键变更点1", "关键变更点2"]
}"""

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(
                role="user",
                content=f"原合同：\n{text_a[:4000]}\n\n新合同：\n{text_b[:4000]}"
            ),
        ]
        
        response = await chat_client.chat(messages, temperature=0.3)
        
        import json
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {
                "changes": [],
                "summary": response.content,
                "key_changes": [],
            }
        
        return TaskResult(
            success=True,
            data=data,
            model_used=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
        )
    
    async def _execute_assistant(
        self,
        context: Dict[str, Any],
        provider_id: Optional[str],
        model: Optional[str],
    ) -> TaskResult:
        """Execute assistant chat."""
        message = context.get("message", "")
        history = context.get("history", [])
        contract_context = context.get("contract_text", "")
        rag_context = context.get("rag_context", "")
        
        chat_client = self.registry.get_chat_client(provider_id, model)
        
        system_prompt = """你是合同哨兵的法务助理，专业、准确、负责任。

你的职责：
1. 回答法律和合同相关问题
2. 分析合同条款风险
3. 提供修改建议
4. 引用相关法规

注意事项：
- 对于超出能力范围的问题，建议咨询专业律师
- 回答需要基于提供的上下文和法规
- 给出建议时说明依据"""

        if contract_context:
            system_prompt += f"\n\n当前合同上下文：\n{contract_context[:4000]}"
        
        if rag_context:
            system_prompt += f"\n\n相关法规参考：\n{rag_context[:2000]}"
        
        messages = [ChatMessage(role="system", content=system_prompt)]
        
        # Add history
        for h in history[-10:]:  # Last 10 messages
            messages.append(ChatMessage(role=h["role"], content=h["content"]))
        
        messages.append(ChatMessage(role="user", content=message))
        
        response = await chat_client.chat(messages, temperature=0.7)
        
        return TaskResult(
            success=True,
            data={
                "response": response.content,
                "citations": [],  # TODO: Extract citations from RAG
            },
            model_used=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
        )
    
    async def stream_assistant(
        self,
        context: Dict[str, Any],
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream assistant response."""
        message = context.get("message", "")
        history = context.get("history", [])
        
        chat_client = self.registry.get_chat_client(provider_id, model)
        
        system_prompt = """你是合同哨兵的法务助理，专业、准确、负责任。
回答法律和合同相关问题，分析合同条款风险，提供修改建议。
对于超出能力范围的问题，建议咨询专业律师。"""
        
        messages = [ChatMessage(role="system", content=system_prompt)]
        
        for h in history[-10:]:
            messages.append(ChatMessage(role=h["role"], content=h["content"]))
        
        messages.append(ChatMessage(role="user", content=message))
        
        async for token in chat_client.chat_stream(messages, temperature=0.7):
            yield token
