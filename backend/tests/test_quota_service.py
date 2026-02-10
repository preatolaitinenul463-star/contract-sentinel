"""Tests for QuotaService."""
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.user import User, PlanType
from app.services.quota_service import QuotaService, PLAN_LIMITS


class TestPlanLimits:
    """Test plan limit configurations."""

    def test_free_plan_limits(self):
        limits = PLAN_LIMITS[PlanType.FREE]
        assert limits.reviews_per_month == 10
        assert limits.comparisons_per_month == 5
        assert limits.assistant_messages_per_day == 20
        assert limits.rag_enabled is False
        assert limits.export_enabled is False

    def test_basic_plan_limits(self):
        limits = PLAN_LIMITS[PlanType.BASIC]
        assert limits.reviews_per_month == 50
        assert limits.rag_enabled is True
        assert limits.export_enabled is True

    def test_pro_plan_limits(self):
        limits = PLAN_LIMITS[PlanType.PRO]
        assert limits.reviews_per_month == 200
        assert limits.priority_support is True

    def test_enterprise_plan_limits(self):
        limits = PLAN_LIMITS[PlanType.ENTERPRISE]
        assert limits.reviews_per_month == 10000
        assert limits.max_file_size_mb == 100


class TestQuotaService:
    """Test quota checking logic."""

    @pytest_asyncio.fixture
    async def service(self, db_session):
        return QuotaService(db_session)

    @pytest_asyncio.fixture
    async def free_user(self, db_session):
        user = User(
            email="test@example.com",
            hashed_password="hashed",
            plan_type=PlanType.FREE,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest_asyncio.fixture
    async def pro_user(self, db_session):
        user = User(
            email="pro@example.com",
            hashed_password="hashed",
            plan_type=PlanType.PRO,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_check_review_allowed(self, service, free_user):
        """Fresh user should have review quota."""
        allowed, error = await service.check_quota(free_user, "review")
        assert allowed is True
        assert error is None

    @pytest.mark.asyncio
    async def test_check_export_denied_free(self, service, free_user):
        """Free plan should not allow export."""
        allowed, error = await service.check_quota(free_user, "export")
        assert allowed is False
        assert "导出" in error

    @pytest.mark.asyncio
    async def test_check_export_allowed_pro(self, service, pro_user):
        """Pro plan should allow export."""
        allowed, error = await service.check_quota(pro_user, "export")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_check_rag_denied_free(self, service, free_user):
        """Free plan should not allow RAG."""
        allowed, error = await service.check_quota(free_user, "rag")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_check_upload_file_size(self, service, free_user):
        """Free plan should deny files larger than 10MB."""
        allowed, error = await service.check_quota(free_user, "upload", file_size_mb=20)
        assert allowed is False
        assert "文件大小" in error

    @pytest.mark.asyncio
    async def test_get_plan_limits(self, service):
        """Should return correct limits for each plan."""
        free_limits = service.get_plan_limits(PlanType.FREE)
        assert free_limits.reviews_per_month == 10

        pro_limits = service.get_plan_limits(PlanType.PRO)
        assert pro_limits.reviews_per_month == 200
