"""Legal assistant service."""
import uuid
from typing import List, Dict, Any, Optional, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.chat import ChatSession, ChatMessage, ContextType
from app.models.contract import Contract
from app.agents.orchestrator import Orchestrator, TaskType
from app.rag.retriever import RagRetriever
from app.services.security_service import (
    get_encryption_service,
    mask_text_for_llm_input,
    mask_llm_output,
)
from app.services.audit_service import AuditService


class AssistantService:
    """Service for legal assistant chat operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = Orchestrator()
        self.retriever = RagRetriever(db)
    
    async def chat(
        self,
        session: ChatSession,
        message: str,
        use_rag: bool = True,
    ) -> ChatMessage:
        """Process a chat message and return response."""
        # Get chat history
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages[-10:]  # Last 10 messages
        ]
        
        # Get contract context if applicable
        contract_context = ""
        if session.context_type == ContextType.CONTRACT and session.context_id:
            from sqlalchemy import select
            result = await self.db.execute(
                select(Contract).where(Contract.id == session.context_id)
            )
            contract = result.scalar_one_or_none()
            if contract and contract.raw_text:
                raw = get_encryption_service().decrypt_at_rest(contract.raw_text) or ""
                contract_context = mask_text_for_llm_input(raw[:4000])
        
        # Get RAG context if enabled
        rag_context = ""
        citations = []
        if use_rag and session.context_type in (ContextType.WEB_RAG, ContextType.GENERAL):
            try:
                rag_results = await self.retriever.search(message, top_k=3)
                rag_parts = []
                for r in rag_results:
                    rag_parts.append(f"来源: {r['source']}\n{r['text']}")
                    citations.append({
                        "type": "web",
                        "source": r["source"],
                        "text": r["text"][:200],
                        "url": r.get("url"),
                    })
                rag_context = "\n\n".join(rag_parts)
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")
        
        # Execute assistant
        result = await self.orchestrator.execute(
            TaskType.ASSISTANT,
            context={
                "message": message,
                "history": history,
                "contract_text": contract_context,
                "rag_context": rag_context,
            },
        )
        
        response_content = result.data.get("response", "抱歉，我暂时无法回答您的问题。")
        response_content = mask_llm_output(response_content)
        await AuditService(self.db).log_llm_call(
            user_id=session.user_id,
            provider="deepseek",
            model=result.model_used or "",
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            duration_ms=result.duration_ms,
            purpose="assistant",
            trace_id=str(uuid.uuid4()),
            input_summary=f"msg_len={len(message)}",
        )
        # Create assistant message
        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=response_content,
            citations=citations if citations else None,
            model_used=result.model_used,
            tokens_used=result.tokens_input + result.tokens_output,
        )
        
        self.db.add(assistant_message)
        await self.db.commit()
        await self.db.refresh(assistant_message)
        
        return assistant_message
    
    async def stream_chat(
        self,
        session: ChatSession,
        message: str,
        use_rag: bool = True,
    ) -> AsyncIterator[str]:
        """Stream chat response with optional RAG augmentation."""
        # Get chat history
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages[-10:]
        ]

        # Get RAG context if enabled
        rag_context = ""
        if use_rag and session.context_type in (ContextType.WEB_RAG, ContextType.GENERAL):
            try:
                rag_results = await self.retriever.search(message, top_k=3)
                rag_parts = []
                for r in rag_results:
                    rag_parts.append(f"来源: {r.get('source', '未知')}\n{r['text']}")
                rag_context = "\n\n".join(rag_parts)
            except Exception as e:
                logger.warning(f"RAG retrieval failed in stream_chat: {e}")

        context: dict = {
            "message": message,
            "history": history,
        }
        if rag_context:
            context["rag_context"] = rag_context

        async for token in self.orchestrator.stream_assistant(context=context):
            yield token
