"""Policy schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PolicyParsePreviewRequest(BaseModel):
    standard_text: str = Field(min_length=1)


class PolicyUpdateRequest(BaseModel):
    standard_text: str = Field(default="")
    prefer_user_standard: bool = True
    fallback_to_default: bool = True


class PolicyResponse(BaseModel):
    source: str
    policy_version: str
    prefer_user_standard: bool
    fallback_to_default: bool
    contract_type: str
    jurisdiction: str
    must_review_items: List[str]
    forbidden_terms: List[str]
    risk_tolerance: str
    parse_warnings: List[str]


class PolicyParsePreviewResponse(BaseModel):
    parsed_policy: Dict[str, Any]
    parse_warnings: List[str]
    success_score: float


class ContractTypeSuggestionRequest(BaseModel):
    text: str = Field(min_length=1)


class ContractTypeSuggestionResponse(BaseModel):
    suggested_contract_type: str
    confidence: float
