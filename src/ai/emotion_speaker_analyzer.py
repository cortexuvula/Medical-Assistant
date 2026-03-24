"""
Per-speaker emotion analysis engine.

Analyzes emotion data from Modulate.ai voice emotion analysis on a per-speaker
basis, computing baselines, detecting deviations, clustering emotion events,
and generating observational clinical flags.

Supports both v1 (raw emotion dicts) and v2 (pre-labeled clinical emotions)
data formats.
"""

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ai.emotion_processor import _format_timestamp
from settings.settings_manager import settings_manager
from stt_providers.modulate import EMOTION_TO_CLINICAL
from utils.structured_logging import get_logger


class SpeakerRole(str, Enum):
    CLINICIAN = "clinician"
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    UNKNOWN = "unknown"


@dataclass
class EmotionDeviation:
    emotion_label: str
    start_time: float
    end_time: float
    text_snippet: str       # first 80 chars of text
    segment_index: int


@dataclass
class SpeakerProfile:
    speaker_id: str
    role: SpeakerRole
    utterance_count: int
    baseline_emotion: str
    baseline_ratio: float
    emotion_counts: Dict[str, int]
    deviations: List[EmotionDeviation] = field(default_factory=list)


@dataclass
class EmotionCluster:
    emotion_label: str
    speaker_id: str
    start_time: float
    end_time: float
    segment_count: int
    deviations: List[EmotionDeviation] = field(default_factory=list)
    topic_hint: str = ""    # first 80 chars from first deviation


@dataclass
class ClinicalFlag:
    message: str            # observational language ONLY
    speaker_id: str
    speaker_role: SpeakerRole
    emotion: str


@dataclass
class EncounterAnalysis:
    speakers: List[SpeakerProfile] = field(default_factory=list)
    clusters: List[EmotionCluster] = field(default_factory=list)
    flags: List[ClinicalFlag] = field(default_factory=list)
    total_segments: int = 0
    disclaimer: str = ""


class SpeakerEmotionAnalyzer:
    """Analyzes emotion data per-speaker with baseline detection and clustering."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def analyze(self, emotion_data: dict) -> EncounterAnalysis:
        """Main entry point. Handles both v1 and v2 data.

        Args:
            emotion_data: Dictionary with 'segments' list containing emotion data.

        Returns:
            EncounterAnalysis with speaker profiles, clusters, and flags.
        """
        if not emotion_data or not isinstance(emotion_data, dict):
            return EncounterAnalysis(disclaimer=self._get_disclaimer())

        segments = emotion_data.get("segments", [])
        if not segments:
            return EncounterAnalysis(disclaimer=self._get_disclaimer())

        # Group by speaker
        speaker_groups = self._group_by_speaker(segments)

        # Infer roles
        roles = self._infer_speaker_roles(speaker_groups)

        # Build profiles
        speakers = []
        all_clusters = []
        all_flags = []

        for speaker_id, indexed_segments in speaker_groups.items():
            role = roles.get(speaker_id, SpeakerRole.UNKNOWN)
            baseline, ratio = self._compute_baseline(indexed_segments)

            # Count emotions
            emotion_counts: Dict[str, int] = {}
            for _, seg in indexed_segments:
                label = self._extract_emotion_label(seg)
                emotion_counts[label] = emotion_counts.get(label, 0) + 1

            deviations = self._find_deviations(indexed_segments, baseline)

            profile = SpeakerProfile(
                speaker_id=speaker_id,
                role=role,
                utterance_count=len(indexed_segments),
                baseline_emotion=baseline,
                baseline_ratio=ratio,
                emotion_counts=emotion_counts,
                deviations=deviations,
            )
            speakers.append(profile)

            # Only detect clusters for non-clinician speakers
            if role != SpeakerRole.CLINICIAN:
                window = settings_manager.get(
                    "modulate", {}
                ).get("emotion_cluster_window_seconds", 120)
                clusters = self._detect_clusters(deviations, window_seconds=window)
                for c in clusters:
                    c.speaker_id = speaker_id
                all_clusters.extend(clusters)

                flags = self._generate_flags(profile, clusters)
                all_flags.extend(flags)

        return EncounterAnalysis(
            speakers=speakers,
            clusters=all_clusters,
            flags=all_flags,
            total_segments=len(segments),
            disclaimer=self._get_disclaimer(),
        )

    def _extract_emotion_label(self, segment: dict) -> str:
        """Get emotion_label from v2 segment, or derive from v1 emotions dict."""
        label = segment.get("emotion_label")
        if label:
            # v2 uses lowercase clinical names, v1 used capitalized raw strings
            if label[0].isupper():
                # Likely v1 raw label, map to clinical
                return EMOTION_TO_CLINICAL.get(label, label.lower())
            return label
        # Fall back to v1: max key from emotions dict
        emotions = segment.get("emotions", {})
        if emotions:
            # Filter out neutral for max detection
            non_neutral = {k: v for k, v in emotions.items() if k != "neutral"}
            if non_neutral:
                return max(non_neutral, key=non_neutral.get)
        return "neutral"

    def _group_by_speaker(self, segments: list) -> Dict[str, list]:
        """Group segments by speaker field.

        Returns:
            Dict mapping speaker_id to list of (index, segment) tuples.
        """
        groups: Dict[str, list] = {}
        for i, seg in enumerate(segments):
            speaker = seg.get("speaker", "unknown")
            groups.setdefault(speaker, []).append((i, seg))
        return groups

    def _infer_speaker_roles(
        self, speaker_groups: Dict[str, list]
    ) -> Dict[str, SpeakerRole]:
        """Infer speaker roles.

        Rules:
        - Check settings for manual overrides first
        - 1 speaker: defaults to PATIENT
        - 2 speakers: speaker with higher calm/neutral/confident proportion
          AND longer avg utterance = CLINICIAN, other = PATIENT
        - If both identical baseline: both UNKNOWN
        - 3+ speakers: infer clinician, rest UNKNOWN
        """
        overrides = settings_manager.get("modulate", {}).get(
            "speaker_role_overrides", {}
        )

        roles: Dict[str, SpeakerRole] = {}
        # Apply overrides first
        for speaker_id, role_str in overrides.items():
            try:
                roles[speaker_id] = SpeakerRole(role_str)
            except ValueError:
                pass

        # If all speakers have overrides, return
        unassigned = [s for s in speaker_groups if s not in roles]
        if not unassigned:
            return roles

        if len(speaker_groups) == 1:
            speaker_id = list(speaker_groups.keys())[0]
            if speaker_id not in roles:
                roles[speaker_id] = SpeakerRole.PATIENT
            return roles

        if len(unassigned) >= 2:
            # Score each speaker: proportion of calm/neutral/confident + avg text len
            CLINICIAN_EMOTIONS = {"calm", "neutral", "confidence", "confident"}
            scores: Dict[str, float] = {}
            for speaker_id in unassigned:
                segments = speaker_groups[speaker_id]
                total = len(segments)
                if total == 0:
                    scores[speaker_id] = 0
                    continue
                calm_count = sum(
                    1 for _, seg in segments
                    if self._extract_emotion_label(seg) in CLINICIAN_EMOTIONS
                )
                avg_text_len = (
                    sum(len(seg.get("text", "")) for _, seg in segments) / total
                )
                # Score: weighted combination of calm ratio and text length
                calm_ratio = calm_count / total
                scores[speaker_id] = (
                    calm_ratio * 0.6 + min(avg_text_len / 200, 1.0) * 0.4
                )

            sorted_speakers = sorted(
                scores.items(), key=lambda x: x[1], reverse=True
            )
            top_score = sorted_speakers[0][1]
            second_score = (
                sorted_speakers[1][1] if len(sorted_speakers) > 1 else 0
            )

            # If scores are very close (within 0.1), can't distinguish
            if abs(top_score - second_score) < 0.1:
                for speaker_id in unassigned:
                    roles[speaker_id] = SpeakerRole.UNKNOWN
            else:
                roles[sorted_speakers[0][0]] = SpeakerRole.CLINICIAN
                for speaker_id, _ in sorted_speakers[1:]:
                    if len(speaker_groups) == 2:
                        roles[speaker_id] = SpeakerRole.PATIENT
                    else:
                        roles[speaker_id] = SpeakerRole.UNKNOWN

        return roles

    def _compute_baseline(self, indexed_segments: list) -> tuple:
        """Compute baseline emotion (most frequent) for a list of segments.

        Args:
            indexed_segments: List of (index, segment) tuples.

        Returns:
            Tuple of (baseline_emotion, ratio).
        """
        labels = [self._extract_emotion_label(seg) for _, seg in indexed_segments]
        if not labels:
            return ("neutral", 1.0)
        counter = Counter(labels)
        baseline, count = counter.most_common(1)[0]
        return (baseline, count / len(labels))

    def _find_deviations(
        self, indexed_segments: list, baseline: str
    ) -> List[EmotionDeviation]:
        """Find segments that deviate from baseline."""
        deviations = []
        for idx, seg in indexed_segments:
            label = self._extract_emotion_label(seg)
            if label != baseline:
                text = seg.get("text", "")
                snippet = text[:80] if text else ""
                deviations.append(EmotionDeviation(
                    emotion_label=label,
                    start_time=seg.get("start_time", 0.0),
                    end_time=seg.get("end_time", 0.0),
                    text_snippet=snippet,
                    segment_index=idx,
                ))
        return deviations

    def _detect_clusters(
        self,
        deviations: List[EmotionDeviation],
        window_seconds: float = 120.0,
    ) -> List[EmotionCluster]:
        """Detect temporal clusters of same-emotion deviations within window.

        For each unique emotion in deviations, scan chronologically.
        2+ deviations of same emotion with start_times within window form a cluster.
        """
        if not deviations:
            return []

        # Group deviations by emotion
        by_emotion: Dict[str, List[EmotionDeviation]] = {}
        for dev in deviations:
            by_emotion.setdefault(dev.emotion_label, []).append(dev)

        clusters = []
        for emotion, devs in by_emotion.items():
            if len(devs) < 2:
                continue
            sorted_devs = sorted(devs, key=lambda d: d.start_time)

            # Greedy clustering: start a cluster, extend while within window
            current_cluster = [sorted_devs[0]]
            for dev in sorted_devs[1:]:
                if dev.start_time - current_cluster[0].start_time <= window_seconds:
                    current_cluster.append(dev)
                else:
                    if len(current_cluster) >= 2:
                        clusters.append(
                            self._make_cluster(emotion, current_cluster)
                        )
                    current_cluster = [dev]
            if len(current_cluster) >= 2:
                clusters.append(self._make_cluster(emotion, current_cluster))

        return sorted(clusters, key=lambda c: c.start_time)

    def _make_cluster(
        self, emotion: str, devs: List[EmotionDeviation]
    ) -> EmotionCluster:
        """Create an EmotionCluster from a list of deviations."""
        return EmotionCluster(
            emotion_label=emotion,
            speaker_id="",  # Will be set by caller
            start_time=devs[0].start_time,
            end_time=devs[-1].end_time,
            segment_count=len(devs),
            deviations=devs,
            topic_hint=devs[0].text_snippet[:80] if devs[0].text_snippet else "",
        )

    def _generate_flags(
        self,
        profile: SpeakerProfile,
        clusters: List[EmotionCluster],
    ) -> List[ClinicalFlag]:
        """Generate observational clinical flags from a speaker's profile and clusters.

        Rules:
        - Concern/anxiety cluster >=2 segments: flag
        - Confusion cluster >=2 segments: flag
        - Sadness in >=30% of utterances: flag
        - Fear in any segment: flag
        - Anger/frustration in >=2 segments: flag
        - High emotion variety (>=4 distinct non-baseline labels): flag
        - No deviations: NO flag (silence, not "all clear")

        Language is STRICTLY observational. No diagnostic terms.
        """
        flags = []

        for cluster in clusters:
            time_range = (
                f"{_format_timestamp(cluster.start_time)}-"
                f"{_format_timestamp(cluster.end_time)}"
            )
            topic = f" — {cluster.topic_hint}" if cluster.topic_hint else ""

            if cluster.emotion_label in ("concern", "anxiety"):
                flags.append(ClinicalFlag(
                    message=(
                        f"Sustained {cluster.emotion_label} detected "
                        f"[{time_range}]{topic}"
                    ),
                    speaker_id=profile.speaker_id,
                    speaker_role=profile.role,
                    emotion=cluster.emotion_label,
                ))
            elif cluster.emotion_label == "confusion":
                flags.append(ClinicalFlag(
                    message=(
                        f"Repeated confusion detected [{time_range}]{topic}"
                    ),
                    speaker_id=profile.speaker_id,
                    speaker_role=profile.role,
                    emotion="confusion",
                ))
            elif cluster.emotion_label in ("anger", "frustration"):
                flags.append(ClinicalFlag(
                    message=(
                        f"{cluster.emotion_label.capitalize()} noted in "
                        f"{cluster.segment_count} utterances [{time_range}]"
                    ),
                    speaker_id=profile.speaker_id,
                    speaker_role=profile.role,
                    emotion=cluster.emotion_label,
                ))

        # Non-cluster flags based on overall counts
        total = profile.utterance_count
        if total > 0:
            sadness_count = profile.emotion_counts.get("sadness", 0)
            if sadness_count / total >= 0.3:
                flags.append(ClinicalFlag(
                    message=(
                        f"Sadness noted in {sadness_count} of {total} utterances"
                    ),
                    speaker_id=profile.speaker_id,
                    speaker_role=profile.role,
                    emotion="sadness",
                ))

            fear_count = profile.emotion_counts.get("fear", 0)
            if fear_count > 0:
                # Find the first fear deviation for timestamp
                fear_devs = [
                    d for d in profile.deviations if d.emotion_label == "fear"
                ]
                if fear_devs:
                    ts = _format_timestamp(fear_devs[0].start_time)
                    context = (
                        f" — {fear_devs[0].text_snippet}"
                        if fear_devs[0].text_snippet else ""
                    )
                    flags.append(ClinicalFlag(
                        message=f"Fear detected at [{ts}]{context}",
                        speaker_id=profile.speaker_id,
                        speaker_role=profile.role,
                        emotion="fear",
                    ))

        # High emotion variety
        non_baseline = [
            e for e in profile.emotion_counts if e != profile.baseline_emotion
        ]
        if len(non_baseline) >= 4:
            flags.append(ClinicalFlag(
                message="Varied emotional presentation across encounter",
                speaker_id=profile.speaker_id,
                speaker_role=profile.role,
                emotion="varied",
            ))

        return flags

    def _get_disclaimer(self) -> str:
        """Get disclaimer text from settings or use default."""
        settings = settings_manager.get("modulate", {})
        return settings.get(
            "emotion_disclaimer",
            "Voice emotion analysis is observational only and based on acoustic "
            "features. It does not constitute a clinical assessment, diagnosis, "
            "or screening tool.",
        )
