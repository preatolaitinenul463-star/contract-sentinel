"""Contract management API routes."""
import hashlib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.contract import Contract, ContractType, Jurisdiction, PartyRole, ContractStatus
from app.schemas.contract import ContractResponse, ContractListResponse
from app.api.deps import get_current_user

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/msword",  # doc
    "image/png",
    "image/jpeg",
    "image/jpg",
}


def get_file_hash(content: bytes) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


@router.post("/upload", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile = File(...),
    contract_type: ContractType = Form(ContractType.GENERAL),
    jurisdiction: Jurisdiction = Form(Jurisdiction.CN),
    party_role: PartyRole = Form(PartyRole.UNKNOWN),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a contract file."""
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}。支持: PDF, DOCX, PNG, JPG"
        )
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Check file size
    max_size = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制 ({settings.max_file_size_mb}MB)"
        )
    
    # Calculate file hash
    file_hash = get_file_hash(content)
    
    # Create storage directory for user
    user_dir = settings.storage_dir / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = user_dir / f"{file_hash}_{file.filename}"
    file_path.write_bytes(content)
    
    # Create contract record
    contract = Contract(
        user_id=current_user.id,
        filename=file.filename,
        file_hash=file_hash,
        file_path=str(file_path),
        file_size=file_size,
        mime_type=file.content_type,
        contract_type=contract_type,
        jurisdiction=jurisdiction,
        party_role=party_role,
        status=ContractStatus.UPLOADED,
    )
    
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    
    return contract


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    contract_type: Optional[ContractType] = None,
    status: Optional[ContractStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's contracts with pagination."""
    # Base query
    query = select(Contract).where(Contract.user_id == current_user.id)
    
    # Apply filters
    if contract_type:
        query = query.where(Contract.contract_type == contract_type)
    if status:
        query = query.where(Contract.status == status)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Contract.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    contracts = result.scalars().all()
    
    return ContractListResponse(
        items=contracts,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get contract details."""
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == current_user.id,
        )
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a contract."""
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == current_user.id,
        )
    )
    contract = result.scalar_one_or_none()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    # Delete file from storage
    file_path = Path(contract.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # Delete from database
    await db.delete(contract)
    await db.commit()
