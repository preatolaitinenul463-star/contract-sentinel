"""Web-RAG subsystem for legal document retrieval."""
from app.rag.source_registry import SourceRegistry, LegalSource
from app.rag.retriever import RagRetriever

__all__ = [
    "SourceRegistry",
    "LegalSource",
    "RagRetriever",
]
