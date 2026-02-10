"""User model."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class PlanType(str, enum.Enum):
    """User subscription plan types."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User account model."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    plan_type: Mapped[PlanType] = mapped_column(
        SqlEnum(PlanType), 
        default=PlanType.FREE
    )
    
    # Usage tracking
    tokens_used: Mapped[int] = mapped_column(default=0)
    reviews_count: Mapped[int] = mapped_column(default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    contracts = relationship("Contract", back_populates="user", lazy="selectin")
    chat_sessions = relationship("ChatSession", back_populates="user", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
