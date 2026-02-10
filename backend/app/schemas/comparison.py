"""Comparison schemas."""
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel


class ChangeLocation(BaseModel):
    """Location of a change in the document."""
    page: Optional[int] = None
    paragraph: Optional[int] = None
    clause_id: Optional[str] = None


class ChangeItem(BaseModel):
    """Schema for a change item found in comparison."""
    id: str
    change_type: Literal["added", "removed", "modified"]
    clause_type: Optional[str] = None  # e.g., "payment", "liability", "termination"
    original_text: Optional[str] = None
    new_text: Optional[str] = None
    location_a: Optional[ChangeLocation] = None
    location_b: Optional[ChangeLocation] = None
    risk_impact: Literal["increased", "decreased", "neutral", "uncertain"]
    analysis: str  # Explanation of the change impact


class CompareRequest(BaseModel):
    """Schema for comparison request."""
    contract_a_id: int  # Original/old contract
    contract_b_id: int  # New/modified contract
    analyze_risk_impact: bool = True


class CompareResponse(BaseModel):
    """Schema for comparison response."""
    id: int
    contract_a_id: int
    contract_b_id: int
    changes: List[ChangeItem]
    added_count: int
    removed_count: int
    modified_count: int
    risk_increased_count: int
    summary: Optional[str]
    key_changes: Optional[List[str]]  # Top changes to review
    model_used: Optional[str]
    tokens_used: int
    report_path: Optional[str]
    created_at: datetime
    
    model_config = {"from_attributes": True}
