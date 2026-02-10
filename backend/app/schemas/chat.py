"""Chat schemas."""
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel

from app.models.chat import ContextType


class Citation(BaseModel):
    """Schema for a citation in assistant response."""
    type: Literal["contract", "web", "template"]
    source: str  # URL or document name
    text: str  # Quoted text
    url: Optional[str] = None  # Clickable link


class ChatRequest(BaseModel):
    """Schema for chat request."""
    session_id: Optional[int] = None  # None to create new session
    message: str
    context_type: ContextType = ContextType.GENERAL
    context_id: Optional[int] = None  # contract_id if context_type is CONTRACT


class ChatMessageResponse(BaseModel):
    """Schema for a chat message."""
    id: int
    role: str
    content: str
    citations: Optional[List[Citation]]
    model_used: Optional[str]
    tokens_used: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    """Schema for chat session response."""
    id: int
    title: Optional[str]
    context_type: ContextType
    context_id: Optional[int]
    messages: List[ChatMessageResponse]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    """Schema for chat response (single message)."""
    session_id: int
    message: ChatMessageResponse


class ChatStreamEvent(BaseModel):
    """Schema for SSE chat streaming events."""
    type: Literal["start", "token", "citation", "done", "error"]
    content: Optional[str] = None  # Token content
    citation: Optional[Citation] = None
    message_id: Optional[int] = None  # Set when done
    error: Optional[str] = None
