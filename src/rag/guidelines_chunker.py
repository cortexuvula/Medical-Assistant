"""
Structure-Aware Chunking for Clinical Guidelines.

Improves on flat sentence-based chunking by detecting and preserving:
- Section headings (markdown #, Section X.Y, ALL CAPS)
- Numbered recommendations
- Table structures
- Preserves section heading as prefix on each chunk from that section

Falls back to standard sentence splitting for unstructured text.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Default chunk size in tokens (approx 4 chars per token)
DEFAULT_MAX_CHUNK_TOKENS = 300
DEFAULT_OVERLAP_TOKENS = 50

# Patterns for detecting section boundaries
HEADING_PATTERNS = [
    re.compile(r'^#{1,4}\s+.+', re.MULTILINE),                    # Markdown headings
    re.compile(r'^(?:Section|SECTION)\s+\d+(?:\.\d+)*\s*[:\.]?\s*.+', re.MULTILINE),  # Section X.Y
    re.compile(r'^[A-Z][A-Z\s]{4,}$', re.MULTILINE),             # ALL CAPS lines (min 5 chars)
    re.compile(r'^\d+\.\s+[A-Z].{10,}$', re.MULTILINE),          # Numbered section headers
]

# Patterns for recommendation boundaries
RECOMMENDATION_PATTERNS = [
    re.compile(r'(?:Class\s+(?:I{1,3}|IIa|IIb))', re.IGNORECASE),
    re.compile(r'(?:Level\s+(?:A|B|B-R|B-NR|C|C-LD|C-EO))', re.IGNORECASE),
    re.compile(r'(?:Recommendation|RECOMMENDATION)\s*\d*\s*[:\.]', re.IGNORECASE),
    re.compile(r'(?:COR|LOE)\s*[:=]?\s*(?:I{1,3}|IIa|IIb|A|B|C)', re.IGNORECASE),
]


@dataclass
class GuidelineChunkResult:
    """A chunk produced by the guidelines chunker."""
    chunk_index: int
    chunk_text: str
    token_count: int
    section_heading: Optional[str] = None
    is_recommendation: bool = False


@dataclass
class Section:
    """A detected section in the document."""
    heading: str
    content: str
    start_pos: int
    end_pos: int
    level: int = 1


class GuidelinesChunker:
    """Structure-aware chunker for clinical guideline documents.

    Detects section headings and recommendation boundaries to produce
    semantically meaningful chunks that preserve document structure.
    """

    def __init__(
        self,
        max_chunk_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
        preserve_headings: bool = True,
    ):
        self._max_chunk_tokens = max_chunk_tokens
        self._overlap_tokens = overlap_tokens
        self._preserve_headings = preserve_headings

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (approx 4 chars per token)."""
        return len(text) // 4

    def _detect_sections(self, text: str) -> list[Section]:
        """Detect section boundaries in the text.

        Returns:
            List of Section objects in document order.
        """
        boundaries = []

        for pattern in HEADING_PATTERNS:
            for match in pattern.finditer(text):
                heading_text = match.group(0).strip()
                # Skip very short headings (likely false positives)
                if len(heading_text) < 3:
                    continue
                # Determine heading level
                level = 1
                if heading_text.startswith('#'):
                    level = len(heading_text) - len(heading_text.lstrip('#'))
                boundaries.append((match.start(), heading_text, level))

        # Sort by position and deduplicate overlapping matches
        boundaries.sort(key=lambda x: x[0])
        deduped = []
        last_end = -1
        for start, heading, level in boundaries:
            if start > last_end:
                deduped.append((start, heading, level))
                last_end = start + len(heading)

        if not deduped:
            return []

        sections = []
        for i, (start, heading, level) in enumerate(deduped):
            content_start = start + len(heading)
            content_end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
            content = text[content_start:content_end].strip()
            sections.append(Section(
                heading=heading,
                content=content,
                start_pos=start,
                end_pos=content_end,
                level=level,
            ))

        return sections

    def _is_recommendation_text(self, text: str) -> bool:
        """Check if text contains recommendation markers."""
        return any(p.search(text) for p in RECOMMENDATION_PATTERNS)

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Split on sentence-ending punctuation followed by space or newline
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _chunk_section_content(
        self,
        content: str,
        heading: Optional[str],
        start_index: int,
    ) -> list[GuidelineChunkResult]:
        """Chunk the content of a single section.

        Args:
            content: Section text content
            heading: Section heading (prepended to each chunk if preserve_headings)
            start_index: Starting chunk index

        Returns:
            List of GuidelineChunkResult objects
        """
        chunks = []

        # Calculate available space for content (minus heading prefix)
        heading_prefix = f"[{heading}]\n" if heading and self._preserve_headings else ""
        heading_tokens = self._estimate_tokens(heading_prefix)
        max_content_tokens = self._max_chunk_tokens - heading_tokens

        if max_content_tokens < 50:
            # Heading is too long, skip prefix
            heading_prefix = ""
            max_content_tokens = self._max_chunk_tokens

        sentences = self._split_into_sentences(content)
        if not sentences:
            return chunks

        current_chunk_sentences = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            if current_tokens + sentence_tokens > max_content_tokens and current_chunk_sentences:
                # Emit current chunk
                chunk_text = heading_prefix + " ".join(current_chunk_sentences)
                is_rec = self._is_recommendation_text(chunk_text)
                chunks.append(GuidelineChunkResult(
                    chunk_index=start_index + len(chunks),
                    chunk_text=chunk_text,
                    token_count=self._estimate_tokens(chunk_text),
                    section_heading=heading,
                    is_recommendation=is_rec,
                ))

                # Overlap: keep last few sentences
                overlap_tokens = 0
                overlap_sentences = []
                for s in reversed(current_chunk_sentences):
                    s_tokens = self._estimate_tokens(s)
                    if overlap_tokens + s_tokens > self._overlap_tokens:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens

                current_chunk_sentences = overlap_sentences
                current_tokens = overlap_tokens
            elif sentence_tokens > max_content_tokens:
                # Single sentence exceeds chunk size - force split by character
                if current_chunk_sentences:
                    chunk_text = heading_prefix + " ".join(current_chunk_sentences)
                    chunks.append(GuidelineChunkResult(
                        chunk_index=start_index + len(chunks),
                        chunk_text=chunk_text,
                        token_count=self._estimate_tokens(chunk_text),
                        section_heading=heading,
                        is_recommendation=self._is_recommendation_text(chunk_text),
                    ))
                    current_chunk_sentences = []
                    current_tokens = 0

                # Split long sentence
                words = sentence.split()
                partial = []
                partial_tokens = 0
                for word in words:
                    word_tokens = self._estimate_tokens(word + " ")
                    if partial_tokens + word_tokens > max_content_tokens and partial:
                        chunk_text = heading_prefix + " ".join(partial)
                        chunks.append(GuidelineChunkResult(
                            chunk_index=start_index + len(chunks),
                            chunk_text=chunk_text,
                            token_count=self._estimate_tokens(chunk_text),
                            section_heading=heading,
                            is_recommendation=self._is_recommendation_text(chunk_text),
                        ))
                        partial = []
                        partial_tokens = 0
                    partial.append(word)
                    partial_tokens += word_tokens

                if partial:
                    current_chunk_sentences = partial
                    current_tokens = partial_tokens
                continue

            current_chunk_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Emit remaining content
        if current_chunk_sentences:
            chunk_text = heading_prefix + " ".join(current_chunk_sentences)
            chunks.append(GuidelineChunkResult(
                chunk_index=start_index + len(chunks),
                chunk_text=chunk_text,
                token_count=self._estimate_tokens(chunk_text),
                section_heading=heading,
                is_recommendation=self._is_recommendation_text(chunk_text),
            ))

        return chunks

    def chunk_text(self, text: str) -> list[GuidelineChunkResult]:
        """Chunk guideline text using structure-aware splitting.

        First attempts to detect sections via headings. Falls back
        to sentence-based splitting for unstructured text.

        Args:
            text: Full guideline document text

        Returns:
            List of GuidelineChunkResult objects
        """
        if not text or not text.strip():
            return []

        sections = self._detect_sections(text)

        if sections:
            logger.debug(f"Detected {len(sections)} sections in guideline text")
            chunks = []

            # Handle any text before the first section
            if sections[0].start_pos > 0:
                preamble = text[:sections[0].start_pos].strip()
                if preamble and self._estimate_tokens(preamble) > 20:
                    chunks.extend(self._chunk_section_content(
                        preamble, None, 0
                    ))

            # Chunk each section
            for section in sections:
                section_chunks = self._chunk_section_content(
                    section.content,
                    section.heading,
                    len(chunks),
                )
                chunks.extend(section_chunks)

            if chunks:
                # Re-index chunks sequentially
                for i, chunk in enumerate(chunks):
                    chunk.chunk_index = i
                logger.info(
                    f"Structure-aware chunking produced {len(chunks)} chunks "
                    f"from {len(sections)} sections"
                )
                return chunks

        # Fallback: sentence-based chunking (no sections detected)
        logger.debug("No sections detected, falling back to sentence-based chunking")
        return self._chunk_section_content(text, None, 0)
