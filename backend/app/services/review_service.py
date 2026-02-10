"""Contract review service."""
import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, AsyncIterator
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.contract import Contract, ContractStatus
from app.models.review import ReviewResult
from app.agents.doc_ingest import DocIngestAgent
from app.agents.clause_struct import ClauseStructAgent
from app.agents.rule_engine import RuleEngineAgent
from app.agents.orchestrator import Orchestrator, TaskType
from app.schemas.review import RiskItem, ClauseLocation, ReviewProgressEvent
from app.services.security_service import (
    get_encryption_service,
    mask_text_for_llm_input,
    mask_llm_output,
)
from app.services.audit_service import AuditService


class ReviewService:
    """Service for contract review operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_ingest = DocIngestAgent()
        self.clause_struct = ClauseStructAgent()
        self.rule_engine = RuleEngineAgent()
        self.orchestrator = Orchestrator()
    
    async def review_contract(
        self,
        contract: Contract,
        use_rules: bool = True,
        deep_review: bool = True,
    ) -> ReviewResult:
        """Perform full contract review."""
        start_time = datetime.utcnow()
        risk_items: List[Dict[str, Any]] = []
        total_tokens = 0
        model_used = None
        
        try:
            # Step 1: Parse document
            contract.status = ContractStatus.PARSING
            await self.db.commit()
            
            parsed_doc = await self.doc_ingest.parse(
                contract.file_path,
                contract.mime_type
            )
            enc = get_encryption_service()
            contract.raw_text = enc.encrypt_at_rest(parsed_doc.raw_text)
            contract.page_count = parsed_doc.page_count
            contract.status = ContractStatus.PARSED
            await self.db.commit()
            
            # Step 2: Extract structure
            structure = await self.clause_struct.extract_structure(parsed_doc.raw_text)
            
            # Step 3: Rule-based checking
            if use_rules:
                rule_matches = self.rule_engine.check(
                    parsed_doc.raw_text,
                    jurisdiction=contract.jurisdiction.value,
                    contract_type=contract.contract_type.value,
                )
                
                for match in rule_matches:
                    risk_items.append({
                        "id": match.rule_id,
                        "severity": match.severity,
                        "name": match.name,
                        "description": match.description,
                        "clause_text": mask_llm_output(match.matched_text or ""),
                        "location": match.location,
                        "suggestion": match.suggestion and mask_llm_output(match.suggestion) or None,
                        "rule_id": match.rule_id,
                        "requires_human_review": False,
                    })
            
            # Step 4: LLM deep review
            if deep_review:
                contract.status = ContractStatus.REVIEWING
                await self.db.commit()
                
                result = await self.orchestrator.execute(
                    TaskType.REVIEW,
                    context={
                        "text": mask_text_for_llm_input(parsed_doc.raw_text),
                        "contract_type": contract.contract_type.value,
                        "jurisdiction": contract.jurisdiction.value,
                    },
                )
                
                if result.success:
                    llm_risks = result.data.get("risk_items", [])
                    for risk in llm_risks:
                        if not any(r["name"] == risk.get("name") for r in risk_items):
                            risk_items.append({
                                "id": f"llm_{len(risk_items)}",
                                "severity": risk.get("severity", "medium"),
                                "name": risk.get("name", ""),
                                "description": risk.get("description", ""),
                                "clause_text": mask_llm_output(risk.get("clause_text", "") or ""),
                                "location": {},
                                "suggestion": risk.get("suggestion") and mask_llm_output(risk["suggestion"]) or None,
                                "rule_id": None,
                                "requires_human_review": True,
                            })
                    total_tokens = result.tokens_input + result.tokens_output
                    model_used = result.model_used
                    await AuditService(self.db).log_llm_call(
                        user_id=contract.user_id,
                        provider="deepseek",
                        model=result.model_used or "",
                        tokens_input=result.tokens_input,
                        tokens_output=result.tokens_output,
                        duration_ms=result.duration_ms,
                        purpose="review",
                        trace_id=str(uuid.uuid4()),
                        input_summary=f"len={len(parsed_doc.raw_text)}",
                    )
            
            contract.status = ContractStatus.REVIEWED
            await self.db.commit()
            
            # Create review result
            high_count = sum(1 for r in risk_items if r["severity"] == "high")
            medium_count = sum(1 for r in risk_items if r["severity"] == "medium")
            low_count = sum(1 for r in risk_items if r["severity"] == "low")
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Generate summary
            summary = self._generate_summary(risk_items)
            
            review_result = ReviewResult(
                contract_id=contract.id,
                risk_items=risk_items,
                clauses={
                    "parties": [p for p in structure.parties],
                    "effective_date": structure.effective_date,
                    "expiry_date": structure.expiry_date,
                    "contract_amount": structure.contract_amount,
                },
                summary=summary,
                high_risk_count=high_count,
                medium_risk_count=medium_count,
                low_risk_count=low_count,
                model_used=model_used,
                tokens_used=total_tokens,
                duration_ms=duration_ms,
            )
            
            self.db.add(review_result)
            await self.db.commit()
            await self.db.refresh(review_result)
            
            return review_result
            
        except Exception as e:
            logger.exception(f"Review failed: {e}")
            contract.status = ContractStatus.ERROR
            contract.error_message = str(e)
            await self.db.commit()
            raise
    
    async def stream_review(
        self,
        contract: Contract,
        use_rules: bool = True,
        deep_review: bool = True,
    ) -> AsyncIterator[ReviewProgressEvent]:
        """Stream review progress."""
        try:
            # Stage 1: Parsing
            yield ReviewProgressEvent(stage="parsing", progress=10, message="正在解析合同文档...")
            
            contract.status = ContractStatus.PARSING
            await self.db.commit()
            
            parsed_doc = await self.doc_ingest.parse(contract.file_path, contract.mime_type)
            enc = get_encryption_service()
            contract.raw_text = enc.encrypt_at_rest(parsed_doc.raw_text)
            contract.page_count = parsed_doc.page_count
            contract.status = ContractStatus.PARSED
            await self.db.commit()
            
            yield ReviewProgressEvent(stage="parsing", progress=25, message="文档解析完成")
            
            # Stage 2: Structuring
            yield ReviewProgressEvent(stage="structuring", progress=35, message="正在提取条款结构...")
            structure = await self.clause_struct.extract_structure(parsed_doc.raw_text)
            yield ReviewProgressEvent(stage="structuring", progress=45, message="条款结构提取完成")
            
            # Stage 3: Rule checking
            risk_items = []
            if use_rules:
                yield ReviewProgressEvent(stage="rule_checking", progress=55, message="正在进行规则检查...")
                
                rule_matches = self.rule_engine.check(
                    parsed_doc.raw_text,
                    jurisdiction=contract.jurisdiction.value,
                    contract_type=contract.contract_type.value,
                )
                
                for match in rule_matches:
                    risk_item = RiskItem(
                        id=match.rule_id,
                        severity=match.severity,
                        name=match.name,
                        description=match.description,
                        clause_text=mask_llm_output(match.matched_text or ""),
                        location=ClauseLocation(),
                        suggestion=match.suggestion and mask_llm_output(match.suggestion) or None,
                        rule_id=match.rule_id,
                        requires_human_review=False,
                    )
                    risk_items.append(risk_item)
                    yield ReviewProgressEvent(
                        stage="rule_checking",
                        progress=60,
                        message=f"发现风险：{match.name}",
                        risk_item=risk_item,
                    )
                
                yield ReviewProgressEvent(stage="rule_checking", progress=65, message="规则检查完成")
            
            # Stage 4: LLM reviewing
            total_tokens = 0
            model_used = None
            
            if deep_review:
                contract.status = ContractStatus.REVIEWING
                await self.db.commit()
                
                yield ReviewProgressEvent(stage="llm_reviewing", progress=75, message="正在进行AI深度审核...")
                
                result = await self.orchestrator.execute(
                    TaskType.REVIEW,
                    context={
                        "text": mask_text_for_llm_input(parsed_doc.raw_text),
                        "contract_type": contract.contract_type.value,
                        "jurisdiction": contract.jurisdiction.value,
                    },
                )
                
                if result.success:
                    llm_risks = result.data.get("risk_items", [])
                    for risk in llm_risks:
                        if not any(r.name == risk.get("name") for r in risk_items):
                            risk_item = RiskItem(
                                id=f"llm_{len(risk_items)}",
                                severity=risk.get("severity", "medium"),
                                name=risk.get("name", ""),
                                description=risk.get("description", ""),
                                clause_text=mask_llm_output(risk.get("clause_text", "") or ""),
                                location=ClauseLocation(),
                                suggestion=risk.get("suggestion") and mask_llm_output(risk["suggestion"]) or None,
                                rule_id=None,
                                requires_human_review=True,
                            )
                            risk_items.append(risk_item)
                            yield ReviewProgressEvent(
                                stage="llm_reviewing",
                                progress=80,
                                message=f"AI发现风险：{risk.get('name')}",
                                risk_item=risk_item,
                            )
                    
                    total_tokens = result.tokens_input + result.tokens_output
                    model_used = result.model_used
                    await AuditService(self.db).log_llm_call(
                        user_id=contract.user_id,
                        provider="deepseek",
                        model=result.model_used or "",
                        tokens_input=result.tokens_input,
                        tokens_output=result.tokens_output,
                        duration_ms=result.duration_ms,
                        purpose="review",
                        trace_id=str(uuid.uuid4()),
                        input_summary=f"len={len(parsed_doc.raw_text)}",
                    )
                
                yield ReviewProgressEvent(stage="llm_reviewing", progress=85, message="AI审核完成")
            
            # Complete
            contract.status = ContractStatus.REVIEWED
            await self.db.commit()
            
            yield ReviewProgressEvent(stage="complete", progress=100, message="审核完成")
            
        except Exception as e:
            contract.status = ContractStatus.ERROR
            contract.error_message = str(e)
            await self.db.commit()
            yield ReviewProgressEvent(stage="error", progress=0, message=f"审核失败: {str(e)}")
    
    def _generate_summary(self, risk_items: List[Dict[str, Any]]) -> str:
        """Generate a summary of the review."""
        high = sum(1 for r in risk_items if r["severity"] == "high")
        medium = sum(1 for r in risk_items if r["severity"] == "medium")
        low = sum(1 for r in risk_items if r["severity"] == "low")
        
        if high == 0 and medium == 0:
            return "合同整体风险较低，建议关注细节条款。"
        elif high > 0:
            return f"发现{high}个高风险条款，建议重点关注并修改后再签署。"
        else:
            return f"发现{medium}个中风险条款，建议仔细审阅相关内容。"
