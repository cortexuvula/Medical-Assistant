"""
Emotion Processor Module

Processes emotion data from Modulate.ai voice emotion analysis and formats it for:
1. SOAP note integration (concise clinical summary)
2. Analysis panel display (detailed per-segment breakdown)
3. Extracting dominant emotions above a confidence threshold
"""

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Emotions considered clinically relevant for medical documentation
CLINICAL_EMOTIONS = {
    "anxiety",
    "sadness",
    "anger",
    "fear",
    "distress",
    "frustration",
    "confusion",
    "joy",
    "calm",
    "surprise",
}

# Map raw emotion names to clinical descriptors
CLINICAL_DESCRIPTORS = {
    "anxiety": "anxious",
    "sadness": "sad",
    "anger": "agitated",
    "fear": "fearful",
    "distress": "distressed",
    "frustration": "frustrated",
    "confusion": "confused",
    "joy": "positive affect",
    "calm": "calm",
    "surprise": "surprised",
    "neutral": "neutral affect",
}


def _format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS display string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def _validate_emotion_data(emotion_data: dict) -> bool:
    """Check that emotion_data has the expected structure and content."""
    if not emotion_data or not isinstance(emotion_data, dict):
        return False
    segments = emotion_data.get("segments")
    if not segments or not isinstance(segments, list):
        return False
    return True


def _get_top_emotions(emotions: dict, n: int = 3, threshold: float = 0.1) -> list:
    """Return the top N emotions above threshold, sorted by confidence descending."""
    if not emotions or not isinstance(emotions, dict):
        return []
    filtered = [
        (name, score)
        for name, score in emotions.items()
        if isinstance(score, (int, float)) and score >= threshold and name != "neutral"
    ]
    filtered.sort(key=lambda x: x[1], reverse=True)
    return filtered[:n]


def format_emotion_for_soap(emotion_data: dict) -> str:
    """Convert raw emotion JSON into a concise clinical summary for the SOAP prompt.

    Produces a brief summary suitable for embedding in a SOAP note, highlighting
    clinically significant emotional states observed during the encounter.

    Args:
        emotion_data: Dict with 'segments' and optional 'overall' keys from
                      Modulate.ai voice emotion analysis.

    Returns:
        A formatted string summarizing detected emotions, or an empty string
        if no meaningful emotion data is available.
    """
    if not _validate_emotion_data(emotion_data):
        logger.debug("No valid emotion data provided for SOAP formatting")
        return ""

    segments = emotion_data.get("segments", [])
    overall = emotion_data.get("overall", {})

    findings = []

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        emotions = segment.get("emotions", {})
        text = segment.get("text", "").strip()
        top_emotions = _get_top_emotions(emotions, n=2, threshold=0.3)

        if not top_emotions:
            continue

        for emotion_name, confidence in top_emotions:
            if emotion_name in CLINICAL_EMOTIONS:
                context = ""
                if text:
                    # Truncate long text for the summary
                    snippet = text[:80] + "..." if len(text) > 80 else text
                    context = f' during "{snippet}"'
                findings.append(
                    f"- Patient exhibited elevated {emotion_name} "
                    f"(confidence: {confidence:.2f}){context}"
                )

    if not findings:
        logger.debug("No clinically significant emotions detected above threshold")
        return ""

    # Build overall affect line
    affect_parts = []
    if overall and isinstance(overall, dict):
        dominant = overall.get("dominant_emotion", "")
        avg_emotions = overall.get("average_emotions", {})

        if dominant and dominant in CLINICAL_DESCRIPTORS:
            affect_parts.append(CLINICAL_DESCRIPTORS[dominant])

        # Add any other elevated average emotions
        if isinstance(avg_emotions, dict):
            for emotion_name, avg_score in sorted(
                avg_emotions.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True
            ):
                if (
                    isinstance(avg_score, (int, float))
                    and avg_score >= 0.3
                    and emotion_name != dominant
                    and emotion_name != "neutral"
                    and emotion_name in CLINICAL_DESCRIPTORS
                ):
                    descriptor = CLINICAL_DESCRIPTORS[emotion_name]
                    if descriptor not in affect_parts:
                        affect_parts.append(f"mildly {descriptor}")
                    if len(affect_parts) >= 3:
                        break

    lines = ["Voice Emotion Analysis:"]
    # Deduplicate and limit findings
    seen = set()
    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            lines.append(finding)
        if len(seen) >= 5:
            break

    if affect_parts:
        lines.append(f"- Overall affect: {', '.join(affect_parts)}")

    return "\n".join(lines)


def format_emotion_for_panel(emotion_data: dict) -> str:
    """Detailed formatted display for the analysis panel with per-segment breakdown.

    Produces a comprehensive report showing timeline of emotions, segment-by-segment
    analysis, overall emotional summary, and clinical relevance notes.

    Args:
        emotion_data: Dict with 'segments' and optional 'overall' keys from
                      Modulate.ai voice emotion analysis.

    Returns:
        A formatted multi-section string for display, or a message indicating
        no data is available.
    """
    if not _validate_emotion_data(emotion_data):
        logger.debug("No valid emotion data provided for panel formatting")
        return "No emotion analysis data available."

    segments = emotion_data.get("segments", [])
    overall = emotion_data.get("overall", {})

    lines = []

    # Header
    lines.append("=" * 50)
    lines.append("VOICE EMOTION ANALYSIS")
    lines.append("=" * 50)
    lines.append("")

    # Segment-by-segment breakdown
    lines.append("SEGMENT ANALYSIS")
    lines.append("-" * 30)

    has_segment_data = False
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue

        start = segment.get("start_time", 0.0)
        end = segment.get("end_time", 0.0)
        speaker = segment.get("speaker", "unknown")
        text = segment.get("text", "").strip()
        emotions = segment.get("emotions", {})

        if not isinstance(start, (int, float)):
            start = 0.0
        if not isinstance(end, (int, float)):
            end = 0.0

        top_emotions = _get_top_emotions(emotions, n=4, threshold=0.1)
        if not top_emotions and not text:
            continue

        has_segment_data = True
        timestamp = f"[{_format_timestamp(start)} - {_format_timestamp(end)}]"
        lines.append(f"\nSegment {i + 1} {timestamp} ({speaker})")

        if text:
            display_text = text[:120] + "..." if len(text) > 120 else text
            lines.append(f'  Text: "{display_text}"')

        if top_emotions:
            lines.append("  Emotions:")
            for emotion_name, confidence in top_emotions:
                bar_len = int(confidence * 20)
                bar = "#" * bar_len + "." * (20 - bar_len)
                lines.append(f"    {emotion_name:<15} [{bar}] {confidence:.2f}")
        else:
            lines.append("  Emotions: (none above threshold)")

    if not has_segment_data:
        lines.append("  No segment data available.")

    lines.append("")

    # Overall summary
    lines.append("OVERALL SUMMARY")
    lines.append("-" * 30)

    if overall and isinstance(overall, dict):
        dominant = overall.get("dominant_emotion", "unknown")
        variability = overall.get("emotion_variability", None)
        avg_emotions = overall.get("average_emotions", {})

        lines.append(f"  Dominant emotion: {dominant}")

        if isinstance(variability, (int, float)):
            variability_label = "low"
            if variability > 0.6:
                variability_label = "high"
            elif variability > 0.3:
                variability_label = "moderate"
            lines.append(
                f"  Emotional variability: {variability:.2f} ({variability_label})"
            )

        if avg_emotions and isinstance(avg_emotions, dict):
            lines.append("  Average emotions across session:")
            sorted_avg = sorted(
                [
                    (k, v)
                    for k, v in avg_emotions.items()
                    if isinstance(v, (int, float))
                ],
                key=lambda x: x[1],
                reverse=True,
            )
            for emotion_name, avg_score in sorted_avg[:6]:
                bar_len = int(avg_score * 20)
                bar = "#" * bar_len + "." * (20 - bar_len)
                lines.append(f"    {emotion_name:<15} [{bar}] {avg_score:.2f}")
    else:
        lines.append("  No overall summary available.")

    lines.append("")

    # Clinical relevance notes
    lines.append("CLINICAL RELEVANCE")
    lines.append("-" * 30)

    clinical_notes = _generate_clinical_notes(segments, overall)
    if clinical_notes:
        for note in clinical_notes:
            lines.append(f"  * {note}")
    else:
        lines.append("  No clinically significant patterns detected.")

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


def _generate_clinical_notes(segments: list, overall: dict) -> list:
    """Generate clinical relevance notes from emotion data."""
    notes = []

    if not segments:
        return notes

    # Check for sustained anxiety or fear
    anxiety_segments = 0
    fear_segments = 0
    sadness_segments = 0
    total_segments = 0

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        emotions = segment.get("emotions", {})
        if not isinstance(emotions, dict):
            continue
        total_segments += 1
        if isinstance(emotions.get("anxiety"), (int, float)) and emotions["anxiety"] >= 0.4:
            anxiety_segments += 1
        if isinstance(emotions.get("fear"), (int, float)) and emotions["fear"] >= 0.4:
            fear_segments += 1
        if isinstance(emotions.get("sadness"), (int, float)) and emotions["sadness"] >= 0.4:
            sadness_segments += 1

    if total_segments > 0:
        if anxiety_segments / total_segments >= 0.5:
            notes.append(
                "Sustained anxiety detected across majority of encounter segments. "
                "Consider screening for anxiety disorder."
            )
        if fear_segments / total_segments >= 0.3:
            notes.append(
                "Elevated fear detected in multiple segments. "
                "Patient may benefit from additional reassurance or counseling."
            )
        if sadness_segments / total_segments >= 0.5:
            notes.append(
                "Persistent sadness observed throughout encounter. "
                "Consider screening for depression (PHQ-9)."
            )

    # Check emotional variability
    if overall and isinstance(overall, dict):
        variability = overall.get("emotion_variability")
        if isinstance(variability, (int, float)) and variability > 0.6:
            notes.append(
                "High emotional variability noted, suggesting significant emotional "
                "distress or lability during the encounter."
            )

    return notes


def get_dominant_emotions(
    emotion_data: dict, threshold: float = 0.3
) -> list:
    """Extract clinically significant emotions above threshold.

    Scans all segments for emotions exceeding the given confidence threshold,
    returning them sorted by confidence (highest first).

    Args:
        emotion_data: Dict with 'segments' key from Modulate.ai voice emotion
                      analysis.
        threshold: Minimum confidence score to include (default 0.3).

    Returns:
        List of dicts, each with keys: emotion, confidence, segment_index,
        timestamp. Returns empty list if no emotions meet the threshold.
    """
    if not _validate_emotion_data(emotion_data):
        logger.debug("No valid emotion data for dominant emotion extraction")
        return []

    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
        logger.warning(f"Invalid threshold value: {threshold}, using default 0.3")
        threshold = 0.3

    segments = emotion_data.get("segments", [])
    results = []

    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue

        emotions = segment.get("emotions", {})
        start_time = segment.get("start_time", 0.0)

        if not isinstance(emotions, dict):
            continue
        if not isinstance(start_time, (int, float)):
            start_time = 0.0

        for emotion_name, confidence in emotions.items():
            if (
                isinstance(confidence, (int, float))
                and confidence >= threshold
                and emotion_name != "neutral"
            ):
                results.append(
                    {
                        "emotion": emotion_name,
                        "confidence": round(confidence, 4),
                        "segment_index": i,
                        "timestamp": round(start_time, 2),
                    }
                )

    results.sort(key=lambda x: x["confidence"], reverse=True)

    logger.debug(f"Found {len(results)} dominant emotions above threshold {threshold:.2f}")
    return results
