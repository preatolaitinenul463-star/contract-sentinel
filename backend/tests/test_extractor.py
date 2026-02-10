"""Tests for RAG Extractor."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.extractor import Extractor


class TestExtractor:
    """Test HTML content extraction logic."""

    def setup_method(self):
        self.extractor = Extractor()

    def test_extract_title_from_h1(self):
        """Should extract title from h1 tag."""
        html = "<html><body><h1>中华人民共和国民法典</h1><p>Some content here that is long enough.</p></body></html>"
        doc = self.extractor.extract(html, "https://example.com/law1", "cn_npc")
        assert doc.title == "中华人民共和国民法典"

    def test_extract_content(self):
        """Should extract body content."""
        html = """
        <html><body>
            <article>
                <p>第一条 为了保护民事主体的合法权益，调整民事关系，维护社会和经济秩序。</p>
                <p>第二条 民法调整平等主体的自然人、法人和非法人组织之间的人身关系和财产关系。</p>
            </article>
        </body></html>
        """
        doc = self.extractor.extract(html, "https://example.com/law2", "cn_npc")
        assert len(doc.content) > 20, "Should extract content"
        assert "民事主体" in doc.content

    def test_extract_date_chinese_format(self):
        """Should parse Chinese date format."""
        html = """
        <html><body>
            <p>2024年3月15日发布</p>
            <p>This is enough content for extraction to work properly with the parser.</p>
        </body></html>
        """
        doc = self.extractor.extract(html, "https://example.com/law3", "cn_npc")
        assert doc.published_date is not None
        assert doc.published_date.year == 2024
        assert doc.published_date.month == 3
        assert doc.published_date.day == 15

    def test_extract_institution(self):
        """Should map source_id to institution name."""
        html = "<html><body><h1>Test</h1><p>Some content that is long enough for extraction.</p></body></html>"
        doc = self.extractor.extract(html, "https://example.com", "cn_npc")
        assert doc.institution == "全国人民代表大会"

    def test_empty_html(self):
        """Should handle empty HTML gracefully."""
        doc = self.extractor.extract("", "https://example.com", "cn_npc")
        assert doc.content == "" or doc.content is not None

    def test_extract_links(self):
        """Should extract and normalize links from HTML."""
        html = """
        <html><body>
            <a href="/laws/123">Law 123</a>
            <a href="https://flk.npc.gov.cn/detail?id=456">Law 456</a>
            <a href="#section1">Section 1</a>
            <a href="javascript:void(0)">Click</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="/images/photo.jpg">Photo</a>
        </body></html>
        """
        links = self.extractor.extract_links(html, "https://flk.npc.gov.cn")
        # Should include the valid links
        assert any("laws/123" in l for l in links), "Should extract relative link"
        assert any("detail" in l for l in links), "Should extract absolute link"
        # Should exclude anchors, javascript, mailto, and images
        assert not any("#section1" in l for l in links), "Should exclude anchors"
        assert not any("javascript" in l for l in links), "Should exclude javascript"
        assert not any("mailto" in l for l in links), "Should exclude mailto"
        assert not any(".jpg" in l for l in links), "Should exclude image files"

    def test_extract_links_deduplication(self):
        """Should deduplicate links."""
        html = """
        <html><body>
            <a href="/page1">Page 1</a>
            <a href="/page1">Page 1 Again</a>
            <a href="/page1#section">Page 1 with fragment</a>
        </body></html>
        """
        links = self.extractor.extract_links(html, "https://example.com")
        page1_links = [l for l in links if "page1" in l]
        assert len(page1_links) == 1, f"Should deduplicate, got {page1_links}"

    def test_noise_removal(self):
        """Should remove script, style, and nav elements."""
        html = """
        <html><body>
            <nav>Navigation links here</nav>
            <script>alert('test')</script>
            <article><p>This is the main content of the legal document that should be extracted.</p></article>
            <footer>Footer content</footer>
        </body></html>
        """
        doc = self.extractor.extract(html, "https://example.com", "cn_npc")
        assert "Navigation" not in doc.content
        assert "alert" not in doc.content
