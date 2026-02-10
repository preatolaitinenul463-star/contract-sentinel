"""Quota middleware - checks usage limits before processing requests."""
import json
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt, JWTError
from loguru import logger

from app.config import settings


class QuotaMiddleware(BaseHTTPMiddleware):
    """Middleware to check quota before processing requests."""

    # Map endpoint patterns to quota actions
    QUOTA_ENDPOINTS = {
        ("/api/review/upload-and-review", "POST"): "review",
        ("/api/compare/upload-and-compare", "POST"): "compare",
        ("/api/compare", "POST"): "compare",
        ("/api/assistant/chat/stream", "GET"): "chat",
        ("/api/assistant/chat", "POST"): "chat",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check quota and process request."""
        path = request.url.path
        method = request.method

        # Check if this endpoint requires quota checking
        action = self.QUOTA_ENDPOINTS.get((path, method))
        if not action:
            return await call_next(request)

        # Extract user from JWT token
        user_id = self._extract_user_id(request)
        if not user_id:
            # No auth header - let the endpoint handle auth errors
            return await call_next(request)

        # Check quota
        try:
            from app.database import async_session_maker
            from app.models.user import User
            from app.services.quota_service import QuotaService
            from sqlalchemy import select

            async with async_session_maker() as db:
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    return await call_next(request)

                quota_service = QuotaService(db)
                allowed, error_message = await quota_service.check_quota(user, action)

                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": error_message or "配额已用尽",
                            "error_type": "quota_exceeded",
                            "action": action,
                        },
                    )
        except Exception as e:
            # Don't block requests on quota check failure
            logger.warning(f"Quota check failed: {e}")

        return await call_next(request)

    def _extract_user_id(self, request: Request) -> int | None:
        """Extract user ID from Authorization header JWT."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Also check query params for SSE endpoints
            token = request.query_params.get("token")
            if not token:
                return None
        else:
            token = auth_header.split(" ", 1)[1]

        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            return payload.get("sub")
        except JWTError:
            return None
