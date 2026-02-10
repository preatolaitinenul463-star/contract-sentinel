"""Oversight (审阅工作台) API — list / detail / approve / reject pipeline runs."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.pipeline import (
    PipelineRun, PipelineEvent, ProvenanceSource,
    VerificationResult, ApprovalTask,
    ApprovalState, PipelineStatus,
)
from app.api.deps import get_current_user

router = APIRouter()


# ── helpers ──

def _run_to_dict(run: PipelineRun, *, include_detail: bool = False) -> dict:
    """Serialise a PipelineRun to a JSON‑safe dict."""
    d = {
        "id": run.id,
        "run_id": run.run_id,
        "feature": run.feature.value if run.feature else None,
        "mode": run.mode,
        "status": run.status.value if run.status else None,
        "jurisdiction": run.jurisdiction,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "duration_ms": run.duration_ms,
        "total_tokens_input": run.total_tokens_input,
        "total_tokens_output": run.total_tokens_output,
        "result_summary": run.result_summary,
        "artifact_paths": run.artifact_paths,
        "trace_id": run.trace_id,
    }
    # source stats
    if run.sources:
        d["official_count"] = sum(1 for s in run.sources if s.trusted)
        d["open_count"] = sum(1 for s in run.sources if not s.trusted)
    else:
        d["official_count"] = 0
        d["open_count"] = 0

    # verification summary
    if run.verifications:
        d["verification_passed"] = all(v.passed for v in run.verifications)
        d["verification_count"] = len(run.verifications)
    else:
        d["verification_passed"] = True
        d["verification_count"] = 0

    # approval
    if run.approval:
        d["approval"] = {
            "state": run.approval.state.value if run.approval.state else "draft",
            "comment": run.approval.comment,
            "export_enabled": run.approval.export_enabled,
            "updated_at": run.approval.updated_at.isoformat() if run.approval.updated_at else None,
        }
    else:
        d["approval"] = None

    # detail: events, sources, verifications
    if include_detail:
        d["events"] = [
            {
                "stage": e.stage, "status": e.status, "progress": e.progress,
                "message": e.message, "payload": e.payload,
                "duration_ms": e.duration_ms,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in (run.events or [])
        ]
        d["sources"] = [
            {
                "source_id": s.source_id, "trusted": s.trusted,
                "kind": s.kind.value if s.kind else "other",
                "title": s.title, "url": s.url,
                "excerpt": (s.excerpt or "")[:500],
                "institution": s.institution,
            }
            for s in (run.sources or [])
        ]
        d["verifications"] = [
            {
                "rule_id": v.rule_id, "passed": v.passed,
                "detail": v.detail,
                "action": v.action.value if v.action else "pass",
            }
            for v in (run.verifications or [])
        ]

    return d


# ── endpoints ──

@router.get("/runs")
async def list_runs(
    feature: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pipeline runs for the current user (or all for admin)."""
    q = (
        select(PipelineRun)
        .options(
            selectinload(PipelineRun.sources),
            selectinload(PipelineRun.verifications),
            selectinload(PipelineRun.approval),
        )
        .where(PipelineRun.user_id == current_user.id)
    )
    if feature:
        q = q.where(PipelineRun.feature == feature)
    if status_filter:
        q = q.where(PipelineRun.status == status_filter)
    q = q.order_by(PipelineRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(q)
    runs = result.scalars().all()
    return [_run_to_dict(r) for r in runs]


@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full detail of a pipeline run including events, sources, verifications."""
    q = (
        select(PipelineRun)
        .options(
            selectinload(PipelineRun.events),
            selectinload(PipelineRun.sources),
            selectinload(PipelineRun.verifications),
            selectinload(PipelineRun.approval),
        )
        .where(PipelineRun.run_id == run_id, PipelineRun.user_id == current_user.id)
    )
    result = await db.execute(q)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return _run_to_dict(run, include_detail=True)


@router.post("/runs/{run_id}/approve")
async def approve_run(
    run_id: str,
    comment: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pipeline run — enables export/download."""
    q = (
        select(PipelineRun)
        .options(selectinload(PipelineRun.approval))
        .where(PipelineRun.run_id == run_id, PipelineRun.user_id == current_user.id)
    )
    result = await db.execute(q)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    if run.approval:
        run.approval.state = ApprovalState.APPROVED
        run.approval.reviewer_user_id = current_user.id
        run.approval.comment = comment
        run.approval.export_enabled = True
        run.approval.updated_at = datetime.utcnow()
    else:
        db.add(ApprovalTask(
            run_id=run_id,
            state=ApprovalState.APPROVED,
            reviewer_user_id=current_user.id,
            comment=comment,
            export_enabled=True,
        ))

    await db.commit()
    logger.info(f"Run {run_id} approved by user {current_user.id}")
    return {"status": "approved", "run_id": run_id}


@router.post("/runs/{run_id}/reject")
async def reject_run(
    run_id: str,
    comment: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pipeline run."""
    q = (
        select(PipelineRun)
        .options(selectinload(PipelineRun.approval))
        .where(PipelineRun.run_id == run_id, PipelineRun.user_id == current_user.id)
    )
    result = await db.execute(q)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    if run.approval:
        run.approval.state = ApprovalState.REJECTED
        run.approval.reviewer_user_id = current_user.id
        run.approval.comment = comment
        run.approval.export_enabled = False
        run.approval.updated_at = datetime.utcnow()
    else:
        db.add(ApprovalTask(
            run_id=run_id,
            state=ApprovalState.REJECTED,
            reviewer_user_id=current_user.id,
            comment=comment,
            export_enabled=False,
        ))

    await db.commit()
    logger.info(f"Run {run_id} rejected by user {current_user.id}")
    return {"status": "rejected", "run_id": run_id}
