"""Extractor - extracts clean text and links from HTML."""
import re
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class ExtractedDocument:
    """Extracted document content."""
    url: str
    title: str
    content: str
    published_date: Optional[datetime]
    institution: Optional[str]
    doc_type: Optional[str]
    

class Extractor:
    """Extracts clean text and metadata from HTML."""
    
    # Common noise patterns to remove
    NOISE_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"<style[^>]*>.*?</style>",
        r"<nav[^>]*>.*?</nav>",
        r"<header[^>]*>.*?</header>",
        r"<footer[^>]*>.*?</footer>",
        r"<!--.*?-->",
    ]
    
    def extract(self, html: str, url: str, source_id: str) -> ExtractedDocument:
        """Extract document from HTML."""
        # Remove noise
        for pattern in self.NOISE_PATTERNS:
            html = re.sub(pattern, "", html, flags=re.DOTALL | re.IGNORECASE)
        
        soup = BeautifulSoup(html, "lxml")
        
        # Extract title
        title = self._extract_title(soup)
        
        # Extract main content
        content = self._extract_content(soup)
        
        # Extract metadata
        published_date = self._extract_date(soup, html)
        institution = self._extract_institution(soup, source_id)
        doc_type = self._extract_doc_type(soup, url)
        
        return ExtractedDocument(
            url=url,
            title=title,
            content=content,
            published_date=published_date,
            institution=institution,
            doc_type=doc_type,
        )
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract document title."""
        # Try various title selectors
        selectors = [
            "h1",
            ".title",
            ".article-title",
            "title",
            "[class*='title']",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and elem.get_text(strip=True):
                return elem.get_text(strip=True)
        
        return "Untitled"
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content."""
        # Try to find main content area
        content_selectors = [
            "article",
            "main",
            ".content",
            ".article-content",
            "#content",
            ".main-content",
            "[class*='content']",
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator="\n", strip=True)
                if len(text) > 100:  # Minimum content length
                    return self._clean_text(text)
        
        # Fallback to body
        body = soup.find("body")
        if body:
            text = body.get_text(separator="\n", strip=True)
            return self._clean_text(text)
        
        return ""
    
    def _extract_date(self, soup: BeautifulSoup, html: str) -> Optional[datetime]:
        """Extract publication date."""
        # Try meta tags
        date_meta_names = ["pubdate", "publishdate", "date", "DC.date"]
        for name in date_meta_names:
            meta = soup.find("meta", attrs={"name": name})
            if meta and meta.get("content"):
                try:
                    return self._parse_date(meta["content"])
                except:
                    pass
        
        # Try common date patterns in text
        date_patterns = [
            r"(\d{4}年\d{1,2}月\d{1,2}日)",
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{4}/\d{2}/\d{2})",
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    return self._parse_date(match.group(1))
                except:
                    pass
        
        return None
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        # Handle Chinese date format
        if "年" in date_str:
            date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "")
        
        date_str = date_str.replace("/", "-")
        
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    
    def _extract_institution(self, soup: BeautifulSoup, source_id: str) -> Optional[str]:
        """Extract publishing institution."""
        # Map source IDs to institutions
        institution_map = {
            "cn_npc": "全国人民代表大会",
            "cn_gov": "国务院",
            "cn_court": "最高人民法院",
            "cn_cac": "国家互联网信息办公室",
            "hk_eleg": "香港特别行政区政府",
            "sg_sso": "Singapore Government",
            "uk_leg": "UK Government",
            "us_ecfr": "US Government",
        }
        
        return institution_map.get(source_id)
    
    def _extract_doc_type(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract document type."""
        # Try to determine from URL or content
        type_patterns = {
            "law": ["法", "law", "act", "statute"],
            "regulation": ["条例", "规定", "办法", "regulation"],
            "interpretation": ["解释", "interpretation"],
            "notice": ["通知", "公告", "notice"],
            "guideline": ["指南", "guide", "guideline"],
        }
        
        url_lower = url.lower()
        for doc_type, patterns in type_patterns.items():
            for pattern in patterns:
                if pattern in url_lower:
                    return doc_type
        
        return "document"
    
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract all navigable links from HTML and convert to absolute URLs.
        
        Filters out non-content links (login, search, anchors, media, etc.).
        """
        soup = BeautifulSoup(html, "lxml")
        links = []
        seen = set()

        # Non-content path patterns to exclude
        skip_patterns = re.compile(
            r"/(login|logout|register|search|tag|user|api|admin|static|css|js|img|font)",
            re.IGNORECASE,
        )
        skip_extensions = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip", ".css", ".js"}

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()

            # Skip empty, anchors, javascript, mailto
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)

            # Normalize: remove fragment
            parsed = urlparse(absolute_url)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized += f"?{parsed.query}"

            # Skip if already seen
            if normalized in seen:
                continue
            seen.add(normalized)

            # Skip non-http(s)
            if parsed.scheme not in ("http", "https"):
                continue

            # Skip non-content paths
            if skip_patterns.search(parsed.path):
                continue

            # Skip media/asset files
            ext = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""
            if f".{ext}" in skip_extensions:
                continue

            links.append(normalized)

        return links

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove very short lines (likely navigation)
        lines = text.split("\n")
        lines = [l.strip() for l in lines if len(l.strip()) > 10]
        return "\n".join(lines)
