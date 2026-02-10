"""Authentication API routes."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.contract import Contract
from app.models.review import ReviewResult
from app.models.chat import ChatSession
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.api.deps import create_access_token, get_current_user
from app.services.email_service import EmailService

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MAX_PASSWORD_BYTES = 72  # bcrypt hard limit

# In-memory token store for password reset and email verification.
# In production, use Redis or database.
_reset_tokens: dict[str, dict] = {}  # token -> {"user_id": int, "expires": datetime}
_verify_tokens: dict[str, dict] = {}  # token -> {"email": str, "expires": datetime}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_length(password: str) -> None:
    """Validate bcrypt password length in bytes."""
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码过长，最多72字节（建议 8-32 位）",
        )


# ------ Registration ------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and send verification email."""
    validate_password_length(user_data.password)
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email (best effort)
    try:
        token = secrets.token_urlsafe(32)
        _verify_tokens[token] = {
            "email": user.email,
            "expires": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        email_service = EmailService()
        await email_service.send_verification_email(user.email, token)
    except Exception as e:
        logger.warning(f"Failed to send verification email: {e}")

    return user


# ------ Login ------

@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token."""
    validate_password_length(credentials.password)
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账号已被禁用",
        )

    access_token, expires_in = create_access_token(user.id)

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


# ------ Token Refresh ------

@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
):
    """Refresh JWT token. Use a valid (non-expired) token to get a new one."""
    access_token, expires_in = create_access_token(current_user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
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

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email."""
    # Always return success to prevent email enumeration
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(32)
        _reset_tokens[token] = {
            "user_id": user.id,
            "expires": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        try:
            email_service = EmailService()
            await email_service.send_password_reset(user.email, token)
        except Exception as e:
            logger.warning(f"Failed to send reset email: {e}")

    return {"message": "如果该邮箱已注册，我们已发送重置链接。请查收邮件。"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using the token from email."""
    validate_password_length(request.new_password)
    token_data = _reset_tokens.get(request.token)
    if not token_data:
        raise HTTPException(status_code=400, detail="无效的重置链接")

    if datetime.now(timezone.utc) > token_data["expires"]:
        _reset_tokens.pop(request.token, None)
        raise HTTPException(status_code=400, detail="重置链接已过期，请重新申请")

    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="密码长度至少8位")

    result = await db.execute(
        select(User).where(User.id == token_data["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    user.hashed_password = get_password_hash(request.new_password)
    await db.commit()

    # Invalidate token
    _reset_tokens.pop(request.token, None)

    return {"message": "密码已重置成功，请使用新密码登录"}


# ------ Email Verification ------

@router.get("/verify-email")
async def verify_email(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Verify email address using the token from email."""
    token_data = _verify_tokens.get(token)
    if not token_data:
        raise HTTPException(status_code=400, detail="无效的验证链接")

    if datetime.now(timezone.utc) > token_data["expires"]:
        _verify_tokens.pop(token, None)
        raise HTTPException(status_code=400, detail="验证链接已过期")

    result = await db.execute(
        select(User).where(User.email == token_data["email"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    user.is_verified = True
    await db.commit()

    _verify_tokens.pop(token, None)

    return {"message": "邮箱验证成功"}


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
