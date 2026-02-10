"""Review schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal

from pydantic import BaseModel, Field


class ClauseLocation(BaseModel):
    """Location of a clause in the document."""
    page: Optional[int] = None
    paragraph: Optional[int] = None
    start: Optional[int] = None  # character offset
    end: Optional[int] = None


class RiskItem(BaseModel):
    """Schema for a risk item found in review."""
    id: str
    severity: Literal["high", "medium", "low"]
    name: str
    description: str
    clause_text: str  # The problematic clause text
    location: ClauseLocation
    suggestion: Optional[str] = None  # Suggested replacement
    rule_id: Optional[str] = None  # Which rule triggered this
    requires_human_review: bool = False


class ReviewRequest(BaseModel):
    """Schema for review request."""
    contract_id: int
    use_rules: bool = True  # Use rule engine first
    deep_review: bool = True  # Use LLM for deep review
    generate_suggestions: bool = True  # Generate replacement suggestions


class ReviewResponse(BaseModel):
    """Schema for review response."""
    id: int
    contract_id: int
    risk_items: List[RiskItem]
    summary: Optional[str]
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    clauses: Optional[Dict[str, Any]]
    model_used: Optional[str]
    tokens_used: int
    cost: float
    duration_ms: int
    report_path: Optional[str]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ReviewProgressEvent(BaseModel):
    """Schema for SSE progress events."""
    stage: str  # parsing, structuring, rule_checking, llm_reviewing, generating_suggestions
    progress: float  # 0-100
    message: str
    risk_item: Optional[RiskItem] = None  # Real-time risk item found
