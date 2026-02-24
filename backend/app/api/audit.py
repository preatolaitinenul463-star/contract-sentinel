"""Audit log API - list and export for traceability."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import csv
import io
import json

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    from_date: Optional[datetime] = Query(None, description="Start time (ISO)"),
    to_date: Optional[datetime] = Query(None, description="End time (ISO)"),
    action: Optional[str] = Query(None, description="Filter by action"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs for current user; admins can query all logs."""
    if current_user.is_admin:
        q = select(AuditLog)
    else:
        q = select(AuditLog).where(AuditLog.user_id == current_user.id)
    if from_date:
        q = q.where(AuditLog.created_at >= from_date)
    if to_date:
        q = q.where(AuditLog.created_at <= to_date)
    if action:
        q = q.where(AuditLog.action == action)
    q = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "provider": log.provider,
            "model": log.model,
            "tokens_input": log.tokens_input,
            "tokens_output": log.tokens_output,
            "ip_address": log.ip_address,
            "success": log.success,
            "extra_data": log.extra_data,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/export")
async def export_audit_logs(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export audit logs; admins can export all records."""
    if current_user.is_admin:
        q = select(AuditLog)
    else:
        q = select(AuditLog).where(AuditLog.user_id == current_user.id)
    if from_date:
        q = q.where(AuditLog.created_at >= from_date)
    if to_date:
        q = q.where(AuditLog.created_at <= to_date)
    q = q.order_by(AuditLog.created_at.asc())
    result = await db.execute(q)
    logs = result.scalars().all()
    rows = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "provider": log.provider,
            "model": log.model,
            "tokens_input": log.tokens_input,
            "tokens_output": log.tokens_output,
            "duration_ms": log.duration_ms,
            "ip_address": log.ip_address,
            "user_agent": (log.user_agent or "")[:200],
            "success": log.success,
            "error_message": log.error_message,
            "extra_data": log.extra_data,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
    if format == "csv":
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
        )
    return StreamingResponse(
        iter([json.dumps(rows, ensure_ascii=False, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_export.json"},
    )
