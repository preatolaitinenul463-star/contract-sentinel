"""Contract model."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ContractType(str, enum.Enum):
    """Contract types."""
    GENERAL = "general"  # 通用商事合同
    LABOR = "labor"  # 劳动合同
    TECH = "tech"  # 技术/软件/外包合同
    NDA = "nda"  # 保密协议
    LEASE = "lease"  # 租赁合同
    SALES = "sales"  # 买卖合同
    SERVICE = "service"  # 服务合同
    OTHER = "other"


class Jurisdiction(str, enum.Enum):
    """Legal jurisdictions."""
    CN = "CN"  # 中国大陆
    HK = "HK"  # 香港
    SG = "SG"  # 新加坡
    US = "US"  # 美国
    UK = "UK"  # 英国
    OTHER = "OTHER"


class ContractStatus(str, enum.Enum):
    """Contract processing status."""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    REVIEWING = "reviewing"
    REVIEWED = "reviewed"
    ERROR = "error"


class PartyRole(str, enum.Enum):
    """User's role in the contract."""
    PARTY_A = "party_a"  # 甲方
    PARTY_B = "party_b"  # 乙方
    EMPLOYER = "employer"  # 雇主
    EMPLOYEE = "employee"  # 雇员
    BUYER = "buyer"  # 买方
    SELLER = "seller"  # 卖方
    UNKNOWN = "unknown"


class Contract(Base):
    """Contract document model."""
    
    __tablename__ = "contracts"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer)  # bytes
    mime_type: Mapped[str] = mapped_column(String(100))
    
    # Contract metadata
    contract_type: Mapped[ContractType] = mapped_column(
        SqlEnum(ContractType), 
        default=ContractType.GENERAL
    )
    jurisdiction: Mapped[Jurisdiction] = mapped_column(
        SqlEnum(Jurisdiction), 
        default=Jurisdiction.CN
    )
    party_role: Mapped[PartyRole] = mapped_column(
        SqlEnum(PartyRole), 
        default=PartyRole.UNKNOWN
    )
    
    # Parsed content
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Status
    status: Mapped[ContractStatus] = mapped_column(
        SqlEnum(ContractStatus), 
        default=ContractStatus.UPLOADED
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Data retention
    
    # Relationships
    user = relationship("User", back_populates="contracts")
    review_results = relationship("ReviewResult", back_populates="contract", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<Contract(id={self.id}, filename={self.filename})>"
