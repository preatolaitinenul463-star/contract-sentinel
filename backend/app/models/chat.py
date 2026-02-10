"""Chat models for legal assistant."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum as SqlEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ContextType(str, enum.Enum):
    """Chat context types."""
    CONTRACT = "contract"  # Specific contract
    TEMPLATE = "template"  # Template library
    WEB_RAG = "web_rag"  # Web legal sources
    GENERAL = "general"  # No specific context


class ChatSession(Base):
    """Chat session model."""
    
    __tablename__ = "chat_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    title: Mapped[Optional[str]] = mapped_column(String(200))
    
    context_type: Mapped[ContextType] = mapped_column(
        SqlEnum(ContextType), 
        default=ContextType.GENERAL
    )
    context_id: Mapped[Optional[int]] = mapped_column(Integer)  # contract_id if applicable
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id})>"


class ChatMessage(Base):
    """Chat message model."""
    
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    
    role: Mapped[str] = mapped_column(String(20))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Citations for assistant messages
    # [{
    #   "type": "contract" | "web" | "template",
    #   "source": str,  # URL or contract name
    #   "text": str,  # Quoted text
    #   "location": {...}  # Optional location info
    # }]
    citations: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    
    # Model info (for assistant messages)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role})>"
