"""Data retention - purge records older than DATA_RETENTION_DAYS."""
from datetime import datetime, timedelta

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.contract import Contract
from app.models.review import ReviewResult
from app.models.comparison import ComparisonResult
from app.models.chat import ChatSession, ChatMessage
from app.models.rag import RagChunk, RagDocument


async def purge_expired_data(db: AsyncSession) -> dict:
    """
    Delete records older than data_retention_days. Returns counts per entity.
    Call from a scheduled job or cron (e.g. python -m app.tasks.retention).
    """
    cutoff = datetime.utcnow() - timedelta(days=settings.data_retention_days)
    stats = {}
    try:
        # Audit logs
        r = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
        stats["audit_logs"] = r.rowcount
        # Review results (before contracts so FK is ok if we delete contracts after)
        r = await db.execute(delete(ReviewResult).where(ReviewResult.created_at < cutoff))
        stats["review_results"] = r.rowcount
        # Comparison results
        r = await db.execute(delete(ComparisonResult).where(ComparisonResult.created_at < cutoff))
        stats["comparison_results"] = r.rowcount
        # Contracts
        r = await db.execute(delete(Contract).where(Contract.created_at < cutoff))
        stats["contracts"] = r.rowcount
        # Chat messages then sessions
        r = await db.execute(delete(ChatMessage).where(ChatMessage.created_at < cutoff))
        stats["chat_messages"] = r.rowcount
        r = await db.execute(delete(ChatSession).where(ChatSession.created_at < cutoff))
        stats["chat_sessions"] = r.rowcount
        # RAG chunks then documents
        r = await db.execute(delete(RagChunk).where(RagChunk.created_at < cutoff))
        stats["rag_chunks"] = r.rowcount
        r = await db.execute(delete(RagDocument).where(RagDocument.created_at < cutoff))
        stats["rag_documents"] = r.rowcount
        await db.commit()
        logger.info(f"Retention purge before {cutoff.isoformat()}: {stats}")
    except Exception as e:
        await db.rollback()
        logger.exception(f"Retention purge failed: {e}")
        raise
    return stats
