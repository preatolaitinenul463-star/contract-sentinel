"""Verification Engine — the Verification–Correction Loop core.

Runs a set of rules against the pipeline output and decides:
  pass              → proceed to persist & export
  retry_generation  → ask LLM to regenerate (lower temp, stricter constraints)
  degrade_with_disclaimer → mark as uncertain, add disclaimer
  human_review_required   → create ApprovalTask, block export until approved

Rules:
  - CitationVerify      : all [S#] in text must exist in sources
  - OfficialBasisPolicy : statute references must come from trusted sources
  - SchemaValidate      : structured JSON must conform to expected schema
  - ClauseLocateVerify  : (redline only) clause_text must match doc paragraphs
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from app.pipeline.context import PipelineContext


# ═══════════════════════════════════════════════════════════
# Individual verification rules
# ═══════════════════════════════════════════════════════════

def _citation_verify(
    text: str,
    sources: List[Dict[str, Any]],
    ctx: PipelineContext,
) -> None:
    """Check that every [S#] footnote in the text maps to an existing source."""
    rule_id = "citation_verify"
    # Extract all [S#] references
    refs = set(re.findall(r'\[S(\d+)\]', text))
    source_ids = {s.get("source_id", "").replace("S", "") for s in sources}

    missing = refs - source_ids
    if missing:
        ctx.add_verification(
            rule_id=rule_id,
            passed=False,
            detail=f"Missing sources for footnotes: {', '.join('S' + m for m in missing)}",
            action="degrade_with_disclaimer",
        )
    else:
        ctx.add_verification(rule_id=rule_id, passed=True, detail=f"All {len(refs)} citations verified")


def _official_basis_policy(
    text: str,
    sources: List[Dict[str, Any]],
    ctx: PipelineContext,
) -> None:
    """Ensure statute/law references are backed by trusted (official) sources."""
    rule_id = "official_basis_policy"

    # Check if there's at least one trusted source
    trusted_sources = [s for s in sources if s.get("trusted")]
    if not trusted_sources:
        # Check if text contains law references
        has_law_refs = bool(re.search(r'《.+?》第.+?条|§\s*\d+', text))
        if has_law_refs:
            ctx.add_verification(
                rule_id=rule_id,
                passed=False,
                detail="Text references laws/statutes but no official sources were found. Confidence degraded.",
                action="degrade_with_disclaimer",
            )
            return
        # No law refs and no trusted sources — pass (nothing to verify)
        ctx.add_verification(rule_id=rule_id, passed=True, detail="No law references found, no official sources needed")
        return

    # Check that [S#] used in law citations point to trusted sources
    trusted_ids = {s.get("source_id", "") for s in trusted_sources}
    # Find law citation patterns followed by [S#]
    law_cite_refs = re.findall(r'《[^》]+》[^[]*?\[S(\d+)\]', text)
    untrusted_law_refs = []
    for ref_num in law_cite_refs:
        sid = f"S{ref_num}"
        if sid not in trusted_ids:
            untrusted_law_refs.append(sid)

    if untrusted_law_refs:
        ctx.add_verification(
            rule_id=rule_id,
            passed=False,
            detail=f"Law citations reference non-official sources: {', '.join(untrusted_law_refs)}",
            action="degrade_with_disclaimer",
        )
    else:
        ctx.add_verification(
            rule_id=rule_id,
            passed=True,
            detail=f"{len(trusted_sources)} official sources available",
        )


def _schema_validate(
    report_json: Any,
    expected_keys: List[str],
    ctx: PipelineContext,
) -> None:
    """Validate that the structured report JSON has expected top‑level keys."""
    rule_id = "schema_validate"

    if not isinstance(report_json, dict):
        ctx.add_verification(
            rule_id=rule_id,
            passed=False,
            detail="Report is not a valid JSON object",
            action="retry_generation",
        )
        return

    missing = [k for k in expected_keys if k not in report_json]
    if missing:
        ctx.add_verification(
            rule_id=rule_id,
            passed=False,
            detail=f"Missing keys in report: {', '.join(missing)}",
            action="retry_generation",
        )
    else:
        ctx.add_verification(rule_id=rule_id, passed=True, detail="Schema valid")


def _clause_locate_verify(
    risk_items: List[Dict[str, Any]],
    doc_paragraphs: List[str],
    ctx: PipelineContext,
    min_score: float = 0.3,
) -> None:
    """(Redline only) Verify that each risk's clause_text can be found in the document."""
    rule_id = "clause_locate_verify"

    if not risk_items or not doc_paragraphs:
        ctx.add_verification(rule_id=rule_id, passed=True, detail="No items to verify")
        return

    def normalize(t: str) -> str:
        return re.sub(r'\s+', '', t.strip())

    def lcs_len(s1: str, s2: str) -> int:
        s1, s2 = s1[:300], s2[:300]
        prev = [0] * (len(s2) + 1)
        best = 0
        for i in range(1, len(s1) + 1):
            curr = [0] * (len(s2) + 1)
            for j in range(1, len(s2) + 1):
                if s1[i-1] == s2[j-1]:
                    curr[j] = prev[j-1] + 1
                    best = max(best, curr[j])
            prev = curr
        return best

    para_norms = [normalize(p) for p in doc_paragraphs]
    unmatched = []

    for risk in risk_items:
        clause = risk.get("clause_text", "")
        if not clause or len(clause) < 4:
            continue
        clause_norm = normalize(clause)
        if len(clause_norm) < 4:
            continue

        best_score = 0.0
        for pn in para_norms:
            if not pn or len(pn) < 4:
                continue
            if clause_norm in pn or pn in clause_norm:
                best_score = 1.0
                break
            ratio = lcs_len(clause_norm, pn) / max(len(clause_norm), 1)
            best_score = max(best_score, ratio)

        if best_score < min_score:
            unmatched.append(risk.get("name", "unknown"))

    if unmatched:
        ctx.add_verification(
            rule_id=rule_id,
            passed=False,
            detail=f"Could not locate {len(unmatched)} clauses in document: {', '.join(unmatched[:5])}",
            action="human_review_required",
        )
    else:
        ctx.add_verification(
            rule_id=rule_id,
            passed=True,
            detail=f"All {len(risk_items)} clauses located in document",
        )


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════

def verify_assistant_output(
    text: str,
    report_json: Any,
    sources: List[Dict[str, Any]],
    ctx: PipelineContext,
    expected_keys: Optional[List[str]] = None,
):
    """Run verification suite for assistant output."""
    _citation_verify(text, sources, ctx)
    _official_basis_policy(text, sources, ctx)
    if report_json and expected_keys:
        _schema_validate(report_json, expected_keys, ctx)


def verify_review_output(
    text: str,
    risk_items: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
    ctx: PipelineContext,
):
    """Run verification suite for review output."""
    _citation_verify(text, sources, ctx)
    _official_basis_policy(text, sources, ctx)


def verify_redline_output(
    risk_items: List[Dict[str, Any]],
    doc_paragraphs: List[str],
    sources: List[Dict[str, Any]],
    ctx: PipelineContext,
):
    """Run verification suite for redline/annotation output."""
    # Build combined text from risk items for citation check
    combined = " ".join((r.get("description") or "") + " " + (r.get("legal_basis") or "") for r in risk_items)
    _citation_verify(combined, sources, ctx)
    _official_basis_policy(combined, sources, ctx)
    _clause_locate_verify(risk_items, doc_paragraphs, ctx)


def get_verification_decision(ctx: PipelineContext) -> str:
    """Return the most severe action from all verification results.
    Priority: human_review_required > retry_generation > degrade_with_disclaimer > pass
    """
    actions = [v["action"] for v in ctx.verifications]
    if "human_review_required" in actions:
        return "human_review_required"
    if "retry_generation" in actions:
        return "retry_generation"
    if "degrade_with_disclaimer" in actions:
        return "degrade_with_disclaimer"
    return "pass"
