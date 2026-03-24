# Voice Emotion Analysis: Clinical Signal Extractor

**Date:** 2026-03-23
**Approach:** B — Clinical Signal Extractor
**Status:** Approved

## Problem Statement

The current voice emotion analysis output is a developer-oriented data dump that provides no clinical value to physicians. Key issues:

1. **Fake continuous scores**: The Modulate.ai API returns one categorical emotion per utterance, but the code synthesizes confidence scores (1.0/0.1) and displays bar charts suggesting granularity that doesn't exist.
2. **Speakers merged**: Doctor and patient emotions are averaged together. Doctor's "calm" dilutes patient's "concern."
3. **Clinical notes never fire**: `_generate_clinical_notes()` requires anxiety in >=50% of ALL segments (both speakers). In a 2-speaker encounter, the patient would need every single utterance to be anxious. This effectively never triggers.
4. **No temporal awareness**: Emotion shifts, clusters, and resolution patterns are invisible.
5. **Misleading negative finding**: "No clinically significant patterns detected" creates false reassurance and liability exposure.

## Design Constraints (from risk analysis)

These are non-negotiable:

1. **No LLM-generated narratives from emotion data.** All summarization is algorithmic (counting, grouping, clustering). No AI interpretation of categorical labels.
2. **No negative findings.** The system never says "no significant patterns" or "patient was fine." It reports what it detected or says "no deviations from baseline detected."
3. **Observational language only.** No diagnostic terms ("anxiety disorder"), no screening recommendations ("consider PHQ-9"). Observations with counts and timestamps.
4. **Disclaimer on all displays.** Every emotion output includes: "Emotion labels are algorithmic estimates from voice analysis, not clinical assessments."
5. **SOAP integration is opt-in.** Off by default (`emotion_in_soap: false`). When enabled, a brief observational note with disclaimer is passed to SOAP generation.

## Data Model (v2)

### Per-Segment Schema

```python
{
    "text": "Yeah, he can't walk...",
    "emotion_label": "concern",          # PRIMARY — categorical
    "emotion_raw": "Concerned",          # Original API string
    "emotions": {"concern": 1.0},        # DEPRECATED, backward compat only
    "start_time": 61.0,
    "end_time": 83.0,
    "speaker": "speaker_1",
}
```

### Overall Schema

```python
{
    "version": 2,
    "segments": [...],
    "overall": {
        "dominant_emotion": "calm",
        "emotion_distribution": {"calm": 10, "concern": 3, "confusion": 2},
        "total_segments": 28,
    }
}
```

### Key Changes

1. **`emotion_label` becomes the first-class field.** All downstream consumers (`_generate_clinical_notes`, `_get_top_emotions`, `format_emotion_for_soap`, `format_emotion_for_panel`) are rewritten to use `emotion_label` and frequency counts instead of score thresholds.

2. **`emotion_label` uses clinical mapped names** (lowercase, from `EMOTION_TO_CLINICAL` mapping): `"concern"`, `"confusion"`, `"calm"` — not the raw API strings. The raw API string is preserved in `emotion_raw` for display/debugging. This ensures consistent naming across all downstream code.

3. **`version: 2` is set at the top level** of the dict returned by `_build_emotion_data()`. This is the branching key for backward compatibility — `format_emotion_for_panel()` checks this field and routes v1 data to legacy rendering.

4. **`emotions` dict continues to be populated in v2 output** for backward compatibility — existing code paths like `get_dominant_emotions()` that iterate `emotions` will continue to work during migration. The dict is marked deprecated and will be removed in a future version once all consumers are migrated to `emotion_label`.

## Per-Speaker Analysis Engine

### New Module: `src/ai/emotion_speaker_analyzer.py`

#### Speaker Role Inference

**Edge cases and rules:**

- **2 speakers**: Speaker with higher proportions of Calm/Neutral/Confident and longer average utterances = clinician. Other speaker = patient (or caregiver).
- **1 speaker**: Defaults to `PATIENT` role. Per-speaker analysis still runs but there's nothing to separate. Baseline/deviation detection works the same way.
- **3+ speakers**: The inferred clinician keeps their role. Remaining speakers are all tagged as `UNKNOWN` initially. If one non-clinician speaker has notably more concern/anxiety than others, they may be the patient (the others are likely family/caregiver). If role inference is ambiguous, all non-clinician speakers are tagged `UNKNOWN` and analyzed individually.
- **Both speakers identical baseline**: If both speakers have the same baseline emotion and similar utterance lengths, fall back to `UNKNOWN` for both — do not guess. The analysis still works; it just won't label the headline as "Patient" or "Physician."
- **Override**: Roles can always be overridden via `settings.json` → `modulate.speaker_role_overrides` (format: `{"speaker_1": "patient", "speaker_2": "clinician"}`). Valid values are the `SpeakerRole` enum strings: `"clinician"`, `"patient"`, `"caregiver"`, `"unknown"`.

#### Baseline Detection

Each speaker's most frequent emotion is their "baseline." Only deviations from baseline are considered signal. This eliminates noise like greetings being "calm."

#### Data Structures

```python
class SpeakerRole(str, Enum):
    CLINICIAN = "clinician"
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    UNKNOWN = "unknown"

@dataclass
class SpeakerProfile:
    speaker_id: str
    role: SpeakerRole
    utterance_count: int
    baseline_emotion: str              # most frequent emotion
    baseline_ratio: float              # how dominant the baseline is (0-1)
    emotion_distribution: Dict[str, int]  # label -> count
    deviations: List[dict]             # segments where emotion != baseline

@dataclass
class EmotionCluster:
    emotion: str
    speaker_id: str
    segments: List[dict]               # the consecutive/nearby deviation segments
    start_time: float
    end_time: float
    topic_hint: str                    # first 80 chars of text from first segment in cluster (literal truncation, not summarized)

@dataclass
class EncounterAnalysis:
    speakers: Dict[str, SpeakerProfile]
    patient_speaker: Optional[SpeakerProfile]
    clusters: List[EmotionCluster]     # sustained deviation episodes
    clinical_flags: List[str]          # observational flags
```

#### Temporal Clustering

When a patient has 2+ non-baseline segments with the same emotion that are either consecutive or within a **120-second window** (measured from start_time of first to start_time of last), they form an `EmotionCluster`. The 120-second window accounts for interleaved clinician utterances between patient segments. Example from the sample data:

```
EmotionCluster(
    emotion="concern",
    speaker_id="speaker_1",
    segments=[seg9, seg11, seg13],
    start_time=61.0, end_time=169.0,
    topic_hint="he can't walk, getting him in and out..."
)
```

## Three-Tier Display

### Tier 1 — Panel Headline (2 seconds to scan)

Default view. Replaces the current 28-segment wall.

```
VOICE EMOTION ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Caregiver (speaker_1): sustained concern [01:01-02:49]
  around mobility and transport to appointments

Physician (speaker_2): baseline neutral throughout

⚠ Emotion labels are algorithmic estimates from voice
  analysis, not clinical assessments.
```

When no deviations exist:

```
VOICE EMOTION ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Patient (speaker_1): calm/neutral throughout (15 utterances)
Physician (speaker_2): neutral throughout (13 utterances)

No deviations from baseline detected.

⚠ Emotion labels are algorithmic estimates from voice
  analysis, not clinical assessments.
```

### Tier 2 — Speaker Summary (10 seconds)

Shown below headline.

```
SPEAKER DETAIL
──────────────────────────────────────────────────

CAREGIVER (speaker_1) — 12 utterances
  Baseline: calm (9 of 12)

  Notable shifts:
   [00:47] confusion — "Oh, yeah. Well... I don't know."
   [01:01] concern  — "he can't walk, getting him in and out..."
   [02:01] concern  — "we have nobody around here to help us..."
   [02:30] concern  — "thinking of giving them a call..."
   [03:43] confusion — "do they come to the home?"
   [04:04] calm ↩   — "Okay, we'll try to get that done then."

  Pattern: concern cluster [01:01-02:49] (3 segments)
           Topic: patient mobility / transport barriers

PHYSICIAN (speaker_2) — 16 utterances
  Baseline: neutral (12 of 16)
  No notable shifts.
```

Design decisions:
- `↩` arrow marks return to baseline (shows resolution)
- Only non-baseline emotions listed
- Text snippets provide context
- "Pattern" line summarizes clusters algorithmically

### Tier 3 — Segment Table (collapsed, "View Details" button)

```
 TIME     SPEAKER      EMOTION     TEXT
 ───────────────────────────────────────────────
 00:01    caregiver    calm        "Hello?"
 00:02    physician    —           "Hi, it's Dr. Yoga..."
 00:47    caregiver    confusion ● "Oh, yeah. Well..."
 01:01    caregiver    concern  ●  "he can't walk..."
 02:01    caregiver    concern  ●  "we have nobody..."
 04:04    caregiver    calm     ○  "Okay, we'll try..."
 04:11    physician    calm        "Bye-bye."

 ● deviation from baseline    ○ return to baseline
 — baseline (suppressed detail)
```

Physician baseline emotions suppressed to `—` (noise for clinical use).

## Clinical Flags

Algorithmic, observational flags generated from clusters and speaker profiles. All emotion names in flag rules use the **clinical mapped names** (lowercase, from `EMOTION_TO_CLINICAL`): `"concern"`, `"anxiety"`, `"confusion"`, etc.

### Flag Rules

| Trigger | Flag text |
|---------|-----------|
| Concern/anxiety cluster >=2 segments on patient | `"Sustained concern detected [timerange] — topic: [snippet]"` |
| Confusion cluster >=2 segments on patient | `"Repeated confusion detected [timerange] — topic: [snippet]"` |
| Sadness in >=30% of patient utterances | `"Sadness noted in [N] of [total] patient utterances"` |
| Fear in any patient segment | `"Fear detected at [timestamp] — context: [snippet]"` |
| Anger/frustration in >=2 patient segments | `"Frustration/anger noted in [N] patient utterances"` |
| High emotion variety (>=4 distinct non-baseline labels) | `"Varied emotional presentation across encounter"` |
| No deviations | *(no flag emitted — silence, not "all clear")* |

### Display

Flags appear in Tier 2 when present:

```
FLAGS
──────────────────────────────────────────────────
  ⚑ Sustained concern [01:01-02:49] — mobility/transport
  ⚑ Repeated confusion [00:47, 03:43] — referral process
```

## SOAP Integration (Opt-In)

Controlled by setting `emotion_in_soap: false` (default off).

When enabled, replaces current `format_emotion_for_soap()` output with:

```
Voice emotion observation: Caregiver showed sustained concern
(3 of 12 utterances, 01:01-02:49) related to patient mobility
and transport. Confusion noted regarding referral process.
[Algorithmic voice analysis — not a clinical assessment]
```

Constraints:
- Always includes disclaimer suffix
- Never uses clinical/diagnostic language
- Never states negative findings
- Reports observations with counts and timestamps only
- The SOAP LLM receives this as context and decides how/whether to incorporate it

## Settings

New/modified settings in `settings.json`:

```json
{
  "modulate": {
    "emotion_in_soap": false,
    "emotion_disclaimer": true,
    "speaker_role_overrides": {}
  }
}
```

## Files Modified

| File | Change |
|------|--------|
| `src/stt_providers/modulate.py` | `_build_emotion_data()` → v2 schema with `emotion_label` primary field |
| `src/ai/emotion_processor.py` | Rewrite all functions to use `emotion_label` and frequency counts; new `format_emotion_headline()`, `format_emotion_speaker_detail()`, `format_emotion_segment_table()`; rewrite `_generate_clinical_notes()` to use per-speaker frequency-based flags |
| `src/ai/emotion_speaker_analyzer.py` | **NEW** — `SpeakerEmotionAnalyzer` with role inference, baseline detection, temporal clustering, flag generation |
| `src/processing/generators/emotion.py` | Update `_run_emotion_to_panel()` to render 3-tier display; wire up View Details for Tier 3 |
| `src/ai/soap_generation.py` | Accept observational string from new `format_emotion_for_soap()` |
| `config/config.default.json` | Add `emotion_in_soap`, `emotion_disclaimer`, `speaker_role_overrides` defaults |

## Backward Compatibility

- The `emotions` dict continues to be populated in v2 data for backward compatibility (see Key Changes above)
- `format_emotion_for_panel()` checks for `version` field at top level; v1 data (no version field or `version: 1`) uses legacy rendering path
- Existing saved recordings with emotion data continue to display (degraded to v1 format)
- The string `"No clinically significant patterns detected."` in the current `_generate_clinical_notes()` (line 292 of `emotion_processor.py`) **must be removed** — it violates the "no negative findings" constraint

## What This Design Explicitly Does NOT Do

- No LLM interpretation of emotion labels
- No clinical/diagnostic recommendations
- No screening tool suggestions
- No negative findings ("patient was fine")
- No automatic SOAP injection (opt-in only)
- No emotion data in exportable clinical documents by default
