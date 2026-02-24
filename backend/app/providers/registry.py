"""Provider registry - loads and manages LLM providers."""
import os
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

import yaml
from loguru import logger

from app.config import settings
from app.providers.base import ChatClient, EmbeddingClient
from app.providers.openai_compat import OpenAICompatChatClient, OpenAICompatEmbeddingClient


class ProviderConfig:
    """Configuration for a single provider."""
    
    def __init__(self, config: Dict[str, Any]):
        self.name = config.get("name", "Unknown")
        self.provider_type = config.get("provider_type", "openai-compatible")
        self.enabled = config.get("enabled", True)
        self.connection = config.get("connection", {})
        self.default_model = config.get("default_model")
        self.defaults = config.get("defaults", {})
        self.models = config.get("models", [])
        self.embedding = config.get("embedding")
    
    @property
    def base_url(self) -> str:
        """Get base URL, resolving environment variables."""
        url = self.connection.get("base_url", "")
        # Handle ${VAR:default} syntax
        if url.startswith("${") and "}" in url:
            var_part = url[2:url.index("}")]
            if ":" in var_part:
                var_name, default = var_part.split(":", 1)
            else:
                var_name, default = var_part, ""
            return os.environ.get(var_name, default)
        return url
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from environment or settings."""
        key_env = self.connection.get("api_key_env")
        if key_env:
            # Try os.environ first, then fall back to settings attribute
            val = os.environ.get(key_env)
            if val:
                return val
            # Map env var names to settings attributes
            attr_name = key_env.lower()  # e.g. DEEPSEEK_API_KEY -> deepseek_api_key
            try:
                return getattr(settings, attr_name, None)
            except Exception:
                return None
        return None


class ProviderRegistry:
    """Registry for managing LLM providers."""
    
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {}
        self._chat_clients: Dict[str, ChatClient] = {}
        self._embedding_clients: Dict[str, EmbeddingClient] = {}
    
    def load_from_directory(self, config_dir: Path) -> None:
        """Load all provider configs from a directory."""
        if not config_dir.exists():
            logger.warning("Provider config directory not found")
            return
        
        for yaml_file in config_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                
                if config:
                    provider_id = yaml_file.stem
                    provider_config = ProviderConfig(config)
                    
                    if provider_config.enabled:
                        self.providers[provider_id] = provider_config
                        logger.info(f"Loaded provider: {provider_config.name} ({provider_id})")
                    else:
                        logger.debug(f"Provider disabled: {provider_config.name}")
            except Exception:
                logger.error("Failed to load provider config")
    
    def get_chat_client(
        self,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ChatClient:
        """Get a chat client for the specified provider and model."""
        # Use default provider if not specified
        if provider_id is None:
            provider_id = settings.default_chat_provider
        
        provider = self.providers.get(provider_id)
        if not provider:
            raise ValueError(f"Provider not found: {provider_id}")
        
        # Use default model if not specified
        if model is None:
            model = settings.default_chat_model or provider.default_model
        
        # Cache key
        cache_key = f"{provider_id}:{model}"
        
        if cache_key not in self._chat_clients:
            # Create client based on provider type
            if provider.provider_type in ("openai", "openai-compatible"):
                client = OpenAICompatChatClient(
                    provider_name=provider.name,
                    model=model,
                    base_url=provider.base_url,
                    api_key=provider.api_key,
                    default_params=provider.defaults,
                )
            else:
                raise ValueError(f"Unsupported provider type: {provider.provider_type}")
            
            self._chat_clients[cache_key] = client
        
        return self._chat_clients[cache_key]
    
    def get_embedding_client(
        self,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> EmbeddingClient:
        """Get an embedding client for the specified provider and model."""
        # Use default provider if not specified
        if provider_id is None:
            provider_id = settings.default_embedding_provider
        
        provider = self.providers.get(provider_id)
        if not provider:
            raise ValueError(f"Provider not found: {provider_id}")
        
        if not provider.embedding:
            raise ValueError(f"Provider {provider_id} does not support embeddings")
        
        # Use default model if not specified
        if model is None:
            model = settings.default_embedding_model or provider.embedding.get("default_model")
        
        # Cache key
        cache_key = f"{provider_id}:{model}"
        
        if cache_key not in self._embedding_clients:
            embedding_config = provider.embedding
            dimensions = None
            
            # Find model dimensions
            for m in embedding_config.get("models", []):
                if m["id"] == model:
                    dimensions = m.get("dimensions")
                    break
            
            if provider.provider_type in ("openai", "openai-compatible"):
                client = OpenAICompatEmbeddingClient(
                    provider_name=provider.name,
                    model=model,
                    base_url=provider.base_url,
                    api_key=provider.api_key,
                    dimensions=dimensions,
                )
            else:
                raise ValueError(f"Unsupported provider type: {provider.provider_type}")
            
            self._embedding_clients[cache_key] = client
        
        return self._embedding_clients[cache_key]
    
    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all available providers and their models."""
        result = {}
        for provider_id, config in self.providers.items():
            result[provider_id] = {
                "name": config.name,
                "type": config.provider_type,
                "models": [m["id"] for m in config.models],
                "embedding_models": (
                    [m["id"] for m in config.embedding.get("models", [])]
                    if config.embedding else []
                ),
            }
        return result


# Global registry instance
_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    global _registry
    
    if _registry is None:
        _registry = ProviderRegistry()
        # Load from config directory
        config_dir = Path(__file__).parent.parent.parent / "configs" / "providers"
        _registry.load_from_directory(config_dir)
    
    return _registry
