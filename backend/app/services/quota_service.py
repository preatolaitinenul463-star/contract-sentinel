"""Quota service - manages user usage limits and billing."""
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user import User, PlanType
from app.models.audit_log import AuditLog


@dataclass
class PlanLimits:
    """Usage limits for a plan."""
    reviews_per_month: int
    comparisons_per_month: int
    assistant_messages_per_day: int
    max_file_size_mb: int
    max_pages_per_document: int
    rag_enabled: bool
    export_enabled: bool
    priority_support: bool


# Plan configurations
PLAN_LIMITS: Dict[PlanType, PlanLimits] = {
    PlanType.FREE: PlanLimits(
        reviews_per_month=10,
        comparisons_per_month=5,
        assistant_messages_per_day=20,
        max_file_size_mb=10,
        max_pages_per_document=20,
        rag_enabled=False,
        export_enabled=False,
        priority_support=False,
    ),
    PlanType.BASIC: PlanLimits(
        reviews_per_month=50,
        comparisons_per_month=20,
        assistant_messages_per_day=100,
        max_file_size_mb=30,
        max_pages_per_document=50,
        rag_enabled=True,
        export_enabled=True,
        priority_support=False,
    ),
    PlanType.PRO: PlanLimits(
        reviews_per_month=200,
        comparisons_per_month=100,
        assistant_messages_per_day=500,
        max_file_size_mb=50,
        max_pages_per_document=100,
        rag_enabled=True,
        export_enabled=True,
        priority_support=True,
    ),
    PlanType.ENTERPRISE: PlanLimits(
        reviews_per_month=10000,
        comparisons_per_month=5000,
        assistant_messages_per_day=10000,
        max_file_size_mb=100,
        max_pages_per_document=500,
        rag_enabled=True,
        export_enabled=True,
        priority_support=True,
    ),
}


@dataclass
class UsageStats:
    """Current usage statistics for a user."""
    reviews_this_month: int
    comparisons_this_month: int
    assistant_messages_today: int
    tokens_used_this_month: int
    
    reviews_remaining: int
    comparisons_remaining: int
    assistant_messages_remaining: int


class QuotaService:
    """Service for managing usage quotas."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def get_plan_limits(self, plan_type: PlanType) -> PlanLimits:
        """Get limits for a plan."""
        return PLAN_LIMITS.get(plan_type, PLAN_LIMITS[PlanType.FREE])
    
    async def get_usage_stats(self, user: User) -> UsageStats:
        """Get current usage statistics for a user."""
        limits = self.get_plan_limits(user.plan_type)
        
        # Get start of current month
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count reviews this month
        reviews_query = select(func.count()).select_from(AuditLog).where(
            AuditLog.user_id == user.id,
            AuditLog.action == "review",
            AuditLog.created_at >= month_start,
            AuditLog.success == True,
        )
        reviews_result = await self.db.execute(reviews_query)
        reviews_this_month = reviews_result.scalar() or 0
        
        # Count comparisons this month
        comparisons_query = select(func.count()).select_from(AuditLog).where(
            AuditLog.user_id == user.id,
            AuditLog.action == "compare",
            AuditLog.created_at >= month_start,
            AuditLog.success == True,
        )
        comparisons_result = await self.db.execute(comparisons_query)
        comparisons_this_month = comparisons_result.scalar() or 0
        
        # Count assistant messages today
        messages_query = select(func.count()).select_from(AuditLog).where(
            AuditLog.user_id == user.id,
            AuditLog.action == "chat",
            AuditLog.created_at >= day_start,
            AuditLog.success == True,
        )
        messages_result = await self.db.execute(messages_query)
        assistant_messages_today = messages_result.scalar() or 0
        
        # Count tokens this month
        tokens_query = select(func.sum(AuditLog.tokens_input + AuditLog.tokens_output)).where(
            AuditLog.user_id == user.id,
            AuditLog.created_at >= month_start,
        )
        tokens_result = await self.db.execute(tokens_query)
        tokens_used_this_month = tokens_result.scalar() or 0
        
        return UsageStats(
            reviews_this_month=reviews_this_month,
            comparisons_this_month=comparisons_this_month,
            assistant_messages_today=assistant_messages_today,
            tokens_used_this_month=tokens_used_this_month,
            reviews_remaining=max(0, limits.reviews_per_month - reviews_this_month),
            comparisons_remaining=max(0, limits.comparisons_per_month - comparisons_this_month),
            assistant_messages_remaining=max(0, limits.assistant_messages_per_day - assistant_messages_today),
        )
    
    async def check_quota(
        self,
        user: User,
        action: str,
        file_size_mb: Optional[int] = None,
        page_count: Optional[int] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user has quota for an action.
        Returns (allowed, error_message).
        """
        limits = self.get_plan_limits(user.plan_type)
        stats = await self.get_usage_stats(user)
        
        if action == "review":
            if stats.reviews_remaining <= 0:
                return False, f"本月审核次数已用完（{limits.reviews_per_month}次）。请升级套餐或下月再试。"
        
        elif action == "compare":
            if stats.comparisons_remaining <= 0:
                return False, f"本月对比次数已用完（{limits.comparisons_per_month}次）。请升级套餐或下月再试。"
        
        elif action == "chat":
            if stats.assistant_messages_remaining <= 0:
                return False, f"今日助理消息次数已用完（{limits.assistant_messages_per_day}次）。请明天再试。"
        
        elif action == "upload":
            if file_size_mb and file_size_mb > limits.max_file_size_mb:
                return False, f"文件大小超过限制（最大{limits.max_file_size_mb}MB）。请升级套餐。"
            if page_count and page_count > limits.max_pages_per_document:
                return False, f"文档页数超过限制（最大{limits.max_pages_per_document}页）。请升级套餐。"
        
        elif action == "export":
            if not limits.export_enabled:
                return False, "当前套餐不支持导出功能。请升级到基础版或更高套餐。"
        
        elif action == "rag":
            if not limits.rag_enabled:
                return False, "当前套餐不支持法规检索功能。请升级到基础版或更高套餐。"
        
        return True, None
    
    async def increment_usage(self, user: User, action: str, count: int = 1) -> None:
        """Increment user's usage counter."""
        if action == "review":
            user.reviews_count += count
        # Note: We rely on audit logs for actual counting
        # This is just for quick reference
        await self.db.commit()


# Pricing information (for display)
PRICING = {
    PlanType.FREE: {
        "name": "免费版",
        "price": 0,
        "price_unit": "永久免费",
        "features": [
            "每月10次合同审核",
            "每月5次合同对比",
            "每日20条助理消息",
            "最大10MB文件",
            "基础风险检测",
        ],
    },
    PlanType.BASIC: {
        "name": "基础版",
        "price": 99,
        "price_unit": "元/月",
        "features": [
            "每月50次合同审核",
            "每月20次合同对比",
            "每日100条助理消息",
            "最大30MB文件",
            "完整风险检测",
            "法规检索功能",
            "报告导出(Word/PDF)",
        ],
    },
    PlanType.PRO: {
        "name": "专业版",
        "price": 299,
        "price_unit": "元/月",
        "features": [
            "每月200次合同审核",
            "每月100次合同对比",
            "每日500条助理消息",
            "最大50MB文件",
            "深度风险分析",
            "法规检索功能",
            "报告导出(Word/PDF)",
            "优先技术支持",
        ],
    },
    PlanType.ENTERPRISE: {
        "name": "企业版",
        "price": None,
        "price_unit": "联系销售",
        "features": [
            "无限次合同审核",
            "无限次合同对比",
            "无限助理消息",
            "最大100MB文件",
            "定制规则包",
            "API集成",
            "私有化部署",
            "专属客户经理",
        ],
    },
}
