"""
Emotion Processor Module

Processes emotion data from Modulate.ai voice emotion analysis and formats it for:
1. SOAP note integration (concise clinical summary)
2. Analysis panel display (detailed per-segment breakdown)
3. Extracting dominant emotions above a confidence threshold

Supports both v1 (legacy continuous-score format) and v2 (categorical, per-speaker) data.
"""

from utils.structured_logging import get_logger
from utils.constants import STT_MODULATE

logger = get_logger(__name__)

# Emotions considered clinically relevant for medical documentation
CLINICAL_EMOTIONS = {
    "anxiety", "sadness", "anger", "fear", "distress", "frustration",
    "confusion", "joy", "calm", "surprise", "stress", "concern",
    "disgust", "disappointment", "hope", "fatigue", "boredom",
    "shame", "excitement", "amusement", "pride", "affection",
    "interest", "contempt", "relief", "confidence",
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
    "stress": "stressed",
    "concern": "concerned",
    "disgust": "disgusted",
    "disappointment": "disappointed",
    "hope": "hopeful",
    "fatigue": "fatigued",
    "boredom": "bored",
    "shame": "ashamed",
    "excitement": "excited",
    "amusement": "amused",
    "pride": "proud",
    "affection": "affectionate",
    "interest": "interested",
    "contempt": "contemptuous",
    "relief": "relieved",
    "confidence": "confident",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS display string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def _is_v2(emotion_data: dict) -> bool:
    """Check whether emotion_data uses the v2 categorical schema."""
    return isinstance(emotion_data, dict) and emotion_data.get("version") == 2


def _validate_emotion_data(emotion_data: dict) -> bool:
    """Check that emotion_data has the expected structure and content."""
    if not emotion_data or not isinstance(emotion_data, dict):
        return False
    segments = emotion_data.get("segments")
    if not segments or not isinstance(segments, list):
        return False
    return True


# ---------------------------------------------------------------------------
# V1 helpers (legacy — used for saved recordings without version field)
# ---------------------------------------------------------------------------

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


def _format_soap_v1(emotion_data: dict) -> str:
    """V1 SOAP formatting — legacy continuous-score format."""
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
                    snippet = text[:80] + "..." if len(text) > 80 else text
                    context = f' during "{snippet}"'
                findings.append(
                    f"- Patient exhibited elevated {emotion_name} "
                    f"(confidence: {confidence:.2f}){context}"
                )

    if not findings:
        return ""

    affect_parts = []
    if overall and isinstance(overall, dict):
        dominant = overall.get("dominant_emotion", "")
        avg_emotions = overall.get("average_emotions", {})

        if dominant and dominant in CLINICAL_DESCRIPTORS:
            affect_parts.append(CLINICAL_DESCRIPTORS[dominant])

        if isinstance(avg_emotions, dict):
            for emotion_name, avg_score in sorted(
                avg_emotions.items(),
                key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0,
                reverse=True,
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


def _format_panel_v1(emotion_data: dict) -> str:
    """V1 panel formatting — legacy segment dump."""
    segments = emotion_data.get("segments", [])
    overall = emotion_data.get("overall", {})

    lines = []

    lines.append("=" * 50)
    lines.append("VOICE EMOTION ANALYSIS")
    lines.append("=" * 50)
    lines.append("")

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


# ---------------------------------------------------------------------------
# V2 formatting (per-speaker, 3-tier display, observational flags)
# ---------------------------------------------------------------------------

def _get_role_label(profile) -> str:
    """Get a display label for a speaker's role."""
    role_labels = {
        "clinician": "Physician",
        "patient": "Patient",
        "caregiver": "Caregiver",
        "unknown": "Speaker",
    }
    return role_labels.get(profile.role.value, "Speaker")


def _format_soap_v2(emotion_data: dict) -> str:
    """V2 SOAP formatting — per-speaker observational summary (opt-in)."""
    from settings.settings_manager import settings_manager

    if not settings_manager.get(STT_MODULATE, {}).get("emotion_in_soap", False):
        return ""

    from ai.emotion_speaker_analyzer import SpeakerEmotionAnalyzer

    analyzer = SpeakerEmotionAnalyzer()
    analysis = analyzer.analyze(emotion_data)

    if not analysis.flags:
        return ""

    # Build brief observational note from flags (max 3)
    parts = []
    for flag in analysis.flags[:3]:
        role_label = _get_role_label_from_flag(flag, analysis)
        parts.append(f"{role_label}: {flag.message}")

    if not parts:
        return ""

    disclaimer = analysis.disclaimer
    note = "Voice emotion observation: " + ". ".join(parts) + "."
    return f"{note}\n[{disclaimer}]"


def _get_role_label_from_flag(flag, analysis) -> str:
    """Get role label for a clinical flag."""
    role_labels = {
        "clinician": "Physician",
        "patient": "Patient",
        "caregiver": "Caregiver",
        "unknown": "Speaker",
    }
    return role_labels.get(flag.speaker_role.value, "Speaker")


def _format_panel_v2(emotion_data: dict) -> str:
    """V2 panel formatting — 3-tier per-speaker display."""
    from ai.emotion_speaker_analyzer import SpeakerEmotionAnalyzer

    analyzer = SpeakerEmotionAnalyzer()
    analysis = analyzer.analyze(emotion_data)

    lines = []

    # ── Tier 1: Headline ──
    lines.append("VOICE EMOTION ANALYSIS")
    lines.append("\u2501" * 50)
    lines.append("")

    for profile in analysis.speakers:
        role_label = _get_role_label(profile)
        speaker_label = f"{role_label} ({profile.speaker_id})"

        # Find clusters for this speaker
        speaker_clusters = [c for c in analysis.clusters if c.speaker_id == profile.speaker_id]

        if speaker_clusters:
            # Summarize main cluster in headline
            main_cluster = speaker_clusters[0]
            time_range = (f"{_format_timestamp(main_cluster.start_time)}-"
                          f"{_format_timestamp(main_cluster.end_time)}")
            topic = ""
            if main_cluster.topic_hint:
                topic = f"\n  around {main_cluster.topic_hint}"
            lines.append(
                f"{speaker_label}: sustained {main_cluster.emotion_label} "
                f"[{time_range}]{topic}"
            )
        elif not profile.deviations:
            lines.append(
                f"{speaker_label}: baseline {profile.baseline_emotion} "
                f"throughout ({profile.utterance_count} utterances)"
            )
        else:
            dev_count = len(profile.deviations)
            lines.append(
                f"{speaker_label}: baseline {profile.baseline_emotion} "
                f"({profile.utterance_count} utterances, "
                f"{dev_count} deviation{'s' if dev_count != 1 else ''})"
            )

    lines.append("")

    # Disclaimer
    lines.append(f"\u26a0 {analysis.disclaimer}")

    # ── Tier 2: Speaker Detail ──
    lines.append("")
    lines.append("SPEAKER DETAIL")
    lines.append("\u2500" * 50)

    for profile in analysis.speakers:
        role_label = _get_role_label(profile)
        lines.append("")
        lines.append(
            f"{role_label.upper()} ({profile.speaker_id}) "
            f"\u2014 {profile.utterance_count} utterances"
        )
        baseline_count = profile.emotion_counts.get(profile.baseline_emotion, 0)
        lines.append(
            f"  Baseline: {profile.baseline_emotion} "
            f"({baseline_count} of {profile.utterance_count})"
        )

        if profile.deviations:
            lines.append("")
            lines.append("  Notable shifts:")

            # Show deviations sorted by time
            sorted_devs = sorted(profile.deviations, key=lambda d: d.start_time)
            for dev in sorted_devs:
                ts = _format_timestamp(dev.start_time)
                snippet = f' \u2014 "{dev.text_snippet}"' if dev.text_snippet else ""
                lines.append(f"   [{ts}] {dev.emotion_label:<10}{snippet}")

            # Check for return to baseline after deviations
            segments = emotion_data.get("segments", [])
            if sorted_devs and segments:
                last_dev_time = sorted_devs[-1].end_time
                # Find next segment for this speaker after last deviation
                for seg in segments:
                    if (seg.get("speaker") == profile.speaker_id
                            and seg.get("start_time", 0) >= last_dev_time):
                        label = seg.get("emotion_label", "")
                        if not label:
                            emotions = seg.get("emotions", {})
                            non_neutral = {k: v for k, v in emotions.items() if k != "neutral"}
                            label = max(non_neutral, key=non_neutral.get) if non_neutral else ""
                        if label == profile.baseline_emotion:
                            ts = _format_timestamp(seg.get("start_time", 0))
                            snippet = seg.get("text", "")[:80]
                            text_part = f' \u2014 "{snippet}"' if snippet else ""
                            lines.append(f"   [{ts}] {label:<10} \u21a9{text_part}")
                        break

            # Show cluster patterns
            speaker_clusters = [c for c in analysis.clusters if c.speaker_id == profile.speaker_id]
            if speaker_clusters:
                lines.append("")
                for cluster in speaker_clusters:
                    time_range = (f"{_format_timestamp(cluster.start_time)}-"
                                  f"{_format_timestamp(cluster.end_time)}")
                    topic = ""
                    if cluster.topic_hint:
                        topic = f"\n           Topic: {cluster.topic_hint}"
                    lines.append(
                        f"  Pattern: {cluster.emotion_label} cluster "
                        f"[{time_range}] ({cluster.segment_count} segments){topic}"
                    )
        else:
            lines.append("  No notable shifts.")

    # ── Flags ──
    if analysis.flags:
        lines.append("")
        lines.append("FLAGS")
        lines.append("\u2500" * 50)
        for flag in analysis.flags:
            lines.append(f"  \u2691 {flag.message}")

    # ── Tier 3: Segment Table ──
    lines.append("")
    lines.append("SEGMENT DETAIL")
    lines.append("\u2500" * 50)
    lines.append(f" {'TIME':<9}{'SPEAKER':<13}{'EMOTION':<13}TEXT")
    lines.append(" " + "\u2500" * 49)

    segments = emotion_data.get("segments", [])

    # Build baseline lookup and deviation index for markers
    baselines = {}
    deviation_indices = set()
    for profile in analysis.speakers:
        baselines[profile.speaker_id] = profile.baseline_emotion
        for dev in profile.deviations:
            deviation_indices.add(dev.segment_index)

    # Track last non-baseline state per speaker for return-to-baseline marker
    last_was_deviation = {}

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue

        start = seg.get("start_time", 0.0)
        if not isinstance(start, (int, float)):
            start = 0.0
        speaker = seg.get("speaker", "unknown")
        text = seg.get("text", "").strip()
        label = seg.get("emotion_label", "")
        if not label:
            emotions = seg.get("emotions", {})
            non_neutral = {k: v for k, v in emotions.items() if k != "neutral"}
            label = max(non_neutral, key=non_neutral.get) if non_neutral else "neutral"

        baseline = baselines.get(speaker, "")

        # Determine role for display
        role_display = speaker
        for profile in analysis.speakers:
            if profile.speaker_id == speaker:
                role_display = _get_role_label(profile).lower()
                break

        # Determine marker
        marker = " "
        is_clinician = any(
            p.speaker_id == speaker and p.role.value == "clinician"
            for p in analysis.speakers
        )

        if is_clinician and label == baseline:
            # Suppress clinician baseline
            emotion_display = "\u2014"
            marker = " "
        elif i in deviation_indices:
            emotion_display = label
            marker = "\u25cf"
            last_was_deviation[speaker] = True
        elif last_was_deviation.get(speaker) and label == baseline:
            emotion_display = label
            marker = "\u25cb"
            last_was_deviation[speaker] = False
        else:
            emotion_display = label
            last_was_deviation[speaker] = False

        ts = _format_timestamp(start)
        snippet = f'"{text[:50]}..."' if len(text) > 50 else f'"{text}"' if text else ""
        lines.append(f" {ts:<9}{role_display:<13}{emotion_display:<12}{marker} {snippet}")

    lines.append("")
    lines.append(" \u25cf deviation from baseline    \u25cb return to baseline")
    lines.append(" \u2014 baseline (suppressed)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API (v1/v2 routing)
# ---------------------------------------------------------------------------

def format_emotion_for_soap(emotion_data: dict) -> str:
    """Convert emotion data into a concise clinical summary for the SOAP prompt.

    Routes to v1 or v2 formatting based on the data version.
    """
    if not _validate_emotion_data(emotion_data):
        logger.debug("No valid emotion data provided for SOAP formatting")
        return ""

    if _is_v2(emotion_data):
        return _format_soap_v2(emotion_data)
    return _format_soap_v1(emotion_data)


def format_emotion_for_panel(emotion_data: dict) -> str:
    """Detailed formatted display for the analysis panel.

    Routes to v1 (legacy segment dump) or v2 (3-tier per-speaker display).
    """
    if not _validate_emotion_data(emotion_data):
        logger.debug("No valid emotion data provided for panel formatting")
        return "No emotion analysis data available."

    if _is_v2(emotion_data):
        return _format_panel_v2(emotion_data)
    return _format_panel_v1(emotion_data)


def _generate_clinical_notes(segments: list, overall: dict) -> list:
    """Generate clinical relevance notes from emotion data (v1 legacy)."""
    notes = []

    if not segments:
        return notes

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

    For v2 data, uses emotion_label directly. For v1, scans emotions dict.
    """
    if not _validate_emotion_data(emotion_data):
        logger.debug("No valid emotion data for dominant emotion extraction")
        return []

    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
        logger.warning(f"Invalid threshold value: {threshold}, using default 0.3")
        threshold = 0.3

    segments = emotion_data.get("segments", [])
    results = []

    if _is_v2(emotion_data):
        # V2: use emotion_label directly (categorical, always 1.0 confidence)
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                continue
            label = segment.get("emotion_label", "")
            start_time = segment.get("start_time", 0.0)
            if not isinstance(start_time, (int, float)):
                start_time = 0.0
            if label and label != "neutral":
                results.append({
                    "emotion": label,
                    "confidence": 1.0,
                    "segment_index": i,
                    "timestamp": round(start_time, 2),
                })
    else:
        # V1: scan emotions dict
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
                    results.append({
                        "emotion": emotion_name,
                        "confidence": round(confidence, 4),
                        "segment_index": i,
                        "timestamp": round(start_time, 2),
                    })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    logger.debug(f"Found {len(results)} dominant emotions above threshold {threshold:.2f}")
    return results
