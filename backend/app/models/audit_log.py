"""Audit log model."""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Audit log for tracking user actions and API calls."""
    
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Action details
    action: Mapped[str] = mapped_column(String(50), index=True)
    # Actions: login, logout, upload, delete, review, compare, chat, export, etc.
    
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    # Types: contract, review, comparison, chat, etc.
    
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)
    
    # LLM call tracking (if applicable)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Optional[float]] = mapped_column()
    
    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Additional context (no sensitive data!) - renamed from 'metadata' which is reserved
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Status
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user={self.user_id})>"
