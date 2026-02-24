"""User policy and feedback models."""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserPolicy(Base):
    """Per-user review policy configuration."""

    __tablename__ = "user_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)

    # Raw user-provided standard text (paste/upload extracted text)
    standard_text: Mapped[Optional[str]] = mapped_column(Text)

    # Parsed, normalized policy JSON
    parsed_policy: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Runtime switches
    prefer_user_standard: Mapped[bool] = mapped_column(Boolean, default=True)
    fallback_to_default: Mapped[bool] = mapped_column(Boolean, default=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewFeedback(Base):
    """Lightweight user feedback for later backtesting."""

    __tablename__ = "review_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    helpful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    issue_type: Mapped[Optional[str]] = mapped_column(String(20))  # false_positive / missed_risk / other
    comment: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
