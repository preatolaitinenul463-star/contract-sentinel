"""Security middleware - adds security headers and rate limiting."""
import time
from collections import defaultdict
from typing import Callable, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # Content-Security-Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.deepseek.com https://api.minimax.chat; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # HSTS only in production
        from app.config import settings
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with Redis support (fallback to in-memory).

    Supports both IP-based and user-based rate limiting.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: Dict[str, list] = defaultdict(list)
        self._redis = None
        self._redis_checked = False

    async def _get_redis(self):
        """Try to connect to Redis for distributed rate limiting."""
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        try:
            from app.config import settings
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            logger.info("Rate limiter using Redis backend")
        except Exception:
            self._redis = None
            logger.info("Rate limiter using in-memory backend (Redis unavailable)")
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and static
        if request.url.path in ("/health", "/", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"rate:{client_ip}"

        redis = await self._get_redis()

        if redis:
            # Redis-backed rate limiting
            try:
                count = await redis.incr(rate_key)
                if count == 1:
                    await redis.expire(rate_key, 60)

                if count > self.requests_per_minute:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "请求过于频繁，请稍后再试", "error_type": "rate_limited"},
                        headers={"Retry-After": "60"},
                    )
            except Exception:
                pass  # On Redis error, allow the request
        else:
            # In-memory fallback
            now = time.time()
            window = 60.0
            self._requests[rate_key] = [
                t for t in self._requests[rate_key] if now - t < window
            ]

            if len(self._requests[rate_key]) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后再试", "error_type": "rate_limited"},
                    headers={"Retry-After": "60"},
                )

            self._requests[rate_key].append(now)

        return await call_next(request)
