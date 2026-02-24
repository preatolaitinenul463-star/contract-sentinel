"""API dependencies."""
from datetime import datetime, timedelta
import hashlib
import re
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(user_id: int) -> tuple[str, int]:
    """Create a JWT access token."""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        # JWT "sub" must be a string per spec; cast to str for compatibility
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_expire_minutes * 60


def _normalize_visitor_id(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "", raw)[:64]
    return normalized or None


async def _get_or_create_anonymous_user(db: AsyncSession, visitor_id: str) -> User:
    anon_email = f"visitor_{visitor_id}@guest.local"
    result = await db.execute(select(User).where(User.email == anon_email))
    user = result.scalar_one_or_none()
    if user and user.is_active:
        return user

    if not user:
        user = User(
            email=anon_email,
            hashed_password=pwd_context.hash(f"visitor-{visitor_id}"),
            full_name="匿名访客",
            is_active=True,
            is_verified=True,
            is_admin=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user


def _fallback_visitor_id(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    digest = hashlib.sha256(f"{ip}|{ua}".encode("utf-8")).hexdigest()
    return digest[:24]


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get user from JWT, fallback to isolated anonymous visitor."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials and credentials.credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            sub = payload.get("sub")
            if sub is None:
                raise credentials_exception
            user_id = int(sub)
        except (JWTError, ValueError):
            raise credentials_exception

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户账号已被禁用",
            )
        return user

    visitor_id = (
        _normalize_visitor_id(request.headers.get("x-visitor-id"))
        or _normalize_visitor_id(request.cookies.get("visitor_id"))
        or _fallback_visitor_id(request)
    )
    return await _get_or_create_anonymous_user(db, visitor_id)


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, otherwise None."""
    try:
        return await get_current_user(request=request, credentials=credentials, db=db)
    except HTTPException:
        return None
