"""
Diagnostic Results Formatter Module

Provides text formatting and analysis display functionality.
"""

import re
from tkinter.constants import END
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import tkinter as tk


class FormatterMixin:
    """Mixin for formatting and displaying diagnostic analysis."""

    result_text: "tk.Text"

    def _format_analysis(self, analysis: str):
        """Format and display the analysis with appropriate styling."""
        # Configure tags for formatting
        self.result_text.tag_configure("section_header", font=("Segoe UI", 12, "bold"), spacing3=10)
        self.result_text.tag_configure("red_flag", foreground="red", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("diagnosis", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("icd_code", foreground="blue", font=("Segoe UI", 10, "italic"))
        self.result_text.tag_configure("confidence_high", foreground="green", font=("Segoe UI", 10, "bold"))
        self.result_text.tag_configure("confidence_medium", foreground="orange", font=("Segoe UI", 10, "bold"))
        self.result_text.tag_configure("confidence_low", foreground="gray", font=("Segoe UI", 10, "bold"))

        # Combined ICD pattern: ICD-10 (e.g., J18.9, K21.0) and ICD-9 (e.g., 486.0, 530.81)
        icd_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b|\b\d{3}\.\d{1,2}\b'
        # Confidence pattern
        confidence_pattern = r'\[(HIGH|MEDIUM|LOW)\]|\b(HIGH|MEDIUM|LOW)\s*(?:confidence|probability)?\b'

        # Insert the analysis
        lines = analysis.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                self.result_text.insert(END, "\n")
                continue

            # Format section headers
            if any(header in line for header in ["CLINICAL SUMMARY:", "DIFFERENTIAL DIAGNOSES:",
                                                 "RED FLAGS:", "RECOMMENDED INVESTIGATIONS:",
                                                 "CLINICAL PEARLS:"]):
                self.result_text.insert(END, line + "\n", "section_header")
            # Highlight red flags
            elif "RED FLAGS:" in analysis and self._is_in_section(line, "RED FLAGS:", lines):
                self.result_text.insert(END, line + "\n", "red_flag")
            # Format differential diagnoses
            elif self._is_in_section(line, "DIFFERENTIAL DIAGNOSES:", lines) and (line[0].isdigit() or line.startswith("-")):
                # Look for ICD codes (both ICD-10 and ICD-9 formats)
                has_icd = re.search(icd_pattern, line)
                has_confidence = re.search(confidence_pattern, line, re.IGNORECASE)

                if has_icd or has_confidence:
                    # Split line to highlight ICD codes and confidence levels
                    combined_pattern = f'({icd_pattern})|({confidence_pattern})'
                    parts = re.split(combined_pattern, line)
                    for part in parts:
                        if part is None:
                            continue
                        if re.match(icd_pattern, part):
                            self.result_text.insert(END, part, "icd_code")
                        elif re.match(r'\[?HIGH\]?', part, re.IGNORECASE):
                            self.result_text.insert(END, part, "confidence_high")
                        elif re.match(r'\[?MEDIUM\]?', part, re.IGNORECASE):
                            self.result_text.insert(END, part, "confidence_medium")
                        elif re.match(r'\[?LOW\]?', part, re.IGNORECASE):
                            self.result_text.insert(END, part, "confidence_low")
                        else:
                            self.result_text.insert(END, part, "diagnosis")
                    self.result_text.insert(END, "\n")
                else:
                    self.result_text.insert(END, line + "\n", "diagnosis")
            else:
                self.result_text.insert(END, line + "\n")

    def _is_in_section(self, line: str, section_header: str, all_lines: list) -> bool:
        """Check if a line belongs to a specific section."""
        # Simple heuristic: check if the section header appears before this line
        # and no other section header appears between them
        section_headers = ["CLINICAL SUMMARY:", "DIFFERENTIAL DIAGNOSES:",
                          "RED FLAGS:", "RECOMMENDED INVESTIGATIONS:", "CLINICAL PEARLS:"]

        in_section = False
        for check_line in all_lines:
            if section_header in check_line:
                in_section = True
            elif any(header in check_line for header in section_headers if header != section_header):
                in_section = False
            elif check_line.strip() == line:
                return in_section
        return False


__all__ = ["FormatterMixin"]
