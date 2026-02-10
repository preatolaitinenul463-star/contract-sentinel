"""Chunker - splits documents into chunks for embedding."""
from dataclasses import dataclass
from typing import List
import re


@dataclass
class TextChunk:
    """A chunk of text with position info."""
    text: str
    start_char: int
    end_char: int
    chunk_index: int


class Chunker:
    """Splits text into overlapping chunks."""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk(self, text: str) -> List[TextChunk]:
        """Split text into chunks."""
        if not text or len(text) < self.min_chunk_size:
            if text:
                return [TextChunk(
                    text=text,
                    start_char=0,
                    end_char=len(text),
                    chunk_index=0,
                )]
            return []
        
        chunks = []
        
        # Try to split on paragraph boundaries first
        paragraphs = self._split_paragraphs(text)
        
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        for para_start, para_end, para_text in paragraphs:
            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para_text) > self.chunk_size:
                # Save current chunk if it's big enough
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(TextChunk(
                        text=current_chunk.strip(),
                        start_char=current_start,
                        end_char=current_start + len(current_chunk),
                        chunk_index=chunk_index,
                    ))
                    chunk_index += 1
                    
                    # Start new chunk with overlap
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else ""
                    current_chunk = overlap_text + para_text
                    current_start = para_start - len(overlap_text)
                else:
                    current_chunk += para_text
            else:
                if not current_chunk:
                    current_start = para_start
                current_chunk += para_text
        
        # Don't forget the last chunk
        if len(current_chunk) >= self.min_chunk_size:
            chunks.append(TextChunk(
                text=current_chunk.strip(),
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                chunk_index=chunk_index,
            ))
        
        return chunks
    
    def _split_paragraphs(self, text: str) -> List[tuple]:
        """Split text into paragraphs with positions."""
        paragraphs = []
        
        # Split on double newlines or Chinese paragraph markers
        pattern = r"(?:\n\n|\n(?=第[一二三四五六七八九十百]+条)|\n(?=\d+[、.]))"
        
        last_end = 0
        for match in re.finditer(pattern, text):
            para_text = text[last_end:match.start()]
            if para_text.strip():
                paragraphs.append((last_end, match.start(), para_text + "\n"))
            last_end = match.end()
        
        # Last paragraph
        if last_end < len(text):
            para_text = text[last_end:]
            if para_text.strip():
                paragraphs.append((last_end, len(text), para_text))
        
        return paragraphs
