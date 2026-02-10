"""PipelineContext — carries run‑level state through the pipeline stages.

Every assistant / review / redline invocation creates a PipelineContext
at the start and uses it to:
  * generate a ``run_id``
  * collect sources, events, verification results
  * persist everything at the end
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.database import async_session_maker
from app.models.pipeline import (
    PipelineRun, PipelineEvent, ProvenanceSource,
    VerificationResult, ApprovalTask,
    PipelineFeature, PipelineStatus, ApprovalState,
    SourceKind, VerifyAction,
)
from app.telemetry import new_run_id, get_run_id, get_trace_id, record_counter


class PipelineContext:
    """Mutable bag that travels through every stage of a pipeline."""

    def __init__(
        self,
        feature: str,
        user_id: Optional[int] = None,
        mode: Optional[str] = None,
        jurisdiction: str = "CN",
        input_text: str = "",
    ):
        self.run_id = new_run_id()
        try:
            self.feature = PipelineFeature(feature)
        except (ValueError, KeyError):
            self.feature = PipelineFeature.ASSISTANT
        self.user_id = user_id
        self.mode = mode
        self.jurisdiction = jurisdiction
        self.input_hash = hashlib.sha256(input_text[:10000].encode()).hexdigest()

        self.started_at = datetime.now(timezone.utc)
        self.status = PipelineStatus.RUNNING

        # collected during pipeline
        self.events: List[Dict[str, Any]] = []
        self.sources: List[Dict[str, Any]] = []
        self.verifications: List[Dict[str, Any]] = []
        self.result_summary: Dict[str, Any] = {}
        self.artifact_paths: Dict[str, str] = {}

        self.total_tokens_input = 0
        self.total_tokens_output = 0

        record_counter("sentinel_pipeline_runs_total", 1, {"feature": feature, "status": "started"})

    # ── helpers ────────────────────────────────────────────

    def add_event(self, stage: str, status: str, progress: int = 0,
                  message: str = "", payload: Optional[dict] = None, duration_ms: int = 0):
        self.events.append({
            "stage": stage, "status": status, "progress": progress,
            "message": message, "payload": payload, "duration_ms": duration_ms,
        })

    def add_source(self, source_id: str, *, trusted: bool, kind: str = "other",
                   title: str = "", url: str = "", excerpt: str = "",
                   institution: str = "", published_date: Optional[datetime] = None):
        self.sources.append({
            "source_id": source_id, "trusted": trusted, "kind": kind,
            "title": title, "url": url, "excerpt": excerpt,
            "institution": institution, "published_date": published_date,
        })

    def add_verification(self, rule_id: str, passed: bool, detail: str = "",
                         action: str = "pass"):
        self.verifications.append({
            "rule_id": rule_id, "passed": passed,
            "detail": detail, "action": action,
        })

    @property
    def needs_human_review(self) -> bool:
        return any(v["action"] == "human_review_required" for v in self.verifications)

    @property
    def is_degraded(self) -> bool:
        return any(v["action"] == "degrade_with_disclaimer" for v in self.verifications)

    # ── persistence ────────────────────────────────────────

    async def persist(self):
        """Write the full pipeline run to the database."""
        now = datetime.now(timezone.utc)
        duration_ms = int((now - self.started_at).total_seconds() * 1000)

        # Normalise status to enum (callers may set string like "failed")
        if isinstance(self.status, str):
            try:
                self.status = PipelineStatus(self.status)
            except (ValueError, KeyError):
                self.status = PipelineStatus.FAILED

        if self.needs_human_review:
            self.status = PipelineStatus.DEGRADED
        elif self.status == PipelineStatus.RUNNING:
            self.status = PipelineStatus.COMPLETED

        try:
            async with async_session_maker() as db:
                run = PipelineRun(
                    run_id=self.run_id,
                    user_id=self.user_id,
                    feature=self.feature,
                    mode=self.mode or "",
                    status=self.status,
                    input_hash=self.input_hash,
                    jurisdiction=self.jurisdiction,
                    started_at=self.started_at,
                    ended_at=now,
                    duration_ms=duration_ms,
                    total_tokens_input=self.total_tokens_input,
                    total_tokens_output=self.total_tokens_output,
                    trace_id=get_trace_id(),
                    result_summary=self.result_summary,
                    artifact_paths=self.artifact_paths if self.artifact_paths else None,
                )
                db.add(run)
                await db.flush()

                # events
                for e in self.events:
                    db.add(PipelineEvent(run_id=self.run_id, **e))

                # sources
                for s in self.sources:
                    s_copy = dict(s)  # don't mutate original
                    kind_val = s_copy.pop("kind", "other")
                    try:
                        kind_enum = SourceKind(kind_val)
                    except (ValueError, KeyError):
                        kind_enum = SourceKind.OTHER
                    # Remove keys that aren't ProvenanceSource columns
                    for extra_key in list(s_copy.keys()):
                        if extra_key not in ("source_id", "trusted", "title", "url", "excerpt", "institution", "published_date"):
                            s_copy.pop(extra_key, None)
                    db.add(ProvenanceSource(run_id=self.run_id, kind=kind_enum, **s_copy))

                # verifications
                for v in self.verifications:
                    v_copy = dict(v)
                    action_val = v_copy.pop("action", "pass")
                    try:
                        action_enum = VerifyAction(action_val)
                    except (ValueError, KeyError):
                        action_enum = VerifyAction.PASS
                    db.add(VerificationResult(
                        run_id=self.run_id,
                        rule_id=v_copy.get("rule_id", "unknown"),
                        passed=v_copy.get("passed", True),
                        detail=v_copy.get("detail", ""),
                        action=action_enum,
                    ))

                # approval task (auto‑create if human review needed)
                if self.needs_human_review:
                    db.add(ApprovalTask(
                        run_id=self.run_id,
                        state=ApprovalState.DRAFT,
                        export_enabled=False,
                    ))

                await db.commit()

            feat_str = self.feature.value if hasattr(self.feature, "value") else str(self.feature)
            stat_str = self.status.value if hasattr(self.status, "value") else str(self.status)
            record_counter("sentinel_pipeline_runs_total", 1, {"feature": feat_str, "status": stat_str})
            logger.info(f"Pipeline run {self.run_id} persisted ({stat_str}, {duration_ms}ms)")

        except Exception as exc:
            logger.error(f"Failed to persist pipeline run {self.run_id}: {exc}")
