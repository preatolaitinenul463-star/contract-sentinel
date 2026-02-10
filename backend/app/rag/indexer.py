"""Indexer - indexes documents into vector store."""
from typing import List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.rag import RagDocument, RagChunk
from app.providers import get_provider_registry
from app.rag.extractor import ExtractedDocument
from app.rag.chunker import Chunker, TextChunk


class Indexer:
    """Indexes documents into the vector store."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.chunker = Chunker()
        self.registry = get_provider_registry()
    
    async def index_document(
        self,
        doc: ExtractedDocument,
        source_id: str,
        content_hash: str,
    ) -> RagDocument:
        """Index a document and its chunks."""
        # Check if already indexed
        result = await self.db.execute(
            select(RagDocument).where(RagDocument.url == doc.url)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update if content changed
            if existing.content_hash != content_hash:
                existing.content = doc.content
                existing.content_hash = content_hash
                existing.title = doc.title
                existing.published_date = doc.published_date
                existing.last_crawled_at = datetime.utcnow()
                
                # Re-index chunks
                await self._delete_chunks(existing.id)
                await self._create_chunks(existing, doc.content)
                
                await self.db.commit()
                logger.info(f"Updated document: {doc.url}")
            
            return existing
        
        # Create new document
        rag_doc = RagDocument(
            source_id=source_id,
            url=doc.url,
            title=doc.title,
            content=doc.content,
            content_hash=content_hash,
            published_date=doc.published_date,
            institution=doc.institution,
            doc_type=doc.doc_type,
            last_crawled_at=datetime.utcnow(),
        )
        
        self.db.add(rag_doc)
        await self.db.flush()  # Get the ID
        
        # Create chunks
        await self._create_chunks(rag_doc, doc.content)
        
        await self.db.commit()
        logger.info(f"Indexed new document: {doc.url}")
        
        return rag_doc
    
    async def _create_chunks(self, doc: RagDocument, content: str) -> None:
        """Create chunks for a document."""
        chunks = self.chunker.chunk(content)
        
        if not chunks:
            return
        
        # Get embeddings
        try:
            embedding_client = self.registry.get_embedding_client()
            texts = [c.text for c in chunks]
            embeddings = await embedding_client.embed_batch(texts)
        except Exception as e:
            logger.warning(f"Failed to generate embeddings: {e}")
            embeddings = [None] * len(chunks)
        
        # Create chunk records
        for i, chunk in enumerate(chunks):
            embedding = embeddings[i].embedding if i < len(embeddings) and embeddings[i] else None
            
            rag_chunk = RagChunk(
                document_id=doc.id,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
                embedding=embedding,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
            )
            self.db.add(rag_chunk)
    
    async def _delete_chunks(self, document_id: int) -> None:
        """Delete all chunks for a document."""
        result = await self.db.execute(
            select(RagChunk).where(RagChunk.document_id == document_id)
        )
        chunks = result.scalars().all()
        for chunk in chunks:
            await self.db.delete(chunk)
