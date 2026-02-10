"""AI Agent pipeline for contract processing."""
from app.agents.doc_ingest import DocIngestAgent, ParsedDocument, ClauseLocation
from app.agents.clause_struct import ClauseStructAgent, ContractStructure
from app.agents.rule_engine import RuleEngineAgent, RuleMatch
from app.agents.llm_review import LLMReviewAgent, LLMRiskItem, LLMReviewResult
from app.agents.redline_draft import RedlineDraftAgent, RedlineItem, RedlineResult
from app.agents.orchestrator import Orchestrator, TaskType

__all__ = [
    # Document Processing
    "DocIngestAgent",
    "ParsedDocument",
    "ClauseLocation",
    # Structure Extraction
    "ClauseStructAgent",
    "ContractStructure",
    # Rule Engine
    "RuleEngineAgent",
    "RuleMatch",
    # LLM Review
    "LLMReviewAgent",
    "LLMRiskItem",
    "LLMReviewResult",
    # Redline Draft
    "RedlineDraftAgent",
    "RedlineItem",
    "RedlineResult",
    # Orchestrator
    "Orchestrator",
    "TaskType",
]
