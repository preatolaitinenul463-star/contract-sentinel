"""Base classes for LLM providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncIterator


@dataclass
class ChatMessage:
    """Chat message structure."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatResponse:
    """Chat completion response."""
    content: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    finish_reason: Optional[str] = None


@dataclass
class EmbeddingResponse:
    """Embedding response."""
    embedding: List[float]
    model: str
    tokens_used: int = 0


class ChatClient(ABC):
    """Abstract base class for chat completion clients."""
    
    def __init__(
        self,
        provider_name: str,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        default_params: Optional[Dict[str, Any]] = None,
    ):
        self.provider_name = provider_name
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.default_params = default_params or {}
    
    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ChatResponse:
        """Send chat completion request."""
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion response."""
        pass


class EmbeddingClient(ABC):
    """Abstract base class for embedding clients."""
    
    def __init__(
        self,
        provider_name: str,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        self.provider_name = provider_name
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.dimensions = dimensions
    
    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResponse]:
        """Generate embeddings for multiple texts."""
        pass
