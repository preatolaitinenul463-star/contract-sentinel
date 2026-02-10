"""Audit service - logs all user actions and API calls."""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.audit_log import AuditLog


class AuditService:
    """Service for logging audit events."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        action: str,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        duration_ms: int = 0,
        cost: Optional[float] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log an audit event."""
        # Sanitize metadata - remove any sensitive data
        if metadata:
            metadata = self._sanitize_metadata(metadata)
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            provider=provider,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms,
            cost=cost,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=metadata,
            success=success,
            error_message=error_message,
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        
        # Also log to file for backup
        logger.info(
            f"AUDIT: action={action} user={user_id} resource={resource_type}:{resource_id} "
            f"success={success}"
        )
        
        return audit_log
    
    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from metadata."""
        sensitive_keys = {
            "password", "token", "api_key", "secret",
            "credit_card", "id_card", "ssn", "bank_account"
        }
        
        sanitized = {}
        for key, value in metadata.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_metadata(value)
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate long strings
                sanitized[key] = value[:100] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    async def log_login(
        self,
        user_id: int,
        ip_address: str,
        user_agent: str,
        success: bool,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log a login attempt."""
        return await self.log(
            action="login",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
    
    async def log_upload(
        self,
        user_id: int,
        contract_id: int,
        filename: str,
        file_size: int,
    ) -> AuditLog:
        """Log a file upload."""
        return await self.log(
            action="upload",
            user_id=user_id,
            resource_type="contract",
            resource_id=contract_id,
            metadata={
                "filename": filename,
                "file_size": file_size,
            },
        )
    
    async def log_review(
        self,
        user_id: int,
        contract_id: int,
        review_id: int,
        provider: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        duration_ms: int,
        cost: float,
    ) -> AuditLog:
        """Log a contract review."""
        return await self.log(
            action="review",
            user_id=user_id,
            resource_type="review",
            resource_id=review_id,
            provider=provider,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms,
            cost=cost,
            metadata={"contract_id": contract_id},
        )
    
    async def log_llm_call(
        self,
        user_id: Optional[int],
        provider: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        duration_ms: int,
        cost: Optional[float] = None,
        purpose: Optional[str] = None,
        trace_id: Optional[str] = None,
        input_summary: Optional[str] = None,
    ) -> AuditLog:
        """Log an LLM API call (trace_id and input_summary for minimization audit)."""
        meta = {}
        if purpose:
            meta["purpose"] = purpose
        if trace_id:
            meta["trace_id"] = trace_id
        if input_summary:
            meta["input_summary"] = input_summary
        return await self.log(
            action="llm_call",
            user_id=user_id,
            provider=provider,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms,
            cost=cost,
            metadata=meta if meta else None,
        )
    
    async def log_export(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int,
        format: str,
    ) -> AuditLog:
        """Log a report export."""
        return await self.log(
            action="export",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"format": format},
        )
    
    async def log_delete(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int,
    ) -> AuditLog:
        """Log a resource deletion."""
        return await self.log(
            action="delete",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
