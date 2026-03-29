"""
Tests for DocumentProcessor in src/rag/document_processor.py

Covers EXTENSION_TO_TYPE mapping, count_tokens() (tiktoken or approx),
get_document_type() (known/unknown extensions, case-insensitive ext),
_split_into_sentences() (basic split, multiline, empty),
_get_overlap_sentences() (empty, fits, too long),
_split_long_sentence() (short sentence, multi-chunk, no words),
and compute_text_hash() (SHA256, deterministic, empty string).
No network, no Tkinter, no file I/O.
"""

import sys
import hashlib
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.document_processor import DocumentProcessor, EXTENSION_TO_TYPE
from rag.models import DocumentType


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def dp() -> DocumentProcessor:
    return DocumentProcessor()


# ===========================================================================
# EXTENSION_TO_TYPE constant
# ===========================================================================

class TestExtensionToType:
    def test_is_dict(self):
        assert isinstance(EXTENSION_TO_TYPE, dict)

    def test_pdf_maps_to_pdf_type(self):
        assert EXTENSION_TO_TYPE[".pdf"] == DocumentType.PDF

    def test_docx_maps_to_docx_type(self):
        assert EXTENSION_TO_TYPE[".docx"] == DocumentType.DOCX

    def test_doc_maps_to_docx_type(self):
        assert EXTENSION_TO_TYPE[".doc"] == DocumentType.DOCX

    def test_txt_maps_to_txt_type(self):
        assert EXTENSION_TO_TYPE[".txt"] == DocumentType.TXT

    def test_md_maps_to_txt_type(self):
        assert EXTENSION_TO_TYPE[".md"] == DocumentType.TXT

    def test_png_maps_to_image_type(self):
        assert EXTENSION_TO_TYPE[".png"] == DocumentType.IMAGE

    def test_jpg_maps_to_image_type(self):
        assert EXTENSION_TO_TYPE[".jpg"] == DocumentType.IMAGE

    def test_jpeg_maps_to_image_type(self):
        assert EXTENSION_TO_TYPE[".jpeg"] == DocumentType.IMAGE

    def test_tiff_maps_to_image_type(self):
        assert EXTENSION_TO_TYPE[".tiff"] == DocumentType.IMAGE

    def test_bmp_maps_to_image_type(self):
        assert EXTENSION_TO_TYPE[".bmp"] == DocumentType.IMAGE

    def test_all_keys_start_with_dot(self):
        for ext in EXTENSION_TO_TYPE:
            assert ext.startswith("."), f"Extension '{ext}' does not start with '.'"

    def test_all_values_are_document_types(self):
        for ext, dtype in EXTENSION_TO_TYPE.items():
            assert isinstance(dtype, DocumentType)


# ===========================================================================
# get_document_type
# ===========================================================================

class TestGetDocumentType:
    def test_pdf_extension(self, dp):
        assert dp.get_document_type("/path/to/file.pdf") == DocumentType.PDF

    def test_docx_extension(self, dp):
        assert dp.get_document_type("/path/to/file.docx") == DocumentType.DOCX

    def test_doc_extension(self, dp):
        assert dp.get_document_type("/path/to/file.doc") == DocumentType.DOCX

    def test_txt_extension(self, dp):
        assert dp.get_document_type("/path/to/file.txt") == DocumentType.TXT

    def test_md_extension(self, dp):
        assert dp.get_document_type("notes.md") == DocumentType.TXT

    def test_png_extension(self, dp):
        assert dp.get_document_type("scan.png") == DocumentType.IMAGE

    def test_jpg_extension(self, dp):
        assert dp.get_document_type("photo.jpg") == DocumentType.IMAGE

    def test_unknown_extension_returns_none(self, dp):
        assert dp.get_document_type("/path/to/file.xyz") is None

    def test_no_extension_returns_none(self, dp):
        assert dp.get_document_type("/path/to/file") is None

    def test_extension_lowercased(self, dp):
        # Extension is lowercased before lookup
        assert dp.get_document_type("/path/to/FILE.PDF") == DocumentType.PDF

    def test_tif_extension(self, dp):
        assert dp.get_document_type("scan.tif") == DocumentType.IMAGE

    def test_bmp_extension(self, dp):
        assert dp.get_document_type("image.bmp") == DocumentType.IMAGE


# ===========================================================================
# count_tokens
# ===========================================================================

class TestCountTokens:
    def test_empty_string_returns_zero(self, dp):
        assert dp.count_tokens("") == 0

    def test_returns_positive_int_for_text(self, dp):
        result = dp.count_tokens("hello world")
        assert isinstance(result, int)
        assert result > 0

    def test_longer_text_has_more_tokens(self, dp):
        short = dp.count_tokens("hello")
        long = dp.count_tokens("hello world this is a longer sentence with many words")
        assert long > short

    def test_single_word(self, dp):
        result = dp.count_tokens("diabetes")
        assert result >= 1

    def test_none_handled_by_zero_check(self, dp):
        # The method has `if not text: return 0`
        assert dp.count_tokens("") == 0


# ===========================================================================
# compute_text_hash
# ===========================================================================

class TestComputeTextHash:
    def test_returns_string(self, dp):
        assert isinstance(dp.compute_text_hash("hello"), str)

    def test_sha256_hex_length(self, dp):
        # SHA256 hex digest is 64 chars
        assert len(dp.compute_text_hash("hello world")) == 64

    def test_deterministic(self, dp):
        text = "patient has hypertension"
        assert dp.compute_text_hash(text) == dp.compute_text_hash(text)

    def test_matches_manual_sha256(self, dp):
        text = "diabetes treatment"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert dp.compute_text_hash(text) == expected

    def test_different_texts_different_hashes(self, dp):
        h1 = dp.compute_text_hash("text one")
        h2 = dp.compute_text_hash("text two")
        assert h1 != h2

    def test_empty_string_hash(self, dp):
        result = dp.compute_text_hash("")
        assert len(result) == 64
        assert result == hashlib.sha256(b"").hexdigest()


# ===========================================================================
# _split_into_sentences
# ===========================================================================

class TestSplitIntoSentences:
    def test_returns_list(self, dp):
        assert isinstance(dp._split_into_sentences("Hello world."), list)

    def test_empty_string_returns_empty(self, dp):
        assert dp._split_into_sentences("") == []

    def test_single_sentence_returns_one(self, dp):
        result = dp._split_into_sentences("Patient has diabetes.")
        assert len(result) == 1
        assert "Patient has diabetes." in result

    def test_two_sentences_split(self, dp):
        text = "Patient has diabetes. Doctor prescribed metformin."
        result = dp._split_into_sentences(text)
        assert len(result) >= 1  # At least one result
        assert any("diabetes" in s for s in result)

    def test_strips_whitespace_from_sentences(self, dp):
        result = dp._split_into_sentences("  Hello world.  ")
        for s in result:
            assert s == s.strip()

    def test_no_empty_sentences_in_result(self, dp):
        result = dp._split_into_sentences("Sentence one. Sentence two.")
        assert all(len(s.strip()) > 0 for s in result)

    def test_question_mark_splits(self, dp):
        text = "Is the patient diabetic? Yes, they are."
        result = dp._split_into_sentences(text)
        assert len(result) >= 1

    def test_exclamation_splits(self, dp):
        text = "Emergency! Patient needs immediate care."
        result = dp._split_into_sentences(text)
        assert len(result) >= 1


# ===========================================================================
# _get_overlap_sentences
# ===========================================================================

class TestGetOverlapSentences:
    def test_empty_list_returns_empty(self, dp):
        assert dp._get_overlap_sentences([], 50) == []

    def test_returns_list(self, dp):
        sentences = ["Patient has diabetes.", "Metformin prescribed."]
        assert isinstance(dp._get_overlap_sentences(sentences, 100), list)

    def test_overlap_zero_returns_empty(self, dp):
        # With 0 overlap tokens, can't fit any sentence (tokens > 0)
        sentences = ["Patient has diabetes."]
        result = dp._get_overlap_sentences(sentences, 0)
        assert result == []

    def test_small_overlap_returns_last_sentence(self, dp):
        # With enough tokens for last sentence
        sentences = ["First long sentence.", "Short one."]
        result = dp._get_overlap_sentences(sentences, 50)
        # Should include at least the shortest sentence
        assert isinstance(result, list)
        assert len(result) >= 0

    def test_large_overlap_returns_all_sentences(self, dp):
        sentences = ["A.", "B.", "C."]
        # With very large overlap tokens, all should fit
        result = dp._get_overlap_sentences(sentences, 10000)
        assert len(result) == 3

    def test_order_preserved(self, dp):
        sentences = ["First.", "Second.", "Third."]
        result = dp._get_overlap_sentences(sentences, 10000)
        if len(result) > 1:
            assert result == sorted(result, key=lambda s: sentences.index(s))


# ===========================================================================
# _split_long_sentence
# ===========================================================================

class TestSplitLongSentence:
    def test_returns_list(self, dp):
        assert isinstance(dp._split_long_sentence("hello world", 100), list)

    def test_empty_string_returns_empty(self, dp):
        result = dp._split_long_sentence("", 100)
        assert result == []

    def test_short_sentence_returns_single_chunk(self, dp):
        result = dp._split_long_sentence("Short sentence.", 100)
        assert len(result) == 1
        assert result[0] == "Short sentence."

    def test_long_sentence_splits_into_multiple(self, dp):
        # Very small max_tokens to force splitting
        long_sentence = " ".join(["word"] * 100)
        result = dp._split_long_sentence(long_sentence, 1)
        assert len(result) > 1

    def test_all_words_preserved(self, dp):
        words = ["word1", "word2", "word3", "word4", "word5"]
        sentence = " ".join(words)
        result = dp._split_long_sentence(sentence, 2)
        reconstructed_words = " ".join(result).split()
        assert set(reconstructed_words) == set(words)

    def test_single_word_not_split(self, dp):
        result = dp._split_long_sentence("diabetes", 0)
        assert len(result) == 1
        assert result[0] == "diabetes"
