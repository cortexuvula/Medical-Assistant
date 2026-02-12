"""
Analysis Panel Formatter

Provides rich text formatting for medication and differential diagnosis panels
with color-coded severity indicators and structured sections.
"""

import tkinter as tk
import re
from typing import Dict, Optional
from dataclasses import dataclass
from utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class SeverityConfig:
    """Configuration for severity level styling."""
    background: str
    foreground: str
    font_weight: str = "bold"


class AnalysisPanelFormatter:
    """Formats analysis panel content with color-coded severity indicators."""

    # Severity color configurations (matching MedicationResultsDialog)
    SEVERITY_COLORS = {
        "contraindicated": SeverityConfig("#dc3545", "white"),      # Red
        "major": SeverityConfig("#fd7e14", "black"),                # Orange
        "moderate": SeverityConfig("#ffc107", "black"),             # Yellow
        "minor": SeverityConfig("#28a745", "white"),                # Green
        "high": SeverityConfig("#dc3545", "white"),                 # Red (for diagnosis likelihood)
        "medium": SeverityConfig("#fd7e14", "black"),               # Orange
        "low": SeverityConfig("#6c757d", "white"),                  # Gray
    }

    # Special warning colors
    WARNING_COLORS = {
        "allergy": SeverityConfig("#dc3545", "white"),              # Red
        "renal": SeverityConfig("#17a2b8", "white"),                # Teal
        "hepatic": SeverityConfig("#6f42c1", "white"),              # Purple
        "red_flag": SeverityConfig("#dc3545", "white"),             # Red
        "general": SeverityConfig("#fd7e14", "black"),              # Orange
    }

    def __init__(self, text_widget: tk.Text):
        """Initialize formatter with target text widget.

        Args:
            text_widget: The tk.Text widget to format
        """
        self.widget = text_widget
        self._configure_tags()

    def _configure_tags(self) -> None:
        """Configure text tags for styling."""
        # Get font family - try to use system font
        font_family = "Segoe UI"

        # Section headers
        self.widget.tag_configure(
            "header",
            font=(font_family, 10, "bold"),
            spacing1=5,
            spacing3=3
        )
        self.widget.tag_configure(
            "summary",
            font=(font_family, 9, "bold"),
            foreground="#0d6efd"  # Bootstrap primary blue
        )
        self.widget.tag_configure(
            "separator",
            font=(font_family, 8),
            foreground="#6c757d"
        )

        # Severity tags with backgrounds
        for name, config in self.SEVERITY_COLORS.items():
            self.widget.tag_configure(
                f"severity_{name}",
                background=config.background,
                foreground=config.foreground,
                font=(font_family, 9, config.font_weight),
                spacing1=2,
                spacing3=2
            )

        # Warning tags
        for name, config in self.WARNING_COLORS.items():
            self.widget.tag_configure(
                f"warning_{name}",
                background=config.background,
                foreground=config.foreground,
                font=(font_family, 9, config.font_weight),
                spacing1=2,
                spacing3=2
            )

        # Standard formatting
        self.widget.tag_configure("bullet", font=(font_family, 9))
        self.widget.tag_configure(
            "medication_name",
            font=(font_family, 9, "bold")
        )
        self.widget.tag_configure("normal", font=(font_family, 9))
        self.widget.tag_configure(
            "detail",
            font=(font_family, 8),
            foreground="#6c757d"
        )
        self.widget.tag_configure(
            "recommendation",
            font=(font_family, 9),
            foreground="#198754"  # Green for recommendations
        )

    def format_medication_panel(
        self,
        result: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Format medication analysis for the panel.

        Args:
            result: The analysis result text (string or dict)
            metadata: Optional metadata with counts and flags
        """
        self.widget.config(state='normal')
        self.widget.delete('1.0', 'end')

        # Handle dict result
        if isinstance(result, dict):
            result = self._dict_to_text(result, 'medication')

        # Insert summary header
        if metadata:
            self._insert_medication_summary(metadata)

        # Parse and format the result
        self._format_medication_content(result)

        self.widget.config(state='disabled')

    def format_diagnostic_panel(
        self,
        result: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Format diagnostic analysis for the panel.

        Args:
            result: The analysis result text (string or dict)
            metadata: Optional metadata with counts and flags
        """
        self.widget.config(state='normal')
        self.widget.delete('1.0', 'end')

        # Handle dict result
        if isinstance(result, dict):
            result = self._dict_to_text(result, 'diagnostic')

        # Insert summary header
        if metadata:
            self._insert_diagnostic_summary(metadata)

        # Parse and format the result
        self._format_diagnostic_content(result)

        self.widget.config(state='disabled')

    def _dict_to_text(self, result: dict, panel_type: str) -> str:
        """Convert dict result to formatted text.

        Args:
            result: Dictionary result from agent
            panel_type: 'medication' or 'diagnostic'

        Returns:
            Formatted text string
        """
        lines = []

        if panel_type == 'medication':
            # Handle medication-specific dict structure
            if 'medications' in result:
                lines.append("MEDICATIONS FOUND:")
                for med in result['medications']:
                    if isinstance(med, dict):
                        name = med.get('name', 'Unknown')
                        dose = med.get('dose', '')
                        freq = med.get('frequency', '')
                        lines.append(f"  * {name} {dose} {freq}".strip())
                    else:
                        lines.append(f"  * {med}")
                lines.append("")

            if 'interactions' in result:
                lines.append("INTERACTIONS:")
                for interaction in result['interactions']:
                    if isinstance(interaction, dict):
                        severity = interaction.get('severity', 'Unknown')
                        desc = interaction.get('description', str(interaction))
                        lines.append(f"  [{severity.upper()}] {desc}")
                    else:
                        lines.append(f"  * {interaction}")
                lines.append("")

            if 'warnings' in result:
                lines.append("WARNINGS:")
                for warning in result['warnings']:
                    lines.append(f"  * {warning}")
                lines.append("")

            if 'recommendations' in result:
                lines.append("RECOMMENDATIONS:")
                for i, rec in enumerate(result['recommendations'], 1):
                    lines.append(f"  {i}. {rec}")

        else:  # diagnostic
            if 'differentials' in result:
                lines.append("DIFFERENTIAL DIAGNOSES:")
                for diff in result['differentials']:
                    if isinstance(diff, dict):
                        diagnosis = diff.get('diagnosis', 'Unknown')
                        confidence = diff.get('confidence', '')
                        if confidence:
                            lines.append(f"  * [{confidence}] {diagnosis}")
                        else:
                            lines.append(f"  * {diagnosis}")
                    else:
                        lines.append(f"  * {diff}")
                lines.append("")

            if 'red_flags' in result:
                lines.append("RED FLAGS:")
                for flag in result['red_flags']:
                    lines.append(f"  * {flag}")
                lines.append("")

            if 'investigations' in result:
                lines.append("RECOMMENDED INVESTIGATIONS:")
                for inv in result['investigations']:
                    lines.append(f"  * {inv}")

        return "\n".join(lines) if lines else str(result)

    def _insert_medication_summary(self, metadata: Dict) -> None:
        """Insert summary metrics for medication analysis.

        Args:
            metadata: Dictionary with medication analysis metadata
        """
        med_count = metadata.get('medication_count', 0)
        interaction_count = metadata.get('interaction_count', 0)
        has_major = metadata.get('has_major_interaction', False)
        has_warnings = metadata.get('has_warnings', False)

        summary_parts = []
        if med_count > 0:
            summary_parts.append(f"Meds: {med_count}")
        if interaction_count > 0:
            severity_indicator = " (!)" if has_major else ""
            summary_parts.append(f"Interactions: {interaction_count}{severity_indicator}")
        if has_warnings:
            summary_parts.append("WARNINGS")

        if summary_parts:
            summary_text = " | ".join(summary_parts) + "\n"
            self.widget.insert('end', summary_text, "summary")
            self.widget.insert('end', "-" * 45 + "\n", "separator")

    def _insert_diagnostic_summary(self, metadata: Dict) -> None:
        """Insert summary metrics for diagnostic analysis.

        Args:
            metadata: Dictionary with diagnostic analysis metadata
        """
        diff_count = metadata.get('differential_count', 0)
        has_red_flags = metadata.get('has_red_flags', False)
        top_confidence = metadata.get('top_confidence')

        summary_parts = []
        if diff_count > 0:
            summary_parts.append(f"Differentials: {diff_count}")
        if top_confidence:
            summary_parts.append(f"Top: {int(top_confidence * 100)}%")
        if has_red_flags:
            summary_parts.append("RED FLAGS")

        if summary_parts:
            summary_text = " | ".join(summary_parts) + "\n"
            self.widget.insert('end', summary_text, "summary")
            self.widget.insert('end', "-" * 45 + "\n", "separator")

    def _format_medication_content(self, text: str) -> None:
        """Parse and format medication analysis content.

        Args:
            text: The medication analysis text to format
        """
        if not text:
            self.widget.insert('end', "No medication information found.\n", "normal")
            return

        lines = text.split('\n')

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                self.widget.insert('end', '\n')
                continue

            # Detect section headers
            if self._is_section_header(line_stripped):
                self.widget.insert('end', line_stripped + '\n', "header")
                continue

            # Check for severity indicators in line
            severity = self._detect_severity(line_stripped)
            if severity:
                self.widget.insert('end', line_stripped + '\n', f"severity_{severity}")
                continue

            # Check for warnings
            if self._is_warning_line(line_stripped):
                warning_type = self._detect_warning_type(line_stripped)
                self.widget.insert('end', line_stripped + '\n', f"warning_{warning_type}")
                continue

            # Check for recommendations (numbered items)
            if self._is_recommendation(line_stripped):
                self.widget.insert('end', line_stripped + '\n', "recommendation")
                continue

            # Bullet points
            if line_stripped.startswith(('*', '-', '•')):
                self.widget.insert('end', line_stripped + '\n', "bullet")
                continue

            # Default
            self.widget.insert('end', line_stripped + '\n', "normal")

    def _format_diagnostic_content(self, text: str) -> None:
        """Parse and format diagnostic analysis content.

        Args:
            text: The diagnostic analysis text to format
        """
        if not text:
            self.widget.insert('end', "No diagnostic information found.\n", "normal")
            return

        lines = text.split('\n')

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                self.widget.insert('end', '\n')
                continue

            # Section headers
            if self._is_section_header(line_stripped):
                self.widget.insert('end', line_stripped + '\n', "header")
                continue

            # Red flags with warning symbol
            if self._is_red_flag(line_stripped):
                self.widget.insert('end', line_stripped + '\n', "warning_red_flag")
                continue

            # Confidence levels in differential diagnoses
            confidence = self._detect_confidence_level(line_stripped)
            if confidence:
                self.widget.insert('end', line_stripped + '\n', f"severity_{confidence}")
                continue

            # Recommendations
            if self._is_recommendation(line_stripped):
                self.widget.insert('end', line_stripped + '\n', "recommendation")
                continue

            # Bullet points
            if line_stripped.startswith(('*', '-', '•')):
                self.widget.insert('end', line_stripped + '\n', "bullet")
                continue

            # Default
            self.widget.insert('end', line_stripped + '\n', "normal")

    def _is_section_header(self, line: str) -> bool:
        """Check if line is a section header.

        Args:
            line: The line to check

        Returns:
            True if line is a header
        """
        headers = [
            'MEDICATIONS', 'MEDICATION', 'MEDS',
            'INTERACTIONS', 'INTERACTION', 'DRUG INTERACTION',
            'WARNINGS', 'WARNING', 'ALERTS', 'ALERT',
            'RECOMMENDATIONS', 'RECOMMENDATION',
            'CLINICAL SUMMARY', 'SUMMARY',
            'DIFFERENTIAL', 'DIAGNOSES', 'DIAGNOSIS',
            'RED FLAGS', 'RED FLAG',
            'INVESTIGATIONS', 'INVESTIGATION',
            'WORKUP', 'TESTS', 'MONITORING'
        ]
        upper = line.upper()
        # Check for header patterns
        if line.endswith(':') and any(h in upper for h in headers):
            return True
        # Check for all-caps headers
        if line.isupper() and len(line) < 50 and any(h in upper for h in headers):
            return True
        return False

    def _detect_severity(self, line: str) -> Optional[str]:
        """Detect drug interaction severity in line.

        Args:
            line: The line to check

        Returns:
            Severity level string or None
        """
        lower = line.lower()

        # Check for contraindicated
        if any(term in lower for term in [
            'contraindicated', 'do not use', 'avoid combination',
            'never use together', 'absolute contraindication'
        ]):
            return 'contraindicated'

        # Check for major severity
        if any(term in lower for term in ['[major]', 'severity: major', 'major interaction']):
            return 'major'
        if 'major' in lower and any(term in lower for term in ['interaction', 'severity', 'risk']):
            return 'major'

        # Check for moderate severity
        if any(term in lower for term in ['[moderate]', 'severity: moderate', 'moderate interaction']):
            return 'moderate'
        if 'moderate' in lower and any(term in lower for term in ['interaction', 'severity', 'risk']):
            return 'moderate'

        # Check for minor severity
        if any(term in lower for term in ['[minor]', 'severity: minor', 'minor interaction']):
            return 'minor'
        if 'minor' in lower and any(term in lower for term in ['interaction', 'severity', 'risk']):
            return 'minor'

        return None

    def _detect_confidence_level(self, line: str) -> Optional[str]:
        """Detect diagnosis confidence level in line.

        Args:
            line: The line to check

        Returns:
            Confidence level string or None
        """
        # Look for percentage patterns
        match = re.search(r'\[?(\d+)\s*%\]?', line)
        if match:
            pct = int(match.group(1))
            if pct >= 70:
                return 'high'
            elif pct >= 40:
                return 'medium'
            else:
                return 'low'

        # Look for bracket patterns [HIGH], [MEDIUM], [LOW]
        upper = line.upper()
        if '[HIGH]' in upper or '[LIKELY]' in upper:
            return 'high'
        if '[MEDIUM]' in upper or '[MODERATE]' in upper or '[POSSIBLE]' in upper:
            return 'medium'
        if '[LOW]' in upper or '[UNLIKELY]' in upper:
            return 'low'

        # Look for text confidence levels
        lower = line.lower()
        if ('high' in lower or 'likely' in lower) and 'confidence' in lower:
            return 'high'
        if ('medium' in lower or 'moderate' in lower) and ('confidence' in lower or 'probability' in lower):
            return 'medium'
        if 'low' in lower and ('confidence' in lower or 'probability' in lower):
            return 'low'

        return None

    def _is_warning_line(self, line: str) -> bool:
        """Check if line contains a warning.

        Args:
            line: The line to check

        Returns:
            True if line is a warning
        """
        lower = line.lower()
        warning_terms = [
            'allergy', 'allergic', 'hypersensitivity',
            'renal', 'kidney', 'egfr', 'creatinine',
            'hepatic', 'liver', 'ast', 'alt',
            'caution', 'warning', 'alert',
            'monitor', 'check', 'careful'
        ]
        return any(term in lower for term in warning_terms)

    def _detect_warning_type(self, line: str) -> str:
        """Detect type of warning.

        Args:
            line: The line to check

        Returns:
            Warning type string
        """
        lower = line.lower()
        if any(term in lower for term in ['allergy', 'allergic', 'hypersensitivity']):
            return 'allergy'
        elif any(term in lower for term in ['renal', 'kidney', 'egfr', 'creatinine']):
            return 'renal'
        elif any(term in lower for term in ['hepatic', 'liver', 'ast', 'alt']):
            return 'hepatic'
        return 'general'

    def _is_red_flag(self, line: str) -> bool:
        """Check if line is a red flag warning.

        Args:
            line: The line to check

        Returns:
            True if line is a red flag
        """
        lower = line.lower()
        # Check for warning symbol
        if '*' in line or '!' in line:
            if any(term in lower for term in [
                'red flag', 'urgent', 'emergent', 'immediate',
                'critical', 'serious', 'severe', 'dangerous'
            ]):
                return True
        # Check for red flag header context
        if 'red flag' in lower:
            return True
        return False

    def format_compliance_panel(
        self,
        result: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Format compliance analysis for the panel.

        Displays a condition summary strip, score, and disclaimer.

        Args:
            result: The analysis result text (string or dict)
            metadata: Metadata with conditions, score, disclaimer
        """
        self.widget.config(state='normal')
        self.widget.delete('1.0', 'end')

        # Configure compliance-specific tags
        font_family = "Segoe UI"
        self.widget.tag_configure(
            "compliance_aligned",
            background="#28a745",
            foreground="white",
            font=(font_family, 9, "bold"),
            spacing1=2,
            spacing3=2,
        )
        self.widget.tag_configure(
            "compliance_gap",
            background="#fd7e14",
            foreground="black",
            font=(font_family, 9, "bold"),
            spacing1=2,
            spacing3=2,
        )
        self.widget.tag_configure(
            "compliance_review",
            background="#17a2b8",
            foreground="white",
            font=(font_family, 9, "bold"),
            spacing1=2,
            spacing3=2,
        )
        self.widget.tag_configure(
            "disclaimer",
            font=(font_family, 8, "italic"),
            foreground="#6c757d",
            spacing1=5,
        )
        self.widget.tag_configure(
            "score_text",
            font=(font_family, 9, "bold"),
            foreground="#0d6efd",
        )
        self.widget.tag_configure(
            "condition_strip",
            font=(font_family, 9),
            spacing1=3,
            spacing3=3,
        )

        if not metadata:
            # No metadata — just show plain text
            self.widget.insert('end', result, "normal")
            self.widget.config(state='disabled')
            return

        has_sufficient = metadata.get('has_sufficient_data', True)

        if not has_sufficient:
            self.widget.insert('end', "Insufficient data\n", "header")
            self.widget.insert('end', result + "\n", "normal")
            disclaimer = metadata.get('disclaimer', '')
            if disclaimer:
                self.widget.insert('end', f"\n{disclaimer}\n", "disclaimer")
            self.widget.config(state='disabled')
            return

        # Condition strip with inline status icons
        conditions = metadata.get('conditions', [])
        if conditions:
            parts = []
            for cond in conditions:
                name = cond.get('condition', 'Unknown')
                status = cond.get('status', 'REVIEW')
                icon = {
                    'ALIGNED': '\u2713', 'GAP': '\u2717', 'REVIEW': '?'
                }.get(status, '?')
                parts.append(f"{name} {icon}")

            strip_text = "Conditions:  " + "  |  ".join(parts) + "\n"

            # Insert each condition segment with appropriate tag
            self.widget.insert('end', "Conditions:  ", "condition_strip")
            for i, cond in enumerate(conditions):
                name = cond.get('condition', 'Unknown')
                status = cond.get('status', 'REVIEW')
                icon = {
                    'ALIGNED': '\u2713', 'GAP': '\u2717', 'REVIEW': '?'
                }.get(status, '?')
                tag = {
                    'ALIGNED': 'compliance_aligned',
                    'GAP': 'compliance_gap',
                    'REVIEW': 'compliance_review',
                }.get(status, 'normal')

                self.widget.insert('end', f" {name} {icon} ", tag)
                if i < len(conditions) - 1:
                    self.widget.insert('end', "  |  ", "condition_strip")
            self.widget.insert('end', "\n")

        # Score line
        overall_score = metadata.get('overall_score', 0.0)
        conditions_count = metadata.get('conditions_count', len(conditions))
        score_pct = int(overall_score * 100)
        self.widget.insert(
            'end',
            f"\nScore: {score_pct}% aligned  |  {conditions_count} conditions analyzed\n",
            "score_text",
        )
        self.widget.insert('end', "-" * 45 + "\n", "separator")

        # Insert the readable result text with formatting
        if isinstance(result, str) and result:
            self._format_compliance_content(result)

        # Disclaimer at bottom
        disclaimer = metadata.get('disclaimer', '')
        if disclaimer:
            self.widget.insert('end', f"\n{disclaimer}\n", "disclaimer")

        self.widget.config(state='disabled')

    def _format_compliance_content(self, text: str) -> None:
        """Parse and format compliance analysis content.

        Args:
            text: The compliance analysis text to format
        """
        if not text:
            return

        lines = text.split('\n')
        in_findings = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                self.widget.insert('end', '\n')
                continue

            # Skip the summary header lines (already displayed above)
            if stripped.startswith('COMPLIANCE ANALYSIS SUMMARY'):
                continue
            if stripped.startswith('Overall Alignment Score:'):
                continue
            if stripped.startswith('Conditions Analyzed:'):
                continue
            if stripped.startswith('Guidelines Searched:'):
                continue
            if stripped.startswith('Conditions:') and '\u2713' in stripped:
                continue
            if stripped.startswith('Note:') and 'AI-assisted' in stripped:
                continue

            # Section headers
            if stripped in ('DETAILED FINDINGS', 'INSUFFICIENT DATA'):
                self.widget.insert('end', stripped + '\n', "header")
                in_findings = True
                continue

            # Condition section headers
            if stripped.startswith('---') and stripped.endswith('---'):
                self.widget.insert('end', stripped + '\n', "header")
                continue

            # Score/guidelines line under condition header
            if stripped.startswith('Score:') and 'Guidelines matched:' in stripped:
                self.widget.insert('end', stripped + '\n', "summary")
                continue

            # Status findings
            if '[ALIGNED]' in stripped:
                self.widget.insert('end', stripped + '\n', "compliance_aligned")
                continue
            if '[GAP]' in stripped:
                self.widget.insert('end', stripped + '\n', "compliance_gap")
                continue
            if '[REVIEW]' in stripped:
                self.widget.insert('end', stripped + '\n', "compliance_review")
                continue

            # Guideline references
            if stripped.startswith('Guideline'):
                self.widget.insert('end', stripped + '\n', "detail")
                continue

            # Recommendations
            if stripped.startswith('Recommendation:'):
                self.widget.insert('end', stripped + '\n', "recommendation")
                continue

            # Default
            self.widget.insert('end', stripped + '\n', "normal")

    def _is_recommendation(self, line: str) -> bool:
        """Check if line is a recommendation.

        Args:
            line: The line to check

        Returns:
            True if line is a recommendation
        """
        # Numbered recommendations
        if re.match(r'^\s*\d+[.\)]\s+', line):
            lower = line.lower()
            rec_terms = [
                'recommend', 'suggest', 'consider', 'should',
                'monitor', 'follow', 'check', 'review', 'obtain',
                'order', 'refer', 'start', 'continue', 'discontinue'
            ]
            return any(term in lower for term in rec_terms)
        return False
