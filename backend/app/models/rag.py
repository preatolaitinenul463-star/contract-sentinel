"""RAG (Retrieval-Augmented Generation) models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RagDocument(Base):
    """RAG document from web sources."""
    
    __tablename__ = "rag_documents"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Source information
    source_id: Mapped[str] = mapped_column(String(50), index=True)  # e.g., "cn_npc", "hk_eleg"
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    
    # Document metadata
    title: Mapped[str] = mapped_column(String(500))
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    institution: Mapped[Optional[str]] = mapped_column(String(200))  # 发布机构
    doc_type: Mapped[Optional[str]] = mapped_column(String(100))  # 法规/公告/解释等
    
    # Content
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    
    # Crawl metadata
    last_crawled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    etag: Mapped[Optional[str]] = mapped_column(String(200))
    last_modified: Mapped[Optional[str]] = mapped_column(String(200))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    chunks = relationship("RagChunk", back_populates="document", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<RagDocument(id={self.id}, title={self.title[:50]})>"


class RagChunk(Base):
    """RAG document chunk with embedding."""
    
    __tablename__ = "rag_chunks"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("rag_documents.id"), index=True)
    
    # Chunk content
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer)  # Position in document
    
    # Embedding vector - stored as JSON for SQLite compatibility
    # For PostgreSQL with pgvector, change to: mapped_column(Vector(1536))
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Metadata
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("RagDocument", back_populates="chunks")
    
    def __repr__(self) -> str:
        return f"<RagChunk(id={self.id}, doc={self.document_id}, idx={self.chunk_index})>"
