"""OpenAI-compatible provider implementation."""
import json
from typing import Optional, List, Dict, Any, AsyncIterator

import httpx
from loguru import logger

from app.providers.base import (
    ChatClient,
    EmbeddingClient,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
)


class OpenAICompatChatClient(ChatClient):
    """OpenAI-compatible chat client."""
    
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ChatResponse:
        """Send chat completion request."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Merge default params with provided kwargs
        params = {**self.default_params, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **params,
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                
                choice = data["choices"][0]
                usage = data.get("usage", {})
                
                return ChatResponse(
                    content=choice["message"]["content"],
                    model=data.get("model", self.model),
                    tokens_input=usage.get("prompt_tokens", 0),
                    tokens_output=usage.get("completion_tokens", 0),
                    finish_reason=choice.get("finish_reason"),
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"Chat API error: status={e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Chat request failed: {e}")
                raise
    
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion response."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        params = {**self.default_params, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            **params,
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue


class OpenAICompatEmbeddingClient(EmbeddingClient):
    """OpenAI-compatible embedding client."""
    
    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]
    
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResponse]:
        """Generate embeddings for multiple texts."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "input": texts,
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                usage = data.get("usage", {})
                tokens_per_text = usage.get("total_tokens", 0) // len(texts) if texts else 0
                
                for item in data["data"]:
                    results.append(EmbeddingResponse(
                        embedding=item["embedding"],
                        model=data.get("model", self.model),
                        tokens_used=tokens_per_text,
                    ))
                
                return results
            except httpx.HTTPStatusError as e:
                logger.error(f"Embedding API error: status={e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Embedding request failed: {e}")
                raise
