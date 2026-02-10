"""Contract comparison service."""
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.contract import Contract
from app.models.comparison import ComparisonResult
from app.agents.doc_ingest import DocIngestAgent
from app.agents.clause_struct import ClauseStructAgent
from app.agents.orchestrator import Orchestrator, TaskType
from app.services.security_service import get_encryption_service, mask_text_for_llm_input


class CompareService:
    """Service for contract comparison operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_ingest = DocIngestAgent()
        self.clause_struct = ClauseStructAgent()
        self.orchestrator = Orchestrator()
    
    async def compare_contracts(
        self,
        contract_a: Contract,
        contract_b: Contract,
        analyze_risk: bool = True,
    ) -> ComparisonResult:
        """Compare two contracts and analyze changes."""
        start_time = datetime.utcnow()
        
        try:
            enc = get_encryption_service()
            # Parse both documents if not already parsed
            text_a = enc.decrypt_at_rest(contract_a.raw_text) if contract_a.raw_text else None
            if not text_a:
                parsed_a = await self.doc_ingest.parse(
                    contract_a.file_path,
                    contract_a.mime_type
                )
                text_a = parsed_a.raw_text
            
            text_b = enc.decrypt_at_rest(contract_b.raw_text) if contract_b.raw_text else None
            if not text_b:
                parsed_b = await self.doc_ingest.parse(
                    contract_b.file_path,
                    contract_b.mime_type
                )
                text_b = parsed_b.raw_text
            
            # Extract structures
            struct_a = await self.clause_struct.extract_structure(text_a)
            struct_b = await self.clause_struct.extract_structure(text_b)
            
            # Use LLM for comparison (masked input)
            result = await self.orchestrator.execute(
                TaskType.COMPARE,
                context={
                    "text_a": mask_text_for_llm_input(text_a),
                    "text_b": mask_text_for_llm_input(text_b),
                },
            )
            
            changes = result.data.get("changes", [])
            summary = result.data.get("summary", "")
            key_changes = result.data.get("key_changes", [])
            
            # Count changes
            added = sum(1 for c in changes if c.get("change_type") == "added")
            removed = sum(1 for c in changes if c.get("change_type") == "removed")
            modified = sum(1 for c in changes if c.get("change_type") == "modified")
            risk_increased = sum(1 for c in changes if c.get("risk_impact") == "increased")
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            comparison = ComparisonResult(
                user_id=contract_a.user_id,
                contract_a_id=contract_a.id,
                contract_b_id=contract_b.id,
                changes=changes,
                added_count=added,
                removed_count=removed,
                modified_count=modified,
                risk_increased_count=risk_increased,
                summary=summary,
                key_changes=key_changes,
                model_used=result.model_used,
                tokens_used=result.tokens_input + result.tokens_output,
            )
            
            self.db.add(comparison)
            await self.db.commit()
            await self.db.refresh(comparison)
            
            return comparison
            
        except Exception as e:
            logger.exception(f"Comparison failed: {e}")
            raise
