"""Policy API - user standards with default fallback."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.policy import UserPolicy
from app.models.user import User
from app.schemas.policy import (
    PolicyParsePreviewRequest,
    PolicyParsePreviewResponse,
    PolicyResponse,
    PolicyUpdateRequest,
    ContractTypeSuggestionRequest,
    ContractTypeSuggestionResponse,
)
from app.services.policy_service import PolicyService, suggest_contract_type

router = APIRouter()


@router.get("/me", response_model=PolicyResponse)
async def get_my_policy(
    contract_type: str = "general",
    jurisdiction: str = "CN",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PolicyService(db)
    p = await service.get_or_default(current_user.id, contract_type=contract_type, jurisdiction=jurisdiction)
    return PolicyResponse(
        source=p.source,
        policy_version=p.policy_version,
        prefer_user_standard=p.prefer_user_standard,
        fallback_to_default=p.fallback_to_default,
        contract_type=p.contract_type,
        jurisdiction=p.jurisdiction,
        must_review_items=p.must_review_items,
        forbidden_terms=p.forbidden_terms,
        risk_tolerance=p.risk_tolerance,
        parse_warnings=p.parse_warnings,
    )


@router.post("/me/parse-preview", response_model=PolicyParsePreviewResponse)
async def parse_preview(
    request: PolicyParsePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PolicyService(db)
    parsed, warnings = service.parse_standard_text(request.standard_text)
    must_count = len(parsed.get("must_review_items", []))
    forbid_count = len(parsed.get("forbidden_terms", []))
    score = min(1.0, 0.2 + 0.06 * must_count + 0.03 * forbid_count)
    if warnings:
        score = max(0.1, score - 0.15)
    return PolicyParsePreviewResponse(parsed_policy=parsed, parse_warnings=warnings, success_score=round(score, 2))


@router.put("/me", response_model=PolicyResponse)
async def update_my_policy(
    request: PolicyUpdateRequest,
    contract_type: str = "general",
    jurisdiction: str = "CN",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PolicyService(db)
    await service.upsert_user_policy(
        user_id=current_user.id,
        standard_text=request.standard_text,
        prefer_user_standard=request.prefer_user_standard,
        fallback_to_default=request.fallback_to_default,
    )
    p = await service.get_or_default(current_user.id, contract_type=contract_type, jurisdiction=jurisdiction)
    return PolicyResponse(
        source=p.source,
        policy_version=p.policy_version,
        prefer_user_standard=p.prefer_user_standard,
        fallback_to_default=p.fallback_to_default,
        contract_type=p.contract_type,
        jurisdiction=p.jurisdiction,
        must_review_items=p.must_review_items,
        forbidden_terms=p.forbidden_terms,
        risk_tolerance=p.risk_tolerance,
        parse_warnings=p.parse_warnings,
    )


@router.post("/suggest-contract-type", response_model=ContractTypeSuggestionResponse)
async def suggest_type(
    request: ContractTypeSuggestionRequest,
    current_user: User = Depends(get_current_user),
):
    data = suggest_contract_type(request.text)
    return ContractTypeSuggestionResponse(**data)
