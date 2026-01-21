"""
Adaptive similarity threshold for RAG system.

Dynamically adjusts the similarity threshold based on:
- Score distribution of initial results
- Query characteristics
- Target result count
"""

import logging
import statistics
from typing import Optional

from rag.search_config import SearchQualityConfig, get_search_quality_config

logger = logging.getLogger(__name__)


class AdaptiveThresholdCalculator:
    """Calculates adaptive similarity thresholds."""

    def __init__(self, config: Optional[SearchQualityConfig] = None):
        """Initialize the adaptive threshold calculator.

        Args:
            config: Search quality configuration
        """
        self.config = config or get_search_quality_config()

    def calculate_threshold(
        self,
        scores: list[float],
        query_length: int,
        initial_threshold: float = 0.5,
    ) -> float:
        """Calculate an adaptive threshold based on result scores.

        The algorithm considers:
        1. Score variance - tight cluster of scores suggests higher quality
        2. Score distribution - gap between scores indicates natural cutoff
        3. Query specificity - longer queries may need higher thresholds
        4. Target result count - ensure we return enough results

        Args:
            scores: List of similarity scores from initial search
            query_length: Number of words in the query
            initial_threshold: Starting threshold value

        Returns:
            Adjusted similarity threshold
        """
        if not self.config.enable_adaptive_threshold:
            return initial_threshold

        if not scores:
            return self.config.min_threshold

        # Sort scores in descending order
        sorted_scores = sorted(scores, reverse=True)

        # Start with the configured threshold
        threshold = initial_threshold

        # Adjust based on score distribution
        threshold = self._adjust_for_distribution(sorted_scores, threshold)

        # Adjust based on query specificity
        threshold = self._adjust_for_query_length(query_length, threshold)

        # Adjust based on target result count
        threshold = self._adjust_for_result_count(sorted_scores, threshold)

        # Ensure threshold is within bounds
        threshold = max(self.config.min_threshold, threshold)
        threshold = min(self.config.max_threshold, threshold)

        logger.debug(
            f"Adaptive threshold: {initial_threshold:.3f} -> {threshold:.3f} "
            f"(scores: {len(scores)}, query_len: {query_length})"
        )

        return threshold

    def _adjust_for_distribution(
        self,
        sorted_scores: list[float],
        threshold: float
    ) -> float:
        """Adjust threshold based on score distribution.

        Args:
            sorted_scores: Scores sorted in descending order
            threshold: Current threshold

        Returns:
            Adjusted threshold
        """
        if len(sorted_scores) < 2:
            return threshold

        # Calculate statistics
        mean_score = statistics.mean(sorted_scores)
        try:
            std_dev = statistics.stdev(sorted_scores)
        except statistics.StatisticsError:
            std_dev = 0

        # Find natural gaps in scores
        max_gap = 0
        gap_threshold = threshold

        for i in range(len(sorted_scores) - 1):
            gap = sorted_scores[i] - sorted_scores[i + 1]
            if gap > max_gap and gap > 0.1:  # Significant gap
                max_gap = gap
                gap_threshold = sorted_scores[i + 1]

        # If scores are tightly clustered (low variance), raise threshold
        if std_dev < 0.1 and mean_score > 0.5:
            threshold = max(threshold, mean_score - std_dev)

        # If there's a natural gap, use it as cutoff
        if max_gap > 0.15:
            threshold = max(threshold, gap_threshold)

        # If top scores are very high, be more selective
        if sorted_scores[0] > 0.8:
            threshold = max(threshold, sorted_scores[0] - 0.2)

        return threshold

    def _adjust_for_query_length(
        self,
        query_length: int,
        threshold: float
    ) -> float:
        """Adjust threshold based on query specificity.

        Longer, more specific queries tend to have better matching results,
        so we can afford a higher threshold.

        Args:
            query_length: Number of words in query
            threshold: Current threshold

        Returns:
            Adjusted threshold
        """
        # Very short queries (1-2 words) - lower threshold
        if query_length <= 2:
            return threshold * 0.85

        # Medium queries (3-5 words) - no adjustment
        if query_length <= 5:
            return threshold

        # Longer queries (6+ words) - slightly higher threshold
        adjustment = min(0.1, (query_length - 5) * 0.02)
        return threshold + adjustment

    def _adjust_for_result_count(
        self,
        sorted_scores: list[float],
        threshold: float
    ) -> float:
        """Adjust threshold to meet target result count.

        Args:
            sorted_scores: Scores sorted in descending order
            threshold: Current threshold

        Returns:
            Adjusted threshold
        """
        target = self.config.target_result_count

        # Count how many results would pass current threshold
        passing_count = sum(1 for s in sorted_scores if s >= threshold)

        # If too few results, lower threshold
        if passing_count < target and sorted_scores:
            # Find threshold that gives us target results
            if len(sorted_scores) >= target:
                threshold = min(threshold, sorted_scores[target - 1])
            else:
                # Not enough results, use minimum threshold
                threshold = self.config.min_threshold

        # If way too many results (>3x target), raise threshold
        if passing_count > target * 3 and len(sorted_scores) >= target:
            # Use threshold that gives us target results
            threshold = max(threshold, sorted_scores[target - 1])

        return threshold

    def analyze_scores(self, scores: list[float]) -> dict:
        """Analyze score distribution for debugging.

        Args:
            scores: List of similarity scores

        Returns:
            Dictionary with analysis results
        """
        if not scores:
            return {"empty": True}

        sorted_scores = sorted(scores, reverse=True)

        analysis = {
            "count": len(scores),
            "min": min(scores),
            "max": max(scores),
            "mean": statistics.mean(scores),
            "median": statistics.median(scores),
        }

        if len(scores) >= 2:
            analysis["std_dev"] = statistics.stdev(scores)

            # Find largest gaps
            gaps = []
            for i in range(len(sorted_scores) - 1):
                gap = sorted_scores[i] - sorted_scores[i + 1]
                gaps.append((i, sorted_scores[i], sorted_scores[i + 1], gap))

            gaps.sort(key=lambda x: x[3], reverse=True)
            analysis["largest_gaps"] = gaps[:3]

        return analysis


# Singleton instance
_calculator: Optional[AdaptiveThresholdCalculator] = None


def get_adaptive_threshold_calculator() -> AdaptiveThresholdCalculator:
    """Get the global adaptive threshold calculator instance.

    Returns:
        AdaptiveThresholdCalculator instance
    """
    global _calculator
    if _calculator is None:
        _calculator = AdaptiveThresholdCalculator()
    return _calculator


def reset_adaptive_threshold_calculator():
    """Reset the global calculator instance."""
    global _calculator
    _calculator = None


def calculate_adaptive_threshold(
    scores: list[float],
    query_length: int,
    initial_threshold: float = 0.5,
) -> float:
    """Convenience function to calculate adaptive threshold.

    Args:
        scores: List of similarity scores
        query_length: Number of words in query
        initial_threshold: Starting threshold

    Returns:
        Adjusted threshold
    """
    calculator = get_adaptive_threshold_calculator()
    return calculator.calculate_threshold(scores, query_length, initial_threshold)
