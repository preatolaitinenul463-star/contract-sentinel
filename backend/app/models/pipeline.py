"""Pipeline models for provenance, verification, and oversight.

Tables:
  - pipeline_runs        : one row per assistant/review/redline invocation
  - pipeline_events      : stage‑level events (used for SSE replay & tracing)
  - provenance_sources   : structured search sources (S1..Sn) per run
  - verification_results : per‑rule pass/fail per run
  - approval_tasks       : human oversight / approval workflow
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import enum

from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text,
    JSON, Boolean, Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────────

class PipelineFeature(str, enum.Enum):
    ASSISTANT = "assistant"
    REVIEW = "review"
    REDLINE = "redline"


class PipelineStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"          # verification forced degradation


class ApprovalState(str, enum.Enum):
    DRAFT = "draft"                # auto‑generated, pending review
    APPROVED = "approved"
    REJECTED = "rejected"


class VerifyAction(str, enum.Enum):
    PASS = "pass"
    RETRY = "retry_generation"
    DEGRADE = "degrade_with_disclaimer"
    HUMAN = "human_review_required"


class SourceKind(str, enum.Enum):
    STATUTE = "statute"
    CASE = "case"
    COMMENTARY = "commentary"
    OTHER = "other"


# ── PipelineRun ────────────────────────────────────────────

class PipelineRun(Base):
    """One invocation of assistant / review / redline."""
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)

    feature: Mapped[PipelineFeature] = mapped_column(SqlEnum(PipelineFeature), nullable=False)
    mode: Mapped[Optional[str]] = mapped_column(String(50))          # e.g. qa / case_analysis
    status: Mapped[PipelineStatus] = mapped_column(SqlEnum(PipelineStatus), default=PipelineStatus.RUNNING)

    # input fingerprint (SHA‑256 of contract text / user message)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64))
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(10))

    # timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # tokens
    total_tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_output: Mapped[int] = mapped_column(Integer, default=0)

    # trace correlation
    trace_id: Mapped[Optional[str]] = mapped_column(String(64))

    # result summary (small JSON for list views)
    result_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # file artifacts (paths in storage)
    artifact_paths: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # relationships
    events = relationship("PipelineEvent", back_populates="run", lazy="selectin",
                          order_by="PipelineEvent.created_at")
    sources = relationship("ProvenanceSource", back_populates="run", lazy="selectin")
    verifications = relationship("VerificationResult", back_populates="run", lazy="selectin")
    approval = relationship("ApprovalTask", back_populates="run", uselist=False, lazy="selectin")

    def __repr__(self):
        return f"<PipelineRun {self.run_id} feature={self.feature}>"


# ── PipelineEvent ──────────────────────────────────────────

class PipelineEvent(Base):
    """Stage‑level event within a pipeline run."""
    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_runs.run_id"), index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(String(500))
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run = relationship("PipelineRun", back_populates="events")


# ── ProvenanceSource ───────────────────────────────────────

class ProvenanceSource(Base):
    """A single search source attached to a pipeline run."""
    __tablename__ = "provenance_sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_runs.run_id"), index=True)
    source_id: Mapped[str] = mapped_column(String(10), nullable=False)          # S1, S2 …
    trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[SourceKind] = mapped_column(SqlEnum(SourceKind), default=SourceKind.OTHER)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    url: Mapped[Optional[str]] = mapped_column(String(2000))
    excerpt: Mapped[Optional[str]] = mapped_column(Text)
    institution: Mapped[Optional[str]] = mapped_column(String(200))
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run = relationship("PipelineRun", back_populates="sources")


# ── VerificationResult ─────────────────────────────────────

class VerificationResult(Base):
    """Result of a single verification rule for a pipeline run."""
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_runs.run_id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(50), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    action: Mapped[VerifyAction] = mapped_column(SqlEnum(VerifyAction), default=VerifyAction.PASS)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run = relationship("PipelineRun", back_populates="verifications")


# ── ApprovalTask ───────────────────────────────────────────

class ApprovalTask(Base):
    """Human oversight / approval record for a pipeline run."""
    __tablename__ = "approval_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_runs.run_id"), unique=True, index=True)
    state: Mapped[ApprovalState] = mapped_column(SqlEnum(ApprovalState), default=ApprovalState.DRAFT)
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    export_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    run = relationship("PipelineRun", back_populates="approval")
