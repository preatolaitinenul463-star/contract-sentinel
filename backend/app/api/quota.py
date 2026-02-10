"""Quota and billing API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models.user import User, PlanType
from app.api.deps import get_current_user
from app.services.quota_service import QuotaService, PRICING, PLAN_LIMITS

router = APIRouter()


class UsageStatsResponse(BaseModel):
    """Usage statistics response."""
    reviews_this_month: int
    comparisons_this_month: int
    assistant_messages_today: int
    tokens_used_this_month: int
    reviews_remaining: int
    comparisons_remaining: int
    assistant_messages_remaining: int


class PlanLimitsResponse(BaseModel):
    """Plan limits response."""
    reviews_per_month: int
    comparisons_per_month: int
    assistant_messages_per_day: int
    max_file_size_mb: int
    max_pages_per_document: int
    rag_enabled: bool
    export_enabled: bool


class PlanInfo(BaseModel):
    """Plan information for pricing page."""
    id: str
    name: str
    price: Optional[int]
    price_unit: str
    features: List[str]
    is_current: bool


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's usage statistics."""
    quota_service = QuotaService(db)
    stats = await quota_service.get_usage_stats(current_user)
    
    return UsageStatsResponse(
        reviews_this_month=stats.reviews_this_month,
        comparisons_this_month=stats.comparisons_this_month,
        assistant_messages_today=stats.assistant_messages_today,
        tokens_used_this_month=stats.tokens_used_this_month,
        reviews_remaining=stats.reviews_remaining,
        comparisons_remaining=stats.comparisons_remaining,
        assistant_messages_remaining=stats.assistant_messages_remaining,
    )


@router.get("/limits", response_model=PlanLimitsResponse)
async def get_plan_limits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's plan limits."""
    quota_service = QuotaService(db)
    limits = quota_service.get_plan_limits(current_user.plan_type)
    
    return PlanLimitsResponse(
        reviews_per_month=limits.reviews_per_month,
        comparisons_per_month=limits.comparisons_per_month,
        assistant_messages_per_day=limits.assistant_messages_per_day,
        max_file_size_mb=limits.max_file_size_mb,
        max_pages_per_document=limits.max_pages_per_document,
        rag_enabled=limits.rag_enabled,
        export_enabled=limits.export_enabled,
    )


@router.get("/plans", response_model=List[PlanInfo])
async def get_available_plans(
    current_user: User = Depends(get_current_user),
):
    """Get all available plans for pricing page."""
    plans = []
    
    for plan_type in PlanType:
        plan_data = PRICING.get(plan_type, {})
        plans.append(PlanInfo(
            id=plan_type.value,
            name=plan_data.get("name", plan_type.value),
            price=plan_data.get("price"),
            price_unit=plan_data.get("price_unit", ""),
            features=plan_data.get("features", []),
            is_current=current_user.plan_type == plan_type,
        ))
    
    return plans


@router.post("/check/{action}")
async def check_quota(
    action: str,
    file_size_mb: Optional[int] = None,
    page_count: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if user has quota for an action."""
    quota_service = QuotaService(db)
    allowed, error_message = await quota_service.check_quota(
        current_user,
        action,
        file_size_mb=file_size_mb,
        page_count=page_count,
    )
    
    return {
        "allowed": allowed,
        "error": error_message,
    }
