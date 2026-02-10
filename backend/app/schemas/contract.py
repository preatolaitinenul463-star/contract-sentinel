"""Contract schemas."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.contract import ContractType, Jurisdiction, PartyRole, ContractStatus


class ContractCreate(BaseModel):
    """Schema for contract upload metadata."""
    contract_type: ContractType = ContractType.GENERAL
    jurisdiction: Jurisdiction = Jurisdiction.CN
    party_role: PartyRole = PartyRole.UNKNOWN


class ContractResponse(BaseModel):
    """Schema for contract response."""
    id: int
    filename: str
    file_size: int
    mime_type: Optional[str]
    contract_type: ContractType
    jurisdiction: Jurisdiction
    party_role: PartyRole
    status: ContractStatus
    page_count: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ContractListResponse(BaseModel):
    """Schema for paginated contract list."""
    items: List[ContractResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
