"""Comparison result model."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComparisonResult(Base):
    """Contract comparison result model."""
    
    __tablename__ = "comparison_results"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    contract_a_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    contract_b_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    
    # Changes (JSONB array)
    # Each item: {
    #   "id": str,
    #   "change_type": "added" | "removed" | "modified",
    #   "clause_type": str,  # e.g., "payment", "liability"
    #   "original_text": str | null,
    #   "new_text": str | null,
    #   "location_a": {...} | null,
    #   "location_b": {...} | null,
    #   "risk_impact": "increased" | "decreased" | "neutral" | "uncertain",
    #   "analysis": str
    # }
    changes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # Statistics
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, default=0)
    modified_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_increased_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Summary
    summary: Mapped[Optional[str]] = mapped_column(Text)
    key_changes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Top changes to review
    
    # Report
    report_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Model usage
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ComparisonResult(id={self.id}, a={self.contract_a_id}, b={self.contract_b_id})>"
