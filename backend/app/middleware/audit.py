"""Audit middleware - logs API requests to console and database."""
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests to console and persist to database."""

    # Paths to skip logging for
    SKIP_PATHS = ("/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico")

    # Paths that represent meaningful actions (persisted to DB)
    ACTION_MAP = {
        ("POST", "/api/review/upload-and-review"): ("review", "contract"),
        ("POST", "/api/compare/upload-and-compare"): ("compare", "contract"),
        ("POST", "/api/compare"): ("compare", "contract"),
        ("POST", "/api/assistant/chat"): ("chat", "chat"),
        ("GET", "/api/assistant/chat/stream"): ("chat", "chat"),
        ("POST", "/api/contracts/upload"): ("upload", "contract"),
        ("DELETE", "/api/contracts"): ("delete", "contract"),
        ("POST", "/api/auth/login"): ("login", "user"),
        ("POST", "/api/auth/register"): ("register", "user"),
        ("GET", "/api/review/export"): ("export", "review"),
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log it."""
        start_time = datetime.now(timezone.utc)

        # Get request info
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")[:200]

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        # Console log (skip health checks and static files)
        if not any(path.startswith(skip) for skip in self.SKIP_PATHS):
            logger.info(
                f"API: {method} {path} - {response.status_code} - {duration_ms}ms - {client_ip}"
            )

        # Persist meaningful actions to database
        action_info = self._match_action(method, path)
        if action_info:
            action, resource_type = action_info
            success = 200 <= response.status_code < 400
            try:
                await self._persist_audit_log(
                    action=action,
                    resource_type=resource_type,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    duration_ms=duration_ms,
                    success=success,
                    request=request,
                )
            except Exception as e:
                # Never block request processing due to audit logging failure
                logger.warning(f"Failed to persist audit log: {e}")

        return response

    def _match_action(self, method: str, path: str) -> tuple[str, str] | None:
        """Match a request to an action for audit logging."""
        # Exact match first
        key = (method, path)
        if key in self.ACTION_MAP:
            return self.ACTION_MAP[key]

        # Prefix match for parameterized paths
        for (m, p), action_info in self.ACTION_MAP.items():
            if m == method and path.startswith(p):
                return action_info

        return None

    async def _persist_audit_log(
        self,
        action: str,
        resource_type: str,
        ip_address: str,
        user_agent: str,
        duration_ms: int,
        success: bool,
        request: Request,
    ) -> None:
        """Persist audit log entry to database."""
        from app.database import async_session_maker
        from app.models.audit_log import AuditLog
        from jose import jwt, JWTError
        from app.config import settings

        # Extract user ID from auth header
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                payload = jwt.decode(
                    token,
                    settings.jwt_secret,
                    algorithms=[settings.jwt_algorithm],
                )
                user_id = payload.get("sub")
            except JWTError:
                pass

        async with async_session_maker() as db:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                ip_address=ip_address,
                user_agent=user_agent,
                duration_ms=duration_ms,
                success=success,
            )
            db.add(log_entry)
            await db.commit()
