"""
Compliance Agent for Clinical Guidelines

Analyzes SOAP notes against clinical guidelines for compliance checking.
Retrieves relevant guidelines from the separate guidelines database and
evaluates adherence to evidence-based recommendations.

Architecture Note:
    This agent uses the GuidelinesRetriever which ONLY accesses the
    separate guidelines database, NOT patient documents.
"""

import re
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse
from utils.structured_logging import get_logger

# Try to import guidelines retriever
try:
    from src.rag.guidelines_retriever import get_guidelines_retriever
    GUIDELINES_AVAILABLE = True
except ImportError:
    GUIDELINES_AVAILABLE = False

# Try to import guidelines models
try:
    from src.rag.guidelines_models import (
        GuidelineReference,
        ComplianceItem,
        ComplianceResult,
        ComplianceStatus,
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = get_logger(__name__)


class ComplianceAgent(BaseAgent):
    """Agent specialized in clinical guidelines compliance analysis."""

    DEFAULT_CONFIG = AgentConfig(
        name="ComplianceAgent",
        description="Analyzes SOAP notes for adherence to clinical guidelines",
        system_prompt="""You are a clinical compliance analyst specializing in evidence-based medicine.

Your role is to:
1. Analyze SOAP notes for adherence to clinical guidelines
2. Identify compliance gaps and areas for improvement
3. Provide specific guideline references with citations
4. Rate compliance status as: COMPLIANT, GAP, or WARNING

Guidelines for analysis:
- Focus on actionable recommendations from evidence-based guidelines
- Consider the patient's specific conditions and treatments
- Reference specific guideline sources (e.g., AHA, ADA, GOLD)
- Include recommendation class (I, IIa, IIb, III) and evidence level (A, B, C)
- Be constructive - suggest improvements, not just identify problems
- Consider clinical context - some deviations may be justified

Format your response as:

1. COMPLIANCE SUMMARY
   - Overall assessment of guideline adherence
   - Key areas of compliance
   - Key gaps identified

2. DETAILED COMPLIANCE FINDINGS
   For each relevant guideline, provide:
   [STATUS] [GUIDELINE] - [FINDING]
   - Status: COMPLIANT, GAP, or WARNING
   - Guideline: Source, title, section
   - Finding: Specific observation
   - Recommendation: What should be done
   - Evidence: Class/Level (e.g., Class I, Level A)

3. IMPROVEMENT OPPORTUNITIES
   - Prioritized list of actions to improve compliance
   - Specific guideline references for each

Example finding format:
[GAP] AHA/ACC Hypertension 2024, Section 8.2 - ACE inhibitor not documented for diabetic patient with HTN
- Recommendation: Consider lisinopril or similar ACE-I per AHA/ACC Class I, Level A
- Note: Unless contraindicated (e.g., angioedema history, pregnancy)

[COMPLIANT] ADA Standards 2024 - Metformin first-line therapy appropriately initiated
- Evidence: Class I, Level A recommendation

[WARNING] GOLD 2024 - COPD patient on ICS without documented exacerbation history
- Recommendation: Review ICS indication per GOLD guidelines
- Note: ICS indicated for patients with blood eos >= 300 or >= 2 exacerbations/year""",
        model="gpt-4",
        temperature=0.1,  # Low temperature for consistent analysis
        max_tokens=1500
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

        Args:
            task: Task containing:
                - soap_note: The SOAP note to analyze
                - specialties: Optional list of specialties to focus on
                - sources: Optional list of guideline sources to prioritize
                - max_guidelines: Maximum guidelines to check (default 10)

        Returns:
            AgentResponse with compliance analysis and structured results
        """
        start_time = time.time()

        try:
            # Extract input data
            soap_note = task.input_data.get('soap_note', '')
            specialties = task.input_data.get('specialties', None)
            sources = task.input_data.get('sources', None)
            max_guidelines = task.input_data.get('max_guidelines', 10)

            if not soap_note:
                return AgentResponse(
                    result="",
                    success=False,
                    error="No SOAP note provided for compliance analysis"
                )

            # Get relevant guidelines
            guidelines_context = ""
            guidelines_checked = 0

            if GUIDELINES_AVAILABLE:
                try:
                    retriever = get_guidelines_retriever()
                    guidelines_context = retriever.get_guideline_context(
                        soap_note=soap_note,
                        max_guidelines=max_guidelines,
                    )
                    # Count guidelines found
                    guidelines_checked = len(re.findall(r'## Guideline \d+', guidelines_context))
                except Exception as e:
                    logger.warning(f"Failed to retrieve guidelines: {e}")
                    guidelines_context = "No guidelines available for comparison."
            else:
                guidelines_context = "Guidelines retrieval system not configured."

            # Build the compliance analysis prompt
            prompt = self._build_compliance_prompt(
                soap_note=soap_note,
                guidelines_context=guidelines_context,
                additional_context=task.context
            )

            # Call AI for compliance analysis
            analysis = self._call_ai(prompt)

            # Extract structured compliance data
            structured_data = self._extract_compliance_data(analysis)

            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000

            # Build response metadata
            metadata = {
                'guidelines_checked': guidelines_checked,
                'compliant_count': structured_data.get('compliant_count', 0),
                'gap_count': structured_data.get('gap_count', 0),
                'warning_count': structured_data.get('warning_count', 0),
                'overall_score': structured_data.get('overall_score', 0.0),
                'compliance_items': structured_data.get('items', []),
                'specialties_analyzed': specialties or ['general'],
                'sources_checked': sources or [],
                'model_used': self.config.model,
                'processing_time_ms': processing_time_ms,
                'guidelines_available': GUIDELINES_AVAILABLE,
            }

            response = AgentResponse(
                result=analysis,
                thoughts=f"Analyzed SOAP note against {guidelines_checked} guidelines. "
                         f"Found {metadata['compliant_count']} compliant, "
                         f"{metadata['gap_count']} gaps, {metadata['warning_count']} warnings.",
                success=True,
                metadata=metadata
            )

            # Add to history
            self.add_to_history(task, response)

            return response

        except Exception as e:
            logger.error(f"Error in compliance analysis: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )

    def _build_compliance_prompt(
        self,
        soap_note: str,
        guidelines_context: str,
        additional_context: Optional[str] = None
    ) -> str:
        """Build the prompt for compliance analysis.

        Args:
            soap_note: The SOAP note to analyze
            guidelines_context: Retrieved guidelines context
            additional_context: Optional additional context

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        prompt_parts.append("Analyze the following SOAP note for adherence to clinical guidelines.\n")

        if additional_context:
            prompt_parts.append(f"Additional Context: {additional_context}\n")

        prompt_parts.append(f"\n{guidelines_context}\n")

        prompt_parts.append(f"\n# SOAP Note to Analyze\n\n{soap_note}\n")

        prompt_parts.append("\n---\n")
        prompt_parts.append("Provide your compliance analysis following the specified format.")
        prompt_parts.append("Be specific about which guidelines apply and cite sources accurately.")

        return "\n".join(prompt_parts)

    def _extract_compliance_data(self, analysis: str) -> Dict[str, Any]:
        """Extract structured compliance data from analysis text.

        Args:
            analysis: The compliance analysis text

        Returns:
            Dictionary with structured compliance data
        """
        data = {
            'items': [],
            'compliant_count': 0,
            'gap_count': 0,
            'warning_count': 0,
            'overall_score': 0.0,
        }

        # Count status occurrences
        data['compliant_count'] = len(re.findall(r'\[COMPLIANT\]', analysis, re.IGNORECASE))
        data['gap_count'] = len(re.findall(r'\[GAP\]', analysis, re.IGNORECASE))
        data['warning_count'] = len(re.findall(r'\[WARNING\]', analysis, re.IGNORECASE))

        total_items = data['compliant_count'] + data['gap_count'] + data['warning_count']

        # Calculate overall score (compliant / total, with warnings counting as 0.5)
        if total_items > 0:
            score = (data['compliant_count'] + data['warning_count'] * 0.5) / total_items
            data['overall_score'] = round(score, 2)
        else:
            data['overall_score'] = 1.0  # No issues found = fully compliant

        # Extract individual compliance items
        items = self._extract_compliance_items(analysis)
        data['items'] = items

        return data

    def _extract_compliance_items(self, analysis: str) -> List[Dict[str, Any]]:
        """Extract individual compliance items from analysis.

        Args:
            analysis: The compliance analysis text

        Returns:
            List of compliance item dictionaries
        """
        items = []

        # Pattern to match compliance findings
        # e.g., [GAP] AHA/ACC Hypertension 2024, Section 8.2 - ACE inhibitor not documented
        pattern = r'\[(COMPLIANT|GAP|WARNING)\]\s*([^-\n]+)\s*-\s*([^\n]+)'

        matches = re.findall(pattern, analysis, re.IGNORECASE)

        for match in matches:
            status, guideline, finding = match
            status = status.upper()

            # Try to extract recommendation and evidence level
            recommendation = ""
            evidence = ""

            # Look for recommendation on following lines
            guideline_pos = analysis.find(finding)
            if guideline_pos != -1:
                following_text = analysis[guideline_pos:guideline_pos + 500]
                rec_match = re.search(r'Recommendation:\s*([^\n]+)', following_text, re.IGNORECASE)
                if rec_match:
                    recommendation = rec_match.group(1).strip()

                ev_match = re.search(r'(?:Evidence|Class):\s*([^\n]+)', following_text, re.IGNORECASE)
                if ev_match:
                    evidence = ev_match.group(1).strip()

            # Parse guideline reference
            guideline_parts = guideline.strip().split(',')
            source = guideline_parts[0].strip() if guideline_parts else ""
            section = guideline_parts[1].strip() if len(guideline_parts) > 1 else ""

            items.append({
                'status': status,
                'guideline_source': source,
                'guideline_section': section,
                'finding': finding.strip(),
                'recommendation': recommendation,
                'evidence': evidence,
            })

        return items

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
        score = metadata.get('overall_score', 0)
        compliant = metadata.get('compliant_count', 0)
        gaps = metadata.get('gap_count', 0)
        warnings = metadata.get('warning_count', 0)
        total = compliant + gaps + warnings

        score_percent = int(score * 100)

        if total == 0:
            return "No applicable guidelines found for this SOAP note."

        summary_parts = [f"Compliance Score: {score_percent}%"]

        if compliant > 0:
            summary_parts.append(f"{compliant} compliant")
        if gaps > 0:
            summary_parts.append(f"{gaps} gaps")
        if warnings > 0:
            summary_parts.append(f"{warnings} warnings")

        return " | ".join(summary_parts)
