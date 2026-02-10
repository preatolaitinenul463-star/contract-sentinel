"""Review result model."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewResult(Base):
    """Contract review result model."""
    
    __tablename__ = "review_results"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    
    # Risk items (JSONB array)
    # Each item: {
    #   "id": str,
    #   "severity": "high" | "medium" | "low",
    #   "name": str,
    #   "description": str,
    #   "clause_text": str,
    #   "location": {"page": int, "paragraph": int, "start": int, "end": int},
    #   "suggestion": str,
    #   "rule_id": str | null,
    #   "requires_human_review": bool
    # }
    risk_items: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # Structured clauses extracted
    # {
    #   "parties": [...],
    #   "payment_terms": {...},
    #   "delivery_terms": {...},
    #   "liability": {...},
    #   "dispute_resolution": {...},
    #   ...
    # }
    clauses: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Summary
    summary: Mapped[Optional[str]] = mapped_column(Text)
    high_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    medium_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    low_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Report file path
    report_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Model usage tracking
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contract = relationship("Contract", back_populates="review_results")
    
    def __repr__(self) -> str:
        return f"<ReviewResult(id={self.id}, contract_id={self.contract_id})>"
