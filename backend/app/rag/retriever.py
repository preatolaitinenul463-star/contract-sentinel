"""Retriever - retrieves relevant documents using semantic search."""
from typing import List, Dict, Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.rag import RagDocument, RagChunk
from app.providers import get_provider_registry
from app.config import settings


class RagRetriever:
    """Retrieves relevant documents using semantic search."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = get_provider_registry()
        self._is_sqlite = settings.database_url.startswith("sqlite")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        jurisdiction: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents using semantic or keyword search."""
        try:
            if self._is_sqlite:
                # SQLite does not support pgvector; fall back to keyword search
                keywords = [w for w in query.split() if len(w) >= 2][:5]
                if keywords:
                    return await self.search_keyword(keywords, top_k=top_k)
                return []

            # PostgreSQL with pgvector: use semantic search
            return await self._search_pgvector(query, top_k, jurisdiction, source_ids)

        except Exception as e:
            logger.error(f"Semantic search failed, falling back to keyword: {e}")
            keywords = [w for w in query.split() if len(w) >= 2][:5]
            if keywords:
                return await self.search_keyword(keywords, top_k=top_k)
            return []

    async def _search_pgvector(
        self,
        query: str,
        top_k: int,
        jurisdiction: Optional[str],
        source_ids: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Semantic search using pgvector."""
        # Get query embedding
        embedding_client = self.registry.get_embedding_client()
        query_embedding = await embedding_client.embed(query)

        # Build parameterized SQL for pgvector similarity search
        params: Dict[str, Any] = {
            "embedding": query_embedding.embedding,
            "top_k": top_k,
        }

        where_clauses = ["c.embedding IS NOT NULL"]

        if source_ids:
            where_clauses.append("d.source_id = ANY(:source_ids)")
            params["source_ids"] = source_ids

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT
                c.id,
                c.chunk_text,
                c.document_id,
                d.url,
                d.title,
                d.source_id,
                d.institution,
                c.embedding <-> :embedding::vector AS distance
            FROM rag_chunks c
            JOIN rag_documents d ON c.document_id = d.id
            WHERE {where_sql}
            ORDER BY distance
            LIMIT :top_k
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "text": row[1],
                "document_id": row[2],
                "url": row[3],
                "title": row[4],
                "source": row[6] or row[5],  # institution or source_id
                "distance": row[7],
            })

        return results

    async def search_keyword(
        self,
        keywords: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fallback keyword-based search."""
        results = []

        for keyword in keywords:
            query = (
                select(RagChunk, RagDocument)
                .join(RagDocument)
                .where(RagChunk.chunk_text.ilike(f"%{keyword}%"))
                .limit(top_k)
            )

            result = await self.db.execute(query)
            rows = result.all()

            for chunk, doc in rows:
                results.append({
                    "chunk_id": chunk.id,
                    "text": chunk.chunk_text,
                    "document_id": doc.id,
                    "url": doc.url,
                    "title": doc.title,
                    "source": doc.institution or doc.source_id,
                    "distance": None,
                })

        # Deduplicate
        seen = set()
        unique_results = []
        for r in results:
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                unique_results.append(r)

        return unique_results[:top_k]
