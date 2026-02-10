"""RAG crawl and management API routes."""
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.models.rag import RagDocument, RagChunk
from app.rag.source_registry import SourceRegistry
from app.rag.fetcher import Fetcher
from app.rag.extractor import Extractor
from app.rag.indexer import Indexer

router = APIRouter()

# Shared registry instance
_source_registry = SourceRegistry()


@router.get("/sources")
async def list_sources():
    """List all configured legal document sources."""
    return {"sources": _source_registry.list_sources()}


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    """Get details for a specific source."""
    source = _source_registry.get_source(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    return {
        "id": source.id,
        "name": source.name,
        "jurisdiction": source.jurisdiction,
        "base_url": source.base_url,
        "seed_urls": source.seed_urls,
        "rate_limit": source.rate_limit,
        "enabled": source.enabled,
    }


@router.get("/stats")
async def rag_stats(db: AsyncSession = Depends(get_db)):
    """Get RAG system statistics."""
    doc_count_result = await db.execute(select(func.count(RagDocument.id)))
    doc_count = doc_count_result.scalar() or 0

    chunk_count_result = await db.execute(select(func.count(RagChunk.id)))
    chunk_count = chunk_count_result.scalar() or 0

    # Last crawled
    last_crawl_result = await db.execute(
        select(RagDocument.last_crawled_at)
        .order_by(RagDocument.last_crawled_at.desc())
        .limit(1)
    )
    last_crawled = last_crawl_result.scalar()

    # Documents per source
    source_stats_result = await db.execute(
        select(
            RagDocument.source_id,
            func.count(RagDocument.id),
        ).group_by(RagDocument.source_id)
    )
    source_stats = {row[0]: row[1] for row in source_stats_result.all()}

    return {
        "total_documents": doc_count,
        "total_chunks": chunk_count,
        "last_crawled_at": last_crawled.isoformat() if last_crawled else None,
        "documents_per_source": source_stats,
        "configured_sources": len(_source_registry.list_sources()),
    }


@router.post("/crawl")
async def trigger_crawl(
    source_id: Optional[str] = None,
    max_depth: int = 2,
    max_pages: int = 50,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a BFS crawl for a specific source or all sources.

    Crawls seed URLs, discovers child links, and recursively indexes content.
    Runs in the background to avoid request timeouts.
    
    - max_depth: how many link hops from seed URLs (default 2)
    - max_pages: maximum total pages to crawl per source (default 50)
    """
    if source_id:
        source = _source_registry.get_source(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source '{source_id}' not found",
            )
        sources = [source]
    else:
        sources = [
            _source_registry.get_source(s["id"])
            for s in _source_registry.list_sources()
            if s["enabled"]
        ]

    # Run crawl in background
    background_tasks.add_task(_crawl_sources_bfs, sources, max_depth, max_pages)

    return {
        "status": "crawl_started",
        "sources": [s.id for s in sources],
        "max_depth": max_depth,
        "max_pages": max_pages,
        "message": f"BFS crawling {len(sources)} source(s) in background",
    }


async def _crawl_sources_bfs(sources, max_depth: int = 2, max_pages: int = 50):
    """Background task: BFS crawl a list of sources with recursive link discovery."""
    from collections import deque
    from app.database import async_session_maker

    fetcher = Fetcher(_source_registry)
    extractor = Extractor()

    for source in sources:
        if not source or not source.enabled:
            continue

        effective_depth = min(max_depth, source.max_depth)
        logger.info(
            f"BFS crawling source: {source.id} ({source.name}), "
            f"max_depth={effective_depth}, max_pages={max_pages}"
        )

        # BFS queue: (url, depth)
        visited: set = set()
        queue: deque = deque()
        pages_crawled = 0

        # Seed the queue
        for seed_url in source.seed_urls:
            if seed_url not in visited:
                queue.append((seed_url, 0))
                visited.add(seed_url)

        while queue and pages_crawled < max_pages:
            url, depth = queue.popleft()

            try:
                # Fetch
                fetch_result = await fetcher.fetch(url, source.id)
                if not fetch_result:
                    continue

                pages_crawled += 1

                # Extract content
                doc = extractor.extract(
                    fetch_result.content, fetch_result.url, source.id
                )

                # Index if content is meaningful
                if doc.content and len(doc.content) >= 50:
                    async with async_session_maker() as db:
                        indexer = Indexer(db)
                        content_hash = hashlib.sha256(
                            doc.content.encode()
                        ).hexdigest()
                        await indexer.index_document(doc, source.id, content_hash)
                    logger.info(f"Indexed [{depth}]: {doc.title} ({url})")

                # Discover child links if not at max depth
                if depth < effective_depth:
                    child_links = extractor.extract_links(
                        fetch_result.content, fetch_result.url
                    )
                    for link in child_links:
                        if link not in visited and _source_registry.is_url_allowed(
                            link, source.id
                        ):
                            visited.add(link)
                            queue.append((link, depth + 1))

            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                continue

        logger.info(
            f"Source {source.id} crawl complete: "
            f"{pages_crawled} pages, {len(visited)} URLs discovered"
        )

    logger.info("All sources crawl complete")


@router.get("/documents")
async def list_documents(
    source_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List indexed RAG documents."""
    query = select(RagDocument).order_by(RagDocument.last_crawled_at.desc())

    if source_id:
        query = query.where(RagDocument.source_id == source_id)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    docs = result.scalars().all()

    return {
        "items": [
            {
                "id": d.id,
                "source_id": d.source_id,
                "url": d.url,
                "title": d.title,
                "institution": d.institution,
                "doc_type": d.doc_type,
                "last_crawled_at": d.last_crawled_at.isoformat() if d.last_crawled_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
