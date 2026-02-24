"""FastAPI application entry point."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import init_db, close_db
from app.api import auth, contracts, review, compare, assistant, quota, audit, rag, oversight, policy
from app.middleware.audit import AuditMiddleware
from app.middleware.quota import QuotaMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware


def setup_logging():
    """Configure loguru logging."""
    # Remove default handler
    logger.remove()

    # Console handler
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=log_format, level=settings.log_level)

    # File handler (if configured)
    if settings.log_file:
        log_dir = Path(settings.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        if settings.is_production:
            # JSON format for production (structured logging)
            logger.add(
                settings.log_file,
                serialize=True,
                rotation=settings.log_rotation,
                retention=settings.log_retention,
                level=settings.log_level,
                compression="gz",
            )
        else:
            logger.add(
                settings.log_file,
                rotation=settings.log_rotation,
                retention=settings.log_retention,
                level=settings.log_level,
            )


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_env}")

    # Validate production configuration
    if settings.is_production:
        try:
            settings.validate_production()
        except ValueError as e:
            logger.error(str(e))
            raise

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize OpenTelemetry (safe no‑op when packages missing)
    from app.telemetry import init_telemetry
    init_telemetry(app)
    
    yield
    
    # Shutdown
    await close_db()
    logger.info("Database connections closed")
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="智能合同审核、对比与法律助手平台",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Middleware (order matters: outermost first, innermost last)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(QuotaMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(contracts.router, prefix="/api/contracts", tags=["合同管理"])
app.include_router(review.router, prefix="/api/review", tags=["合同审核"])
app.include_router(compare.router, prefix="/api/compare", tags=["合同对比"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["法律助手"])
app.include_router(policy.router, prefix="/api/policy", tags=["审核策略"])
app.include_router(quota.router, prefix="/api/quota", tags=["配额与计费"])
app.include_router(audit.router, prefix="/api/audit", tags=["审计与取证"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG 知识库"])
app.include_router(oversight.router, prefix="/api/oversight", tags=["审阅工作台"])


@app.on_event("startup")
async def ensure_guest_session():
    """Ensure a local guest session exists when auth UI is removed."""
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models.user import User
    from app.api.auth import get_password_hash
    guest_email = "2606536766@qq.com"
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == guest_email))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email=guest_email,
                hashed_password=get_password_hash("guest-access-only"),
                full_name="本地访客",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.commit()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/health/detail")
async def health_detail():
    """Detailed health check - reports database and Redis connectivity."""
    checks = {"database": "unknown", "redis": "unknown"}

    # Check database
    try:
        from app.database import async_session_maker
        from sqlalchemy import text
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)[:100]}"

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unavailable: {str(e)[:100]}"

    overall = "healthy" if checks["database"] == "healthy" else "degraded"
    return {"status": overall, "checks": checks}
