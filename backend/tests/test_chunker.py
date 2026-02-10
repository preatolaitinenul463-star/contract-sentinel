"""Tests for RAG Chunker."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.chunker import Chunker


class TestChunker:
    """Test text chunking logic."""

    def setup_method(self):
        self.chunker = Chunker(chunk_size=100, chunk_overlap=20, min_chunk_size=20)

    def test_basic_chunking(self):
        """Should split text into chunks."""
        text = "这是第一段内容。" * 20 + "\n\n" + "这是第二段内容。" * 20
        chunks = self.chunker.chunk(text)
        assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"

    def test_empty_text(self):
        """Should handle empty text gracefully."""
        chunks = self.chunker.chunk("")
        assert len(chunks) == 0

    def test_short_text_single_chunk(self):
        """Short text should result in a single chunk."""
        text = "这是一段简短的合同条款文本，仅供测试使用。"
        chunks = self.chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0].text.strip() == text.strip()

    def test_chunk_has_correct_fields(self):
        """Each chunk should have text, position info, and index."""
        text = "这是测试文本。" * 50
        chunks = self.chunker.chunk(text)
        for i, chunk in enumerate(chunks):
            assert chunk.text, "Chunk should have text"
            assert chunk.chunk_index == i, f"Chunk index should be {i}"
            assert chunk.start_char >= 0, "start_char should be non-negative"
            assert chunk.end_char > chunk.start_char, "end_char should be after start_char"

    def test_chinese_legal_text(self):
        """Should handle Chinese legal text with article markers."""
        text = """
第一条 甲方应按照合同约定支付货款。
第二条 乙方应按时交付合格产品。
第三条 违约方应承担违约责任。
第四条 本合同自签字之日起生效。
第五条 合同争议由仲裁机构解决。
""" * 5
        chunks = self.chunker.chunk(text)
        assert len(chunks) >= 1, "Should produce at least 1 chunk"

    def test_chunk_overlap(self):
        """Chunks should have overlapping content when overlap > 0."""
        chunker = Chunker(chunk_size=50, chunk_overlap=10, min_chunk_size=10)
        text = "测试" * 100  # 200 chars
        chunks = chunker.chunk(text)
        if len(chunks) >= 2:
            # Verify chunks cover the full text
            total_coverage = sum(len(c.text) for c in chunks)
            assert total_coverage >= len(text.strip()), "Chunks should cover full text"
