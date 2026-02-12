"""
Compliance Agent for Clinical Guidelines

Analyzes SOAP notes against clinical guidelines for treatment alignment.
Extracts conditions/medications from the SOAP note, retrieves per-condition
guidelines, and evaluates whether treatment decisions align with
evidence-based recommendations.

Architecture Note:
    This agent uses the GuidelinesRetriever which ONLY accesses the
    separate guidelines database, NOT patient documents.
"""

import json
import re
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse
from utils.structured_logging import get_logger

# Try to import guidelines retriever
try:
    from rag.guidelines_retriever import get_guidelines_retriever
    GUIDELINES_AVAILABLE = True
except ImportError:
    GUIDELINES_AVAILABLE = False

# Try to import guidelines models
try:
    from rag.guidelines_models import (
        ConditionFinding,
        ConditionCompliance,
        ComplianceAnalysisResult,
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

# Try to import NER extractor
try:
    from rag.medical_ner import get_medical_ner_extractor
    NER_AVAILABLE = True
except ImportError:
    NER_AVAILABLE = False

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = get_logger(__name__)

DISCLAIMER = (
    "AI-assisted analysis for clinical decision support. "
    "Verify findings against current clinical guidelines."
)


class ComplianceAgent(BaseAgent):
    """Agent specialized in condition-centric clinical guidelines compliance analysis."""

    DEFAULT_CONFIG = AgentConfig(
        name="ComplianceAgent",
        description="Analyzes SOAP notes for treatment alignment with clinical guidelines",
        system_prompt="""You are a clinical compliance analyst evaluating whether treatment decisions in a SOAP note align with clinical guidelines.

IMPORTANT RULES:
1. Evaluate TREATMENT ALIGNMENT, not documentation completeness.
2. Only cite guidelines from the PROVIDED CONTEXT below — never fabricate citations.
3. Use exactly three status levels:
   - ALIGNED: Treatment matches guideline recommendations
   - GAP: Treatment deviates from or omits a guideline recommendation
   - REVIEW: Insufficient information to determine alignment, or a guideline may apply but context is ambiguous
4. For each finding, quote the relevant guideline text you are referencing.
5. Consider clinical context — some deviations may be clinically justified.
6. If no relevant guidelines are provided for a condition, state that explicitly.

OUTPUT FORMAT — respond with ONLY valid JSON:
{
  "conditions": [
    {
      "condition": "Condition Name",
      "findings": [
        {
          "status": "ALIGNED|GAP|REVIEW",
          "finding": "What was observed in the SOAP note",
          "guideline_reference": "Exact quote or close paraphrase from provided guideline text",
          "recommendation": "Specific action to consider (empty string for ALIGNED)"
        }
      ]
    }
  ]
}

Rules for JSON output:
- Output ONLY the JSON object, no markdown fences or extra text
- Every finding MUST reference text from the provided guidelines
- Use empty string "" for recommendation when status is ALIGNED
- Include all conditions identified, even if no guidelines were found""",
        model="gpt-4",
        temperature=0.2,
        max_tokens=4000
    )

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        ai_caller: Optional['AICallerProtocol'] = None
    ):
        """Initialize the compliance agent.

        Args:
            config: Optional custom configuration
            ai_caller: Optional AI caller for dependency injection
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)

    def execute(self, task: AgentTask) -> AgentResponse:
        """Analyze SOAP note for clinical guidelines compliance.

        Performs condition-centric analysis:
        1. Extract conditions/medications from SOAP note via NER
        2. Retrieve per-condition guidelines
        3. Call LLM for alignment analysis
        4. Parse and verify citations
        5. Compute per-condition and overall scores

        Args:
            task: Task containing:
                - soap_note: The SOAP note to analyze
                - specialties: Optional list of specialties to focus on
                - sources: Optional list of guideline sources to prioritize
                - max_guidelines: Maximum guidelines per condition (default 5)

        Returns:
            AgentResponse with compliance analysis and structured results
        """
        start_time = time.time()

        try:
            soap_note = task.input_data.get('soap_note', '')
            specialties = task.input_data.get('specialties', None)
            sources = task.input_data.get('sources', None)
            max_guidelines = task.input_data.get('max_guidelines', 5)

            if not soap_note:
                return AgentResponse(
                    result="",
                    success=False,
                    error="No SOAP note provided for compliance analysis"
                )

            # Step 1: Extract conditions and medications from SOAP note
            extracted = self._extract_conditions(soap_note)
            if not extracted:
                return self._build_insufficient_data_response(
                    start_time,
                    "Could not extract any conditions from the SOAP note."
                )

            # Step 2: Retrieve per-condition guidelines
            guidelines_by_condition = {}
            total_guidelines_searched = 0

            if GUIDELINES_AVAILABLE:
                try:
                    retriever = get_guidelines_retriever()
                    guidelines_by_condition = retriever.get_guidelines_for_conditions(
                        conditions=extracted,
                        top_k_per_condition=max_guidelines,
                    )
                    total_guidelines_searched = sum(
                        len(v) for v in guidelines_by_condition.values()
                    )
                except Exception as e:
                    logger.warning(f"Failed to retrieve guidelines: {e}")
            else:
                logger.warning("Guidelines retrieval system not configured")

            if total_guidelines_searched == 0:
                return self._build_insufficient_data_response(
                    start_time,
                    "No matching clinical guidelines found in the database.\n\n"
                    "To enable compliance checking:\n"
                    "1. Upload clinical guidelines (PDF, DOCX, TXT)\n"
                    "2. Specify specialty and source\n"
                    "3. Re-run compliance analysis"
                )

            # Step 3: Build per-condition prompt with guideline text
            prompt = self._build_condition_prompt(
                soap_note=soap_note,
                extracted_conditions=extracted,
                guidelines_by_condition=guidelines_by_condition,
                additional_context=task.context,
            )

            # Step 4: Call LLM for alignment analysis
            raw_response = self._call_ai(prompt)

            # Step 5: Parse structured response
            analysis_result = self._parse_analysis_response(
                raw_response, guidelines_by_condition
            )
            analysis_result.guidelines_searched = total_guidelines_searched

            # Step 6: Compute scores
            self._compute_scores(analysis_result)

            # Build human-readable text from structured result
            readable_text = self._format_readable(analysis_result)

            processing_time_ms = (time.time() - start_time) * 1000

            # Serialize conditions for metadata
            conditions_data = []
            for cc in analysis_result.conditions:
                cond_dict = {
                    'condition': cc.condition,
                    'status': cc.status,
                    'score': cc.score,
                    'guidelines_matched': cc.guidelines_matched,
                    'findings': [],
                }
                for f in cc.findings:
                    cond_dict['findings'].append({
                        'status': f.status,
                        'finding': f.finding,
                        'guideline_reference': f.guideline_reference,
                        'recommendation': f.recommendation,
                        'citation_verified': f.citation_verified,
                    })
                conditions_data.append(cond_dict)

            # Count totals
            aligned_count = sum(
                1 for cc in analysis_result.conditions
                for f in cc.findings if f.status == 'ALIGNED'
            )
            gap_count = sum(
                1 for cc in analysis_result.conditions
                for f in cc.findings if f.status == 'GAP'
            )
            review_count = sum(
                1 for cc in analysis_result.conditions
                for f in cc.findings if f.status == 'REVIEW'
            )

            metadata = {
                'guidelines_checked': total_guidelines_searched,
                'compliant_count': aligned_count,
                'gap_count': gap_count,
                'warning_count': review_count,
                'overall_score': analysis_result.overall_score,
                'has_sufficient_data': analysis_result.has_sufficient_data,
                'conditions': conditions_data,
                'conditions_count': len(analysis_result.conditions),
                'disclaimer': analysis_result.disclaimer,
                'specialties_analyzed': specialties or ['general'],
                'sources_checked': sources or [],
                'model_used': self.config.model,
                'processing_time_ms': processing_time_ms,
                'guidelines_available': GUIDELINES_AVAILABLE,
            }

            response = AgentResponse(
                result=readable_text,
                thoughts=(
                    f"Analyzed {len(analysis_result.conditions)} conditions against "
                    f"{total_guidelines_searched} guidelines. "
                    f"Score: {int(analysis_result.overall_score * 100)}% "
                    f"({aligned_count} aligned, {gap_count} gaps, {review_count} review)."
                ),
                success=True,
                metadata=metadata
            )

            self.add_to_history(task, response)
            return response

        except Exception as e:
            logger.error(f"Error in compliance analysis: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )

    def _extract_conditions(self, soap_note: str) -> list[dict]:
        """Extract conditions and their associated medications from SOAP note.

        Uses MedicalNERExtractor for pattern-based extraction, then groups
        medications with their associated conditions.

        Args:
            soap_note: The full SOAP note text

        Returns:
            List of dicts with 'condition' and 'medications' keys
        """
        conditions_list = []

        if NER_AVAILABLE:
            try:
                ner = get_medical_ner_extractor()
                entities = ner.extract_to_dict(soap_note)

                # Get conditions
                raw_conditions = entities.get('condition', [])
                raw_medications = entities.get('medication', [])

                med_names = [
                    m.get('normalized_name') or m.get('text', '')
                    for m in raw_medications
                ]

                for cond in raw_conditions:
                    name = cond.get('normalized_name') or cond.get('text', '')
                    if name:
                        conditions_list.append({
                            'condition': name,
                            'medications': med_names,
                        })

                if conditions_list:
                    return conditions_list
            except Exception as e:
                logger.warning(f"NER extraction failed, using LLM fallback: {e}")

        # Fallback: Use LLM to extract conditions
        try:
            extraction_prompt = (
                "Extract the medical conditions and their associated medications "
                "from this SOAP note. Return ONLY valid JSON:\n\n"
                '{"conditions": [{"condition": "name", "medications": ["med1", "med2"]}]}\n\n'
                f"SOAP Note:\n{soap_note[:6000]}"
            )
            raw = self._call_ai(extraction_prompt)
            cleaned = self._clean_json_response(raw)
            parsed = json.loads(cleaned)
            conditions_list = parsed.get('conditions', [])
        except Exception as e:
            logger.warning(f"LLM condition extraction failed: {e}")

        return conditions_list

    def _build_condition_prompt(
        self,
        soap_note: str,
        extracted_conditions: list[dict],
        guidelines_by_condition: dict,
        additional_context: Optional[str] = None,
    ) -> str:
        """Build per-condition prompt with relevant guideline text.

        Args:
            soap_note: The full SOAP note
            extracted_conditions: Extracted conditions with medications
            guidelines_by_condition: Guidelines retrieved per condition
            additional_context: Optional additional context

        Returns:
            Formatted prompt string
        """
        parts = []

        parts.append(
            "Analyze whether the treatment decisions in this SOAP note align "
            "with the provided clinical guidelines for each condition.\n"
        )

        if additional_context:
            parts.append(f"Additional Context: {additional_context}\n")

        # Per-condition guideline sections
        parts.append("# CLINICAL GUIDELINES BY CONDITION\n")

        for item in extracted_conditions:
            cond_name = item.get('condition', '')
            meds = item.get('medications', [])
            guidelines = guidelines_by_condition.get(cond_name, [])

            parts.append(f"\n## {cond_name}")
            if meds:
                parts.append(f"Current medications: {', '.join(meds)}")

            if guidelines:
                parts.append(f"\nRelevant guidelines ({len(guidelines)} found):")
                for i, g in enumerate(guidelines, 1):
                    source = g.guideline_source or "Unknown"
                    title = g.guideline_title or "Untitled"
                    version = g.guideline_version or ""
                    rec_class = g.recommendation_class or ""
                    ev_level = g.evidence_level or ""

                    header = f"  [{i}] {source} — {title}"
                    if version:
                        header += f" ({version})"
                    if rec_class:
                        header += f" | Class {rec_class}"
                    if ev_level:
                        header += f", Level {ev_level}"
                    parts.append(header)
                    parts.append(f"  Text: {g.chunk_text}")
                    parts.append("")
            else:
                parts.append("  No matching guidelines found in database.")

        parts.append(f"\n# SOAP NOTE\n\n{soap_note}\n")

        parts.append(
            "\n---\n"
            "Analyze treatment alignment for each condition using ONLY the "
            "guidelines provided above. Respond with JSON as specified."
        )

        return "\n".join(parts)

    def _parse_analysis_response(
        self,
        raw_response: str,
        guidelines_by_condition: dict,
    ) -> 'ComplianceAnalysisResult':
        """Parse the LLM response into a ComplianceAnalysisResult.

        Also verifies citations against retrieved guideline text.

        Args:
            raw_response: Raw LLM response text
            guidelines_by_condition: Retrieved guidelines for verification

        Returns:
            ComplianceAnalysisResult with parsed and verified data
        """
        result = ComplianceAnalysisResult() if MODELS_AVAILABLE else None
        if result is None:
            # Minimal fallback
            from types import SimpleNamespace
            result = SimpleNamespace(
                conditions=[], overall_score=0.0,
                has_sufficient_data=False, guidelines_searched=0,
                disclaimer=DISCLAIMER,
            )

        # Collect all guideline text for citation verification
        all_guideline_texts = []
        for cond_guidelines in guidelines_by_condition.values():
            for g in cond_guidelines:
                all_guideline_texts.append(g.chunk_text.lower())

        try:
            cleaned = self._clean_json_response(raw_response)
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Try to extract JSON from mixed text
            parsed = self._extract_json_from_text(raw_response)
            if not parsed:
                logger.warning("Failed to parse JSON from compliance response")
                # Fall back to regex parsing
                return self._fallback_parse(raw_response, all_guideline_texts)

        # Parse conditions from JSON
        conditions_data = parsed.get('conditions', [])
        for cond_data in conditions_data:
            cond_name = cond_data.get('condition', 'Unknown')
            findings_data = cond_data.get('findings', [])

            findings = []
            for fd in findings_data:
                status = fd.get('status', 'REVIEW').upper()
                if status not in ('ALIGNED', 'GAP', 'REVIEW'):
                    # Map old status names
                    status_map = {
                        'COMPLIANT': 'ALIGNED',
                        'WARNING': 'REVIEW',
                    }
                    status = status_map.get(status, 'REVIEW')

                ref_text = fd.get('guideline_reference', '')
                citation_verified = self._verify_citation(
                    ref_text, all_guideline_texts
                )

                finding = ConditionFinding(
                    status=status,
                    finding=fd.get('finding', ''),
                    guideline_reference=ref_text,
                    recommendation=fd.get('recommendation', ''),
                    citation_verified=citation_verified,
                ) if MODELS_AVAILABLE else {
                    'status': status,
                    'finding': fd.get('finding', ''),
                    'guideline_reference': ref_text,
                    'recommendation': fd.get('recommendation', ''),
                    'citation_verified': citation_verified,
                }
                findings.append(finding)

            cond_guidelines = guidelines_by_condition.get(cond_name, [])

            condition = ConditionCompliance(
                condition=cond_name,
                status='REVIEW',  # Will be computed later
                findings=findings,
                guidelines_matched=len(cond_guidelines),
            ) if MODELS_AVAILABLE else SimpleNamespace(
                condition=cond_name, status='REVIEW',
                findings=findings, score=0.0,
                guidelines_matched=len(cond_guidelines),
            )
            result.conditions.append(condition)

        result.has_sufficient_data = len(result.conditions) > 0

        return result

    def _verify_citation(
        self, reference_text: str, guideline_texts: list[str]
    ) -> bool:
        """Check if a citation references text actually present in retrieved guidelines.

        Uses fuzzy substring matching — a citation is verified if a significant
        portion of its words appear in any guideline chunk.

        Args:
            reference_text: The citation text from the LLM
            guideline_texts: List of lowercased guideline chunk texts

        Returns:
            True if citation can be matched to a guideline
        """
        if not reference_text or not guideline_texts:
            return False

        ref_lower = reference_text.lower().strip()
        if len(ref_lower) < 10:
            return False

        # Extract key words (skip very short words)
        ref_words = [w for w in ref_lower.split() if len(w) > 3]
        if not ref_words:
            return False

        for gt in guideline_texts:
            matching_words = sum(1 for w in ref_words if w in gt)
            if len(ref_words) > 0 and matching_words / len(ref_words) >= 0.4:
                return True

        return False

    def _fallback_parse(
        self, raw_text: str, guideline_texts: list[str]
    ) -> 'ComplianceAnalysisResult':
        """Parse compliance findings from free text using regex.

        Used when JSON parsing fails.

        Args:
            raw_text: Raw LLM response
            guideline_texts: Guideline texts for citation verification

        Returns:
            ComplianceAnalysisResult
        """
        result = ComplianceAnalysisResult() if MODELS_AVAILABLE else None
        if result is None:
            from types import SimpleNamespace
            result = SimpleNamespace(
                conditions=[], overall_score=0.0,
                has_sufficient_data=False, guidelines_searched=0,
                disclaimer=DISCLAIMER,
            )

        # Match [STATUS] patterns
        pattern = r'\[(ALIGNED|GAP|REVIEW|COMPLIANT|WARNING)\]\s*([^-\n]+)\s*-\s*([^\n]+)'
        matches = re.findall(pattern, raw_text, re.IGNORECASE)

        # Group by condition-like first token
        conditions_map = {}
        for status_str, guideline, finding in matches:
            status = status_str.upper()
            status_map = {'COMPLIANT': 'ALIGNED', 'WARNING': 'REVIEW'}
            status = status_map.get(status, status)

            ref = guideline.strip()
            citation_verified = self._verify_citation(ref, guideline_texts)

            # Try to extract recommendation
            recommendation = ""
            finding_pos = raw_text.find(finding)
            if finding_pos != -1:
                following = raw_text[finding_pos:finding_pos + 500]
                rec_match = re.search(
                    r'Recommendation:\s*([^\n]+)', following, re.IGNORECASE
                )
                if rec_match:
                    recommendation = rec_match.group(1).strip()

            # Use a generic condition name from guideline reference
            cond_key = ref.split(',')[0].strip() if ',' in ref else ref[:40]

            if cond_key not in conditions_map:
                conditions_map[cond_key] = []

            finding_obj = ConditionFinding(
                status=status,
                finding=finding.strip(),
                guideline_reference=ref,
                recommendation=recommendation,
                citation_verified=citation_verified,
            ) if MODELS_AVAILABLE else {
                'status': status, 'finding': finding.strip(),
                'guideline_reference': ref,
                'recommendation': recommendation,
                'citation_verified': citation_verified,
            }
            conditions_map[cond_key].append(finding_obj)

        for cond_name, findings in conditions_map.items():
            condition = ConditionCompliance(
                condition=cond_name,
                status='REVIEW',
                findings=findings,
                guidelines_matched=len(findings),
            ) if MODELS_AVAILABLE else None
            if condition:
                result.conditions.append(condition)

        result.has_sufficient_data = len(result.conditions) > 0
        return result

    def _compute_scores(self, result) -> None:
        """Compute per-condition and overall alignment scores.

        Scoring formula per condition:
            aligned / (aligned + gaps + review * 0.5)

        No findings = 0 score (not 100%).

        Args:
            result: ComplianceAnalysisResult to update in-place
        """
        total_aligned = 0
        total_gap = 0
        total_review = 0

        for condition in result.conditions:
            findings = condition.findings
            aligned = sum(
                1 for f in findings
                if (f.status if hasattr(f, 'status') else f['status']) == 'ALIGNED'
            )
            gaps = sum(
                1 for f in findings
                if (f.status if hasattr(f, 'status') else f['status']) == 'GAP'
            )
            reviews = sum(
                1 for f in findings
                if (f.status if hasattr(f, 'status') else f['status']) == 'REVIEW'
            )

            denominator = aligned + gaps + reviews * 0.5
            if denominator > 0:
                condition.score = round(aligned / denominator, 2)
            else:
                condition.score = 0.0

            # Set condition status to worst finding
            if gaps > 0:
                condition.status = 'GAP'
            elif reviews > 0:
                condition.status = 'REVIEW'
            elif aligned > 0:
                condition.status = 'ALIGNED'
            else:
                condition.status = 'REVIEW'

            total_aligned += aligned
            total_gap += gaps
            total_review += reviews

        # Overall score
        total_denominator = total_aligned + total_gap + total_review * 0.5
        if total_denominator > 0:
            result.overall_score = round(total_aligned / total_denominator, 2)
        else:
            result.overall_score = 0.0

    def _format_readable(self, result) -> str:
        """Format ComplianceAnalysisResult as human-readable text.

        Args:
            result: ComplianceAnalysisResult

        Returns:
            Formatted analysis text
        """
        lines = []
        score_pct = int(result.overall_score * 100)

        lines.append("COMPLIANCE ANALYSIS SUMMARY")
        lines.append(f"Overall Alignment Score: {score_pct}%")
        lines.append(f"Conditions Analyzed: {len(result.conditions)}")
        lines.append(f"Guidelines Searched: {result.guidelines_searched}")

        if not result.has_sufficient_data:
            lines.append("")
            lines.append("INSUFFICIENT DATA")
            lines.append(
                "Not enough information available to perform a complete "
                "compliance analysis. Upload relevant clinical guidelines."
            )
            lines.append("")
            lines.append(f"Note: {result.disclaimer}")
            return "\n".join(lines)

        lines.append("")

        # Condition summary strip
        cond_parts = []
        for cc in result.conditions:
            icon = {'ALIGNED': '\u2713', 'GAP': '\u2717', 'REVIEW': '?'}.get(
                cc.status, '?'
            )
            cond_parts.append(f"{cc.condition} {icon}")
        lines.append("Conditions:  " + "  |  ".join(cond_parts))
        lines.append("")

        # Detailed findings per condition
        lines.append("DETAILED FINDINGS")
        lines.append("")

        for cc in result.conditions:
            status_label = {
                'ALIGNED': 'ALIGNED',
                'GAP': 'GAP IDENTIFIED',
                'REVIEW': 'NEEDS REVIEW',
            }.get(cc.status, cc.status)

            lines.append(f"--- {cc.condition} [{status_label}] ---")
            lines.append(
                f"Score: {int(cc.score * 100)}% | "
                f"Guidelines matched: {cc.guidelines_matched}"
            )
            lines.append("")

            for f in cc.findings:
                status = f.status if hasattr(f, 'status') else f['status']
                finding = f.finding if hasattr(f, 'finding') else f['finding']
                ref = (
                    f.guideline_reference
                    if hasattr(f, 'guideline_reference')
                    else f['guideline_reference']
                )
                rec = (
                    f.recommendation
                    if hasattr(f, 'recommendation')
                    else f['recommendation']
                )
                verified = (
                    f.citation_verified
                    if hasattr(f, 'citation_verified')
                    else f.get('citation_verified', False)
                )

                icon = {'ALIGNED': '\u2713', 'GAP': '\u2717', 'REVIEW': '?'}.get(
                    status, '?'
                )
                verify_mark = '\u2713' if verified else '?'

                lines.append(f"  [{status}] {finding}")
                if ref:
                    lines.append(f"    Guideline [{verify_mark}]: {ref}")
                if rec:
                    lines.append(f"    Recommendation: {rec}")
                lines.append("")

        lines.append(f"Note: {result.disclaimer}")

        return "\n".join(lines)

    def _build_insufficient_data_response(
        self, start_time: float, message: str
    ) -> AgentResponse:
        """Build a response for when there's insufficient data.

        Args:
            start_time: Start time for processing duration
            message: Explanation message

        Returns:
            AgentResponse with has_sufficient_data=False
        """
        processing_time_ms = (time.time() - start_time) * 1000

        metadata = {
            'guidelines_checked': 0,
            'compliant_count': 0,
            'gap_count': 0,
            'warning_count': 0,
            'overall_score': 0.0,
            'has_sufficient_data': False,
            'conditions': [],
            'conditions_count': 0,
            'disclaimer': DISCLAIMER,
            'specialties_analyzed': [],
            'sources_checked': [],
            'model_used': self.config.model,
            'processing_time_ms': processing_time_ms,
            'guidelines_available': GUIDELINES_AVAILABLE,
        }

        return AgentResponse(
            result=message,
            thoughts="Insufficient data for compliance analysis.",
            success=True,
            metadata=metadata,
        )

    def check_compliance(
        self,
        soap_note: str,
        specialties: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
    ) -> AgentResponse:
        """Convenience method to check compliance for a SOAP note.

        Args:
            soap_note: The SOAP note to analyze
            specialties: Optional list of specialties to focus on
            sources: Optional list of guideline sources to prioritize

        Returns:
            AgentResponse with compliance analysis
        """
        task = AgentTask(
            task_description="Check SOAP note compliance with clinical guidelines",
            input_data={
                "soap_note": soap_note,
                "specialties": specialties,
                "sources": sources,
            }
        )

        return self.execute(task)

    def get_compliance_summary(self, response: AgentResponse) -> str:
        """Get a concise compliance summary from a response.

        Args:
            response: The compliance analysis response

        Returns:
            Concise summary string for display
        """
        if not response.success:
            return f"Compliance check failed: {response.error}"

        metadata = response.metadata or {}

        if not metadata.get('has_sufficient_data', False):
            return "Insufficient data for compliance analysis."

        score = metadata.get('overall_score', 0)
        aligned = metadata.get('compliant_count', 0)
        gaps = metadata.get('gap_count', 0)
        reviews = metadata.get('warning_count', 0)
        conditions_count = metadata.get('conditions_count', 0)

        score_percent = int(score * 100)

        summary_parts = [f"Alignment: {score_percent}%"]

        if conditions_count > 0:
            summary_parts.append(f"{conditions_count} conditions")
        if aligned > 0:
            summary_parts.append(f"{aligned} aligned")
        if gaps > 0:
            summary_parts.append(f"{gaps} gaps")
        if reviews > 0:
            summary_parts.append(f"{reviews} review")

        return " | ".join(summary_parts)
