"""
Medication Agent Prompt Builders

Mixin providing prompt construction methods for the MedicationAgent.
Extracted to keep the main agent file focused on execution logic.
"""

from typing import Optional, List, Dict, Any


class MedicationPromptMixin:
    """Prompt construction methods for medication analysis tasks."""

    def _build_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for medication extraction."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        prompt_parts.append("Extract all medications mentioned in the following clinical text.")
        prompt_parts.append("For each medication, identify:")
        prompt_parts.append("- Generic and brand names")
        prompt_parts.append("- Dosage and strength")
        prompt_parts.append("- Route of administration")
        prompt_parts.append("- Frequency")
        prompt_parts.append("- Duration or status (ongoing, discontinued, etc.)")
        prompt_parts.append("- Indication if mentioned\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Extracted Medications:")

        return "\n".join(prompt_parts)

    def _build_interaction_prompt(self, medications: List[str], context: Optional[str] = None) -> str:
        """Build prompt for interaction checking with priority classification."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        prompt_parts.append("Check for drug-drug interactions between the following medications:")
        for med in medications:
            prompt_parts.append(f"- {med}")

        prompt_parts.append("""

STRUCTURE YOUR RESPONSE BY PRIORITY LEVEL:

## \U0001f534 HIGH PRIORITY INTERACTIONS (Contraindicated/Major)
For each CONTRAINDICATED or MAJOR interaction:
- **Medications:** [Drug A] + [Drug B]
- **Risk:** [Specific clinical consequence, e.g., "Life-threatening bone marrow suppression"]
- **Mechanism:** [Brief explanation of why this occurs]
- **Action:** [STOP one medication / Contraindicated / Avoid combination]
- **Timeline:** [Immediate / Before next dose / Within 24 hours]

## \U0001f7e1 MODERATE PRIORITY INTERACTIONS
For each MODERATE interaction:
- **Medications:** [Drug A] + [Drug B]
- **Risk:** [Clinical concern]
- **Action:** [Monitor closely / Dose adjustment / Timing separation]
- **Monitoring:** [Specific labs/parameters and timing]

## \U0001f7e2 LOW PRIORITY INTERACTIONS (Minor)
For each MINOR interaction:
- **Medications:** [Drug A] + [Drug B]
- **Note:** [Brief clinical note]
- **Monitoring:** [If any needed]

## ACTIONABLE RECOMMENDATIONS
\u25a1 [Specific action items based on the interactions found]
\u25a1 [Labs to order with timing]
\u25a1 [Follow-up recommendations]

## PATIENT COUNSELING
Key points to discuss with patient about these drug interactions:
\u2022 [Important warnings in lay language]
\u2022 [Signs/symptoms to watch for]
\u2022 [When to seek immediate medical attention]

If no interactions are found at a priority level, state "None identified." """)

        return "\n".join(prompt_parts)

    def _build_prescription_prompt(
        self,
        medication: Dict[str, Any],
        patient_info: Dict[str, Any],
        indication: str,
        context: Optional[str] = None
    ) -> str:
        """Build prompt for prescription generation."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        prompt_parts.append("Generate prescription information for:")
        prompt_parts.append(f"Medication: {medication.get('name', 'Unknown')}")

        if indication:
            prompt_parts.append(f"Indication: {indication}")

        if patient_info:
            prompt_parts.append("\nPatient Information:")
            for key, value in patient_info.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt_parts.append("\nProvide complete prescription details including:")
        prompt_parts.append("- Exact dosing with units")
        prompt_parts.append("- Route of administration")
        prompt_parts.append("- Frequency and timing")
        prompt_parts.append("- Duration of treatment")
        prompt_parts.append("- Quantity to dispense")
        prompt_parts.append("- Number of refills")
        prompt_parts.append("- Important instructions")
        prompt_parts.append("- Warnings and precautions\n")
        prompt_parts.append("Prescription:")

        return "\n".join(prompt_parts)

    def _build_dosing_prompt(
        self,
        medication: Dict[str, Any],
        patient_factors: Dict[str, Any],
        context: Optional[str] = None
    ) -> str:
        """Build prompt for dosing validation with renal/hepatic adjustment tables."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        prompt_parts.append("Validate the following medication dosing:")
        prompt_parts.append(f"Medication: {medication.get('name', 'Unknown')}")
        prompt_parts.append(f"Dose: {medication.get('dose', 'Unknown')}")
        prompt_parts.append(f"Frequency: {medication.get('frequency', 'Unknown')}")

        if medication.get('indication'):
            prompt_parts.append(f"Indication: {medication.get('indication')}")

        if patient_factors:
            prompt_parts.append("\nPatient Factors:")
            for key, value in patient_factors.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt_parts.append("""

PROVIDE YOUR ASSESSMENT IN THE FOLLOWING STRUCTURE:

## DOSING ASSESSMENT
- **Current Dose:** [dose being evaluated]
- **Standard Range:** [typical dosing range for this indication]
- **Assessment:** \U0001f534 INAPPROPRIATE / \U0001f7e1 NEEDS ADJUSTMENT / \U0001f7e2 APPROPRIATE
- **Rationale:** [why this assessment]""")

        # Add renal dosing section if eGFR provided
        if patient_factors and patient_factors.get('egfr'):
            egfr = patient_factors.get('egfr')
            prompt_parts.append(f"""

## RENAL DOSE ADJUSTMENT (eGFR: {egfr} mL/min)
| Parameter | Value |
|-----------|-------|
| Current Dose | {medication.get('dose', 'Unknown')} |
| Recommended Dose | [adjusted dose for this GFR] |
| Adjustment Reason | [why adjustment needed] |
| Source | [FDA label / Lexicomp / Clinical guideline] |

**CKD Stage Classification:**
- eGFR <15: Stage 5 (ESRD)
- eGFR 15-29: Stage 4
- eGFR 30-44: Stage 3b
- eGFR 45-59: Stage 3a
- eGFR 60-89: Stage 2
- eGFR \u226590: Stage 1

Current patient: [identify CKD stage based on eGFR {egfr}]""")

        # Add hepatic dosing section if hepatic function provided
        if patient_factors and patient_factors.get('hepatic_function'):
            hepatic = patient_factors.get('hepatic_function')
            prompt_parts.append(f"""

## HEPATIC DOSE ADJUSTMENT ({hepatic})
| Parameter | Value |
|-----------|-------|
| Current Dose | {medication.get('dose', 'Unknown')} |
| Recommended Dose | [adjusted dose for this hepatic function] |
| Adjustment Reason | [why adjustment needed] |
| Source | [FDA label / Lexicomp / Clinical guideline] |

**Child-Pugh Classification:**
- Class A (5-6 points): Mild impairment
- Class B (7-9 points): Moderate impairment
- Class C (10-15 points): Severe impairment""")

        prompt_parts.append("""

## ACTIONABLE RECOMMENDATIONS
\u25a1 [Dose change to implement, if any]
\u25a1 [Labs to monitor with timing]
\u25a1 [Follow-up schedule]
\u25a1 [Documentation requirements]

## PATIENT COUNSELING POINTS
\u2022 [How to take the adjusted dose]
\u2022 [Signs of toxicity to watch for]
\u2022 [When to contact physician]

## MONITORING REQUIREMENTS
- What to monitor: [specific parameters]
- Frequency: [how often]
- Target values: [therapeutic ranges if applicable]

## SUMMARY
[Brief 1-2 sentence summary: Is dose appropriate? What action needed?]""")

        return "\n".join(prompt_parts)

    def _build_alternatives_prompt(
        self,
        current_medication: Dict[str, Any],
        reason: str,
        patient_factors: Dict[str, Any],
        context: Optional[str] = None
    ) -> str:
        """Build prompt for alternative suggestions."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        prompt_parts.append("Suggest alternative medications for:")
        prompt_parts.append(f"Current Medication: {current_medication.get('name', 'Unknown')}")
        prompt_parts.append(f"Reason for Change: {reason}")

        if patient_factors:
            prompt_parts.append("\nPatient Factors:")
            for key, value in patient_factors.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt_parts.append("""
Provide 3-5 suitable alternatives with the following structure for EACH alternative:

## Alternative [Number]: [Generic Name] ([Brand Name])

**Dosing:** [Recommended dose, frequency, route]

**Clinical Advantages:**
- [Specific advantage over current medication]
- [Efficacy considerations]

**Potential Disadvantages:**
- [Side effects, contraindications, monitoring requirements]

**Cost & Formulary:**
- Generic available: Yes/No
- Cost tier: $ (generic) / $$ (preferred brand) / $$$ (non-preferred) / $$$$ (specialty)
- Typical monthly cost range: [if known]

**Switching Instructions:**
- [How to transition from current medication]
- [Overlap period if needed]
- [Monitoring during switch]

**Evidence/Guideline Support:**
- [Cite relevant guidelines or evidence for this alternative]

---

ORDER ALTERNATIVES BY: Efficacy and safety first, then cost-effectiveness.
Highlight if any alternative is significantly more cost-effective with similar efficacy.
""")

        return "\n".join(prompt_parts)

    def _format_patient_context(self, patient_context: Dict[str, Any]) -> str:
        """Format patient context for inclusion in prompts."""
        if not patient_context:
            return ""

        parts = ["\nPATIENT FACTORS (IMPORTANT - Consider these in your analysis):"]

        if 'age' in patient_context:
            age = patient_context['age']
            parts.append(f"- Age: {age} years")
            if age < 12:
                parts.append("  \u26a0\ufe0f PEDIATRIC patient - use pediatric dosing")
            elif age >= 65:
                parts.append("  \u26a0\ufe0f GERIATRIC patient - consider reduced dosing, increased fall risk")

        if 'weight_kg' in patient_context:
            weight = patient_context['weight_kg']
            parts.append(f"- Weight: {weight} kg")
            if weight < 50:
                parts.append("  \u26a0\ufe0f Low body weight - may need dose reduction")

        if 'egfr' in patient_context:
            egfr = patient_context['egfr']
            parts.append(f"- eGFR: {egfr} mL/min")
            if egfr < 30:
                parts.append("  \u26a0\ufe0f SEVERE renal impairment (CKD Stage 4-5) - significant dose adjustments likely needed")
            elif egfr < 60:
                parts.append("  \u26a0\ufe0f MODERATE renal impairment (CKD Stage 3) - dose adjustments may be needed")
            elif egfr < 90:
                parts.append("  Note: Mild renal impairment (CKD Stage 2)")

        if 'hepatic_function' in patient_context:
            hepatic = patient_context['hepatic_function']
            parts.append(f"- Hepatic function: {hepatic}")
            if 'Child-Pugh C' in hepatic:
                parts.append("  \u26a0\ufe0f SEVERE hepatic impairment - many medications contraindicated")
            elif 'Child-Pugh B' in hepatic:
                parts.append("  \u26a0\ufe0f MODERATE hepatic impairment - significant dose reductions needed")
            elif 'Child-Pugh A' in hepatic:
                parts.append("  Note: Mild hepatic impairment - monitor closely")

        if 'allergies' in patient_context and patient_context['allergies']:
            allergies = patient_context['allergies']
            parts.append(f"- Known allergies: {', '.join(allergies)}")
            parts.append("  \u26a0\ufe0f CHECK for cross-reactivity with any recommended medications!")

        return "\n".join(parts)

    def _build_comprehensive_prompt(
        self,
        text: str,
        current_medications: List[str],
        context: Optional[str] = None,
        patient_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for comprehensive analysis with clinical decision support."""
        prompt_parts = []

        prompt_parts.append("Perform a comprehensive medication analysis with clinical decision support.\n")

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        # Add patient context prominently at the top
        if patient_context:
            patient_info = self._format_patient_context(patient_context)
            if patient_info:
                prompt_parts.append(patient_info)

        if text:
            prompt_parts.append(f"\nCLINICAL TEXT:\n{text}")

        if current_medications:
            prompt_parts.append("\nCURRENT MEDICATIONS:")
            for med in current_medications:
                prompt_parts.append(f"- {med}")

        # Enhanced output structure
        prompt_parts.append("""

PROVIDE YOUR ANALYSIS IN THE FOLLOWING STRUCTURE:

## \U0001f534 HIGH PRIORITY ISSUES (Immediate Action Required)
List any contraindicated combinations, dangerous interactions, or critical safety issues.
For each issue provide:
- Drug combination or medication involved
- Specific risk/consequence
- Required action with timeline
- Monitoring needed

## \U0001f7e1 MODERATE PRIORITY ISSUES (Address This Visit)
List significant interactions or concerns requiring attention during this visit.
For each issue provide:
- Issue description
- Risk level and clinical significance
- Recommended action
- Monitoring parameters

## \U0001f7e2 LOW PRIORITY/MONITORING
List minor interactions or items requiring ongoing monitoring only.
- Brief description and monitoring recommendation""")

        # Add renal dosing section if eGFR provided
        if patient_context and patient_context.get('egfr'):
            egfr = patient_context.get('egfr')
            prompt_parts.append(f"""

## RENAL DOSE ADJUSTMENTS (eGFR: {egfr} mL/min)
Provide a table of dose adjustments for renally-cleared medications:

| Medication | Standard Dose | Adjusted Dose | Reason | Source |
|------------|---------------|---------------|--------|--------|
| [med name] | [standard]    | [adjusted]    | [why]  | [FDA/Lexicomp/guideline] |

Flag any medications that should be DISCONTINUED at this GFR level.""")

        # Add hepatic dosing section if hepatic function provided
        if patient_context and patient_context.get('hepatic_function'):
            hepatic = patient_context.get('hepatic_function')
            prompt_parts.append(f"""

## HEPATIC DOSE ADJUSTMENTS ({hepatic})
Provide a table of dose adjustments for hepatically-metabolized medications:

| Medication | Standard Dose | Adjusted Dose | Reason | Source |
|------------|---------------|---------------|--------|--------|
| [med name] | [standard]    | [adjusted]    | [why]  | [FDA/Lexicomp/guideline] |

Flag any medications that are CONTRAINDICATED with this level of hepatic impairment.""")

        # Add TDM section
        prompt_parts.append("""

## THERAPEUTIC DRUG MONITORING (TDM)
If any narrow therapeutic index drugs are present (vancomycin, digoxin, lithium, warfarin, phenytoin, carbamazepine, valproic acid, aminoglycosides, theophylline, cyclosporine, tacrolimus, methotrexate, sirolimus), provide:

| Drug | Target Level | When to Check | Frequency | Guideline |
|------|--------------|---------------|-----------|-----------|
| [drug] | [target range] | [timing] | [how often] | [source] |

For each TDM drug, also include:
- Signs of toxicity to monitor
- Note if AUC-based vs trough-based monitoring preferred
- Renal adjustment impact on drug levels (if applicable)

If no TDM drugs are present, state "No narrow therapeutic index drugs requiring TDM."
""")

        # Add cost considerations section
        prompt_parts.append("""
## COST CONSIDERATIONS
For significant medications, provide cost-conscious prescribing information:
- Generic available: Yes/No
- Cost tier: $ (generic) / $$ (preferred brand) / $$$ (non-preferred) / $$$$ (specialty)
- Lower-cost therapeutic alternatives if applicable

Flag any brand-only or specialty/high-cost medications with potential alternatives.
""")

        # Add de-prescribing section conditionally
        if patient_context:
            age = patient_context.get('age', 0)
            med_count = len(current_medications) if current_medications else 0
            if age >= 65 or med_count > 5:
                prompt_parts.append("""
## DE-PRESCRIBING OPPORTUNITIES (Beers Criteria 2023)
This patient is eligible for de-prescribing review (age \u226565 or polypharmacy).

Review and identify:
1. **Potentially Inappropriate Medications (PIMs)** per AGS Beers Criteria 2023
2. **Medications without clear indication**
3. **Duplicate therapy**
4. **Candidates for safe discontinuation**

For each de-prescribing candidate, provide:
| Medication | Risk/Reason | Safer Alternative | Taper Instructions | Monitoring |
|------------|-------------|-------------------|-------------------|------------|
| [med name] | [concern - especially in elderly] | [if needed] | [or "can stop abruptly"] | [after discontinuation] |

Key Beers Criteria medications to evaluate:
- First-gen antihistamines (diphenhydramine, hydroxyzine)
- Benzodiazepines (diazepam, alprazolam, lorazepam)
- Tricyclic antidepressants (amitriptyline)
- Muscle relaxants (cyclobenzaprine)
- NSAIDs (long-term use)
- Opioids (meperidine)
""")

        prompt_parts.append("""

## ACTIONABLE RECOMMENDATIONS
Provide specific checkbox-style action items for the physician:
\u25a1 Labs to order (specify test and timing, e.g., "BMP in 7 days")
\u25a1 Follow-up schedule
\u25a1 Specialist consultations if needed
\u25a1 Medication changes to implement
\u25a1 Documentation requirements

## PATIENT COUNSELING POINTS
For each significant medication, provide patient-friendly counseling points:

**[Medication Name]:**
\u2022 How to take it (timing, with/without food)
\u2022 Common side effects to expect
\u2022 Red flag symptoms to report immediately (call doctor if...)
\u2022 Foods/drinks/activities to avoid
\u2022 Important drug interactions to remember

## MONITORING REQUIREMENTS
Summarize all required monitoring:
- What labs/tests to order
- When to order them (specific timing)
- What parameters to track
- Follow-up intervals

## EVIDENCE REFERENCES
Cite clinical guidelines and sources used in this analysis:
- Interaction sources: [FDA label, Lexicomp, UpToDate, specific guideline]
- Dose adjustment sources: [FDA label, renal dosing guidelines, etc.]
- TDM guidelines: [IDSA/ASHP, ACC/AHA, AAN, etc.]
- De-prescribing references: [AGS Beers Criteria 2023, STOPP/START criteria]

Format: "Per [Guideline Name Year]" or "Source: [reference]"
Include PMID for major interactions if known.

## SUMMARY
Brief 2-3 sentence summary of the most important findings and actions.""")

        return "\n".join(prompt_parts)
