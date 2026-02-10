"""Fetcher - crawls legal documents with rate limiting and caching."""
import asyncio
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

import httpx
from loguru import logger

from app.rag.source_registry import SourceRegistry, LegalSource


@dataclass
class FetchResult:
    """Result of fetching a URL."""
    url: str
    content: str
    content_hash: str
    status_code: int
    content_type: Optional[str]
    etag: Optional[str]
    last_modified: Optional[str]
    fetched_at: datetime


class RateLimiter:
    """Simple rate limiter per domain."""
    
    def __init__(self):
        self._last_request: Dict[str, float] = {}
    
    async def wait(self, domain: str, rate_limit: float) -> None:
        """Wait if needed to respect rate limit."""
        now = asyncio.get_event_loop().time()
        last = self._last_request.get(domain, 0)
        
        wait_time = (1 / rate_limit) - (now - last)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        self._last_request[domain] = asyncio.get_event_loop().time()


class Fetcher:
    """Fetches web pages with rate limiting and caching."""
    
    def __init__(self, source_registry: SourceRegistry = None):
        self.source_registry = source_registry or SourceRegistry()
        self.rate_limiter = RateLimiter()
        self._cache: Dict[str, FetchResult] = {}
    
    async def fetch(
        self,
        url: str,
        source_id: str,
        use_cache: bool = True,
        if_none_match: Optional[str] = None,
        if_modified_since: Optional[str] = None,
    ) -> Optional[FetchResult]:
        """Fetch a URL respecting robots and rate limits."""
        source = self.source_registry.get_source(source_id)
        if not source:
            logger.warning(f"Unknown source: {source_id}")
            return None
        
        # Check if URL is allowed
        if not self.source_registry.is_url_allowed(url, source_id):
            logger.warning(f"URL not allowed: {url}")
            return None
        
        # Check cache
        if use_cache and url in self._cache:
            cached = self._cache[url]
            # Cache valid for 24 hours
            if (datetime.utcnow() - cached.fetched_at).total_seconds() < 86400:
                return cached
        
        # Rate limiting
        domain = urlparse(url).netloc
        await self.rate_limiter.wait(domain, source.rate_limit)
        
        # Fetch
        headers = {
            "User-Agent": "ContractSentinel/1.0 (Legal Research Bot; +https://contract-sentinel.ai)",
        }
        if if_none_match:
            headers["If-None-Match"] = if_none_match
        if if_modified_since:
            headers["If-Modified-Since"] = if_modified_since
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
                
                # Handle 304 Not Modified
                if response.status_code == 304:
                    if url in self._cache:
                        return self._cache[url]
                    return None
                
                response.raise_for_status()
                
                content = response.text
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                
                result = FetchResult(
                    url=url,
                    content=content,
                    content_hash=content_hash,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    etag=response.headers.get("etag"),
                    last_modified=response.headers.get("last-modified"),
                    fetched_at=datetime.utcnow(),
                )
                
                # Cache
                self._cache[url] = result
                
                return result
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return None
    
    async def check_robots(self, base_url: str) -> Dict[str, Any]:
        """Check robots.txt for a site."""
        robots_url = urljoin(base_url, "/robots.txt")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    return self._parse_robots(response.text)
            except Exception:
                pass
        
        return {"allowed": True, "crawl_delay": None}
    
    def _parse_robots(self, content: str) -> Dict[str, Any]:
        """Parse robots.txt content."""
        result = {"allowed": True, "crawl_delay": None, "disallow": []}
        
        current_agent = None
        for line in content.split("\n"):
            line = line.strip().lower()
            
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                if agent == "*" or "contractsentinel" in agent:
                    current_agent = agent
            elif current_agent and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    result["disallow"].append(path)
            elif current_agent and line.startswith("crawl-delay:"):
                try:
                    result["crawl_delay"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        
        return result
