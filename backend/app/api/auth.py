"""Authentication API routes."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.database import get_db
from app.models.user import User
from app.models.contract import Contract
from app.models.review import ReviewResult
from app.models.chat import ChatSession
from app.schemas.user import UserResponse
from app.api.deps import get_current_user

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MAX_PASSWORD_BYTES = 72  # bcrypt hard limit

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_length(password: str) -> None:
    """Validate bcrypt password length in bytes."""
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码过长，最多72字节（建议 8-32 位）",
        )


# ------ Profile ------

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    full_name: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user information."""
    if full_name is not None:
        current_user.full_name = full_name

    await db.commit()
    await db.refresh(current_user)

    return current_user


# ------ Password Reset ------


# ------ Account Deletion & Data Export ------

@router.get("/me/export")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all user data as JSON (GDPR/个保法 compliance)."""
    # Contracts
    contracts_result = await db.execute(
        select(Contract).where(Contract.user_id == current_user.id)
    )
    contracts = contracts_result.scalars().all()

    # Reviews
    review_ids = [c.id for c in contracts]
    reviews = []
    if review_ids:
        reviews_result = await db.execute(
            select(ReviewResult).where(ReviewResult.contract_id.in_(review_ids))
        )
        reviews = reviews_result.scalars().all()

    # Chat sessions
    sessions_result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == current_user.id)
    )
    sessions = sessions_result.scalars().all()

    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "plan_type": current_user.plan_type.value if current_user.plan_type else None,
            "created_at": str(current_user.created_at),
        },
        "contracts_count": len(contracts),
        "reviews_count": len(reviews),
        "chat_sessions_count": len(sessions),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/me", status_code=200)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete user account and clean up data."""
    current_user.is_active = False
    current_user.email = f"deleted_{current_user.id}@deleted"
    current_user.full_name = "已注销用户"
    await db.commit()

    return {"message": "账号已注销。您的数据将在保留期后被清理。"}
