"""
Search quality configuration for RAG system.

Provides configuration for:
- Adaptive similarity threshold
- Medical query expansion
- BM25 hybrid search
- MMR result diversity
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchQualityConfig:
    """Configuration for RAG search quality improvements.

    Attributes:
        enable_adaptive_threshold: Whether to dynamically adjust similarity threshold
        min_threshold: Minimum similarity threshold
        max_threshold: Maximum similarity threshold
        target_result_count: Target number of quality results

        enable_query_expansion: Whether to expand medical terms
        expand_abbreviations: Whether to expand medical abbreviations
        expand_synonyms: Whether to expand medical synonyms
        max_expansion_terms: Maximum number of expansion terms per query term

        enable_bm25: Whether to use BM25 keyword search
        vector_weight: Weight for vector similarity scores (0-1)
        bm25_weight: Weight for BM25 keyword scores (0-1)
        graph_weight: Weight for knowledge graph scores (0-1)

        enable_mmr: Whether to apply MMR for result diversity
        mmr_lambda: Balance between relevance and diversity (0-1)
                    Higher = more relevance, Lower = more diversity
    """
    # Adaptive threshold settings
    enable_adaptive_threshold: bool = True
    min_threshold: float = 0.2
    max_threshold: float = 0.8
    target_result_count: int = 5

    # Query expansion settings
    enable_query_expansion: bool = True
    expand_abbreviations: bool = True
    expand_synonyms: bool = True
    max_expansion_terms: int = 3

    # BM25 hybrid search settings
    enable_bm25: bool = True
    vector_weight: float = 0.5
    bm25_weight: float = 0.3
    graph_weight: float = 0.2

    # MMR diversity settings
    enable_mmr: bool = True
    mmr_lambda: float = 0.7

    def __post_init__(self):
        """Validate configuration values."""
        # Ensure thresholds are in valid range
        if not 0.0 <= self.min_threshold <= 1.0:
            raise ValueError("min_threshold must be between 0 and 1")
        if not 0.0 <= self.max_threshold <= 1.0:
            raise ValueError("max_threshold must be between 0 and 1")
        if self.min_threshold > self.max_threshold:
            raise ValueError("min_threshold must be <= max_threshold")

        # Ensure weights sum to approximately 1
        total_weight = self.vector_weight + self.bm25_weight + self.graph_weight
        if abs(total_weight - 1.0) > 0.01:
            # Normalize weights
            self.vector_weight /= total_weight
            self.bm25_weight /= total_weight
            self.graph_weight /= total_weight

        # Ensure mmr_lambda is in valid range
        if not 0.0 <= self.mmr_lambda <= 1.0:
            raise ValueError("mmr_lambda must be between 0 and 1")

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SearchQualityConfig":
        """Create configuration from dictionary.

        Args:
            config_dict: Dictionary with configuration values

        Returns:
            SearchQualityConfig instance
        """
        # Filter out unknown keys
        valid_keys = {
            'enable_adaptive_threshold', 'min_threshold', 'max_threshold',
            'target_result_count', 'enable_query_expansion', 'expand_abbreviations',
            'expand_synonyms', 'max_expansion_terms', 'enable_bm25',
            'vector_weight', 'bm25_weight', 'graph_weight', 'enable_mmr',
            'mmr_lambda'
        }
        filtered = {k: v for k, v in config_dict.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of config
        """
        return {
            'enable_adaptive_threshold': self.enable_adaptive_threshold,
            'min_threshold': self.min_threshold,
            'max_threshold': self.max_threshold,
            'target_result_count': self.target_result_count,
            'enable_query_expansion': self.enable_query_expansion,
            'expand_abbreviations': self.expand_abbreviations,
            'expand_synonyms': self.expand_synonyms,
            'max_expansion_terms': self.max_expansion_terms,
            'enable_bm25': self.enable_bm25,
            'vector_weight': self.vector_weight,
            'bm25_weight': self.bm25_weight,
            'graph_weight': self.graph_weight,
            'enable_mmr': self.enable_mmr,
            'mmr_lambda': self.mmr_lambda,
        }


# Default configuration singleton
_default_config: Optional[SearchQualityConfig] = None


def get_search_quality_config() -> SearchQualityConfig:
    """Get the search quality configuration.

    Loads from settings if available, otherwise uses defaults.

    Returns:
        SearchQualityConfig instance
    """
    global _default_config

    if _default_config is None:
        try:
            from settings.settings import SETTINGS
            config_dict = SETTINGS.get("rag_search_quality", {})
            _default_config = SearchQualityConfig.from_dict(config_dict)
        except Exception:
            _default_config = SearchQualityConfig()

    return _default_config


def reset_search_quality_config():
    """Reset the configuration singleton."""
    global _default_config
    _default_config = None
