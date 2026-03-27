"""
Medication agent for analyzing medications, checking interactions, and managing prescriptions.
"""

import re
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from .base import BaseAgent
from .medication_prompts import MedicationPromptMixin
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = get_logger(__name__)


# Therapeutic Drug Monitoring (TDM) reference data
TDM_DRUGS = {
    "vancomycin": {
        "target": "AUC 400-600 or trough 15-20 mcg/mL",
        "timing": "Before 4th dose",
        "guideline": "IDSA/ASHP 2020"
    },
    "digoxin": {
        "target": "0.5-2.0 ng/mL",
        "timing": "6-8h post-dose",
        "guideline": "ACC/AHA"
    },
    "lithium": {
        "target": "0.6-1.2 mEq/L",
        "timing": "12h post-dose",
        "guideline": "APA"
    },
    "warfarin": {
        "target": "INR 2-3 (most indications)",
        "timing": "Daily until stable",
        "guideline": "CHEST"
    },
    "phenytoin": {
        "target": "10-20 mcg/mL (total)",
        "timing": "Trough level",
        "guideline": "AAN"
    },
    "carbamazepine": {
        "target": "4-12 mcg/mL",
        "timing": "Trough level",
        "guideline": "AAN"
    },
    "valproic_acid": {
        "target": "50-100 mcg/mL",
        "timing": "Trough level",
        "guideline": "AAN"
    },
    "aminoglycosides": {
        "target": "Peak/trough varies by indication",
        "timing": "30min post & pre-dose",
        "guideline": "IDSA"
    },
    "theophylline": {
        "target": "5-15 mcg/mL",
        "timing": "Trough level",
        "guideline": "GINA"
    },
    "cyclosporine": {
        "target": "Indication-specific (100-400 ng/mL)",
        "timing": "C0 or C2",
        "guideline": "Transplant guidelines"
    },
    "tacrolimus": {
        "target": "Indication-specific (5-20 ng/mL)",
        "timing": "Trough (C0)",
        "guideline": "Transplant guidelines"
    },
    "methotrexate": {
        "target": "<0.1 μmol/L at 72h (high-dose)",
        "timing": "24h, 48h, 72h post-dose",
        "guideline": "Oncology protocols"
    },
    "sirolimus": {
        "target": "4-12 ng/mL",
        "timing": "Trough level",
        "guideline": "Transplant guidelines"
    },
    "amikacin": {
        "target": "Peak 20-30, Trough <5 mcg/mL",
        "timing": "30min post & pre-dose",
        "guideline": "IDSA"
    },
    "gentamicin": {
        "target": "Peak 5-10, Trough <2 mcg/mL",
        "timing": "30min post & pre-dose",
        "guideline": "IDSA"
    },
    "tobramycin": {
        "target": "Peak 5-10, Trough <2 mcg/mL",
        "timing": "30min post & pre-dose",
        "guideline": "IDSA"
    }
}

# Beers Criteria - High-Risk Medications for Elderly (subset for prompt context)
BEERS_HIGH_RISK = [
    # First-generation antihistamines (anticholinergic)
    "diphenhydramine", "hydroxyzine", "promethazine", "chlorpheniramine",
    "cyproheptadine", "dexchlorpheniramine", "doxylamine", "meclizine",
    # Long-acting benzodiazepines
    "diazepam", "chlordiazepoxide", "flurazepam", "clorazepate", "quazepam",
    # Short-acting benzodiazepines (still avoid in elderly)
    "alprazolam", "lorazepam", "triazolam", "temazepam",
    # Tricyclic antidepressants
    "amitriptyline", "imipramine", "doxepin", "clomipramine", "nortriptyline",
    # Opioids - avoid especially
    "meperidine", "pentazocine",
    # Antipsychotics (increased mortality in dementia)
    "haloperidol", "thioridazine",
    # Barbiturates
    "phenobarbital", "butalbital",
    # Muscle relaxants
    "carisoprodol", "chlorzoxazone", "cyclobenzaprine", "metaxalone",
    "methocarbamol", "orphenadrine",
    # NSAIDs (GI bleeding, renal, CV risk)
    "indomethacin", "ketorolac", "piroxicam",
    # Anticholinergic antiparkinson
    "benztropine", "trihexyphenidyl",
    # Antispasmodics
    "dicyclomine", "hyoscyamine", "propantheline", "scopolamine",
    # Other high-risk
    "nitrofurantoin",  # If CrCl <30
    "metoclopramide",  # EPS risk
    "mineral oil",  # Aspiration risk
]


class MedicationAgent(MedicationPromptMixin, BaseAgent):
    """Agent specialized in medication management, interaction checking, and prescription generation."""
    
    # Default configuration for medication agent
    DEFAULT_CONFIG = AgentConfig(
        name="MedicationAgent",
        description="Manages medications, checks interactions, and generates prescriptions",
        system_prompt="""You are a clinical pharmacology specialist with expertise in medication management and clinical decision support.

Your role is to:
1. Extract and analyze medication information from clinical text
2. Check for drug-drug interactions and contraindications
3. Validate appropriate dosing based on patient factors
4. Suggest alternative medications when needed
5. Generate properly formatted prescription information
6. Provide medication counseling points for patient education

CLINICAL DECISION SUPPORT GUIDELINES:

PRIORITY CLASSIFICATION:
- Structure ALL findings by clinical urgency using these indicators:
  🔴 HIGH PRIORITY: Immediate action required (contraindicated combinations, life-threatening risks)
  🟡 MODERATE PRIORITY: Address this visit (significant interactions, dosing concerns)
  🟢 LOW PRIORITY: Monitor/educate (minor interactions, routine monitoring)

ACTIONABLE RECOMMENDATIONS:
- Provide checkbox-style specific actions for physicians:
  □ Labs to order with specific timing (e.g., "BMP in 7 days")
  □ Follow-up recommendations
  □ Patient education points
  □ Documentation requirements

PATIENT COUNSELING:
- Include lay-language counseling points for each significant medication
- Use simple bullet points patients can understand
- Include "red flag" symptoms to report immediately
- Note food/drug/activity interactions in plain language

RENAL/HEPATIC DOSING:
- When eGFR or hepatic function is provided, include dose adjustment table:
  | Medication | Standard Dose | Adjusted Dose | Reason | Source |
- Cite sources (FDA label, Lexicomp, clinical guidelines)
- Flag medications requiring discontinuation at certain GFR levels

FORMAT REQUIREMENTS:
1. MEDICATION NAME: Generic (Brand)
2. DOSE: Amount and units
3. ROUTE: How administered
4. FREQUENCY: How often
5. DURATION: Length of treatment
6. INDICATION: Reason for use
7. WARNINGS: Important safety information
8. INTERACTIONS: With current medications
9. MONITORING: Required follow-up with specific labs and timing

INTERACTION SEVERITY LEVELS:
- CONTRAINDICATED: 🔴 Do not use together - immediate action required
- MAJOR: 🔴 Serious interaction, use alternative if possible
- MODERATE: 🟡 Use with caution, monitor closely
- MINOR: 🟢 Minimal risk, monitor for effects

EVIDENCE-BASED PRACTICE:
- Cite clinical guidelines where applicable: ACC/AHA, IDSA, AGS Beers Criteria 2023, CHEST, AAN, STOPP/START
- Include source for dose adjustments: FDA label, Lexicomp, UpToDate, or specific clinical guidelines
- For major interactions, reference guideline or PMID when known
- Format citations: "Per [Guideline Name Year]" or "Source: [FDA label/Lexicomp/UpToDate]"
- Example: "Per IDSA/ASHP 2020 Guidelines, vancomycin AUC-based dosing is preferred"

THERAPEUTIC DRUG MONITORING (TDM):
- Identify narrow therapeutic index drugs requiring TDM (vancomycin, digoxin, lithium, warfarin, phenytoin, aminoglycosides, etc.)
- Provide target levels, optimal timing for blood draws, and monitoring frequency
- Cite relevant monitoring guidelines (IDSA/ASHP for vancomycin, ACC/AHA for digoxin, etc.)
- Include signs of toxicity to monitor for each TDM drug
- Note if AUC-based vs trough-based monitoring is preferred

COST-CONSCIOUS PRESCRIBING:
- Note generic availability for suggested medications
- Flag brand-only and high-cost/specialty medications
- Suggest therapeutic alternatives when a significantly cheaper option exists
- Use cost indicators: "$" = generic available, "$$" = brand preferred, "$$$" = specialty/high-cost
- Consider formulary tier implications when suggesting alternatives

DE-PRESCRIBING (for polypharmacy or elderly patients):
- Apply AGS Beers Criteria 2023 for patients ≥65 years
- Identify Potentially Inappropriate Medications (PIMs)
- Look for medications without clear indication or duplicate therapy
- For de-prescribing candidates, provide: medication, risk/reason for concern, safer alternative if needed, taper instructions, and monitoring after discontinuation
- Note medications that can be stopped abruptly vs those requiring tapering

Always:
- Prioritize patient safety above all
- Include both generic and brand names when relevant
- Consider patient-specific factors (age, weight, renal/hepatic function, allergies)
- Cite clinical guidelines where applicable (ACC/AHA, IDSA, Beers Criteria, etc.)
- Emphasize the importance of clinical judgment
- Never recommend medications without appropriate clinical context""",
        model="gpt-4",
        temperature=0.2,  # Lower temperature for medication accuracy
        max_tokens=2000  # Increased for more comprehensive output
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the medication agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute medication-related tasks.
        
        Args:
            task: Task containing medication query or clinical text
            
        Returns:
            AgentResponse with medication analysis
        """
        try:
            # Determine task type from task description or input data
            task_type = self._determine_task_type(task)
            
            if task_type == "extract":
                return self._extract_medications(task)
            elif task_type == "check_interactions":
                return self._check_interactions(task)
            elif task_type == "generate_prescription":
                return self._generate_prescription(task)
            elif task_type == "validate_dosing":
                return self._validate_dosing(task)
            elif task_type == "suggest_alternatives":
                return self._suggest_alternatives(task)
            else:
                # Default comprehensive analysis
                return self._comprehensive_analysis(task)
                
        except Exception as e:
            logger.error(f"Error in medication analysis: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
    
    def _determine_task_type(self, task: AgentTask) -> str:
        """Determine the type of medication task from the task description."""
        task_desc = task.task_description.lower()
        
        if "extract" in task_desc or "identify" in task_desc:
            return "extract"
        elif "interaction" in task_desc or "check interaction" in task_desc:
            return "check_interactions"
        elif "prescription" in task_desc or "prescribe" in task_desc:
            return "generate_prescription"
        elif "dosing" in task_desc or "dose" in task_desc:
            return "validate_dosing"
        elif "alternative" in task_desc or "substitute" in task_desc:
            return "suggest_alternatives"
        else:
            return "comprehensive"
    
    def _extract_medications(self, task: AgentTask) -> AgentResponse:
        """Extract medications from clinical text."""
        clinical_text = task.input_data.get('clinical_text', '')
        soap_note = task.input_data.get('soap_note', '')
        
        text_to_analyze = clinical_text or soap_note
        if not text_to_analyze:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for medication extraction"
            )
        
        prompt = self._build_extraction_prompt(text_to_analyze, task.context)
        
        # Call AI to extract medications
        extracted = self._call_ai(prompt)
        
        # Parse the extracted medications
        medications = self._parse_medication_list(extracted)
        
        # Create response
        response = AgentResponse(
            result=extracted,
            thoughts=f"Extracted {len(medications)} medications from clinical text",
            success=True,
            metadata={
                'medication_count': len(medications),
                'medications': medications,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _check_interactions(self, task: AgentTask) -> AgentResponse:
        """Check for drug-drug interactions."""
        medications = task.input_data.get('medications', [])
        
        if not medications or len(medications) < 2:
            return AgentResponse(
                result="At least two medications are required for interaction checking",
                success=False,
                error="Insufficient medications for interaction check"
            )
        
        prompt = self._build_interaction_prompt(medications, task.context)
        
        # Call AI to check interactions
        interaction_analysis = self._call_ai(prompt)
        
        # Parse interaction severity
        has_major_interaction = any(
            severity in interaction_analysis.upper() 
            for severity in ["CONTRAINDICATED", "MAJOR", "SERIOUS"]
        )
        
        # Simulate tool call for drug interaction database
        tool_calls = [
            ToolCall(
                tool_name="lookup_drug_interactions",
                arguments={"medications": medications}
            )
        ]
        
        # Create response
        response = AgentResponse(
            result=interaction_analysis,
            thoughts=f"Analyzed interactions between {len(medications)} medications",
            tool_calls=tool_calls,
            success=True,
            metadata={
                'medication_count': len(medications),
                'has_major_interaction': has_major_interaction,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _generate_prescription(self, task: AgentTask) -> AgentResponse:
        """Generate prescription information."""
        medication_info = task.input_data.get('medication', {})
        patient_info = task.input_data.get('patient_info', {})
        indication = task.input_data.get('indication', '')
        
        if not medication_info:
            return AgentResponse(
                result="",
                success=False,
                error="No medication information provided for prescription"
            )
        
        prompt = self._build_prescription_prompt(medication_info, patient_info, indication, task.context)
        
        # Call AI to generate prescription
        prescription = self._call_ai(prompt)
        
        # Create response
        response = AgentResponse(
            result=prescription,
            thoughts="Generated prescription with appropriate dosing and instructions",
            success=True,
            metadata={
                'medication': medication_info.get('name', 'Unknown'),
                'has_patient_info': bool(patient_info),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _validate_dosing(self, task: AgentTask) -> AgentResponse:
        """Validate medication dosing."""
        medication = task.input_data.get('medication', {})
        patient_factors = task.input_data.get('patient_factors', {})
        
        if not medication:
            return AgentResponse(
                result="",
                success=False,
                error="No medication information provided for dosing validation"
            )
        
        prompt = self._build_dosing_prompt(medication, patient_factors, task.context)
        
        # Call AI to validate dosing
        validation = self._call_ai(prompt)
        
        # Check if dosing is appropriate
        is_appropriate = "appropriate" in validation.lower() and "inappropriate" not in validation.lower()
        
        # Create response
        response = AgentResponse(
            result=validation,
            thoughts="Validated medication dosing based on patient factors",
            success=True,
            metadata={
                'medication': medication.get('name', 'Unknown'),
                'dose': medication.get('dose', 'Unknown'),
                'dosing_appropriate': is_appropriate,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _suggest_alternatives(self, task: AgentTask) -> AgentResponse:
        """Suggest alternative medications."""
        current_medication = task.input_data.get('current_medication', {})
        reason_for_change = task.input_data.get('reason', '')
        patient_factors = task.input_data.get('patient_factors', {})
        
        if not current_medication:
            return AgentResponse(
                result="",
                success=False,
                error="No current medication provided for alternative suggestions"
            )
        
        prompt = self._build_alternatives_prompt(
            current_medication, reason_for_change, patient_factors, task.context
        )
        
        # Call AI to suggest alternatives
        alternatives = self._call_ai(prompt)
        
        # Parse alternative count
        alternative_count = len(re.findall(r'\d+\.', alternatives))
        
        # Create response
        response = AgentResponse(
            result=alternatives,
            thoughts=f"Suggested {alternative_count} alternative medications",
            success=True,
            metadata={
                'current_medication': current_medication.get('name', 'Unknown'),
                'reason_for_change': reason_for_change,
                'alternative_count': alternative_count,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _comprehensive_analysis(self, task: AgentTask) -> AgentResponse:
        """Perform comprehensive medication analysis."""
        clinical_text = task.input_data.get('clinical_text', '')
        soap_note = task.input_data.get('soap_note', '')
        current_medications = task.input_data.get('current_medications', [])
        patient_context = task.input_data.get('patient_context', {})

        text_to_analyze = clinical_text or soap_note

        prompt = self._build_comprehensive_prompt(
            text_to_analyze, current_medications, task.context, patient_context
        )
        
        # Call AI for comprehensive analysis
        analysis = self._call_ai(prompt)

        # Create response
        response = AgentResponse(
            result=analysis,
            thoughts="Performed comprehensive medication analysis",
            success=True,
            metadata={
                'analysis_type': 'comprehensive',
                'has_current_medications': bool(current_medications),
                'has_patient_context': bool(patient_context),
                'patient_age': patient_context.get('age'),
                'patient_allergies': patient_context.get('allergies', []),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _parse_medication_list(self, text: str) -> List[Dict[str, str]]:
        """Parse extracted medications into structured format."""
        medications = []
        
        # Simple parsing - in production, would use more sophisticated NLP
        lines = text.strip().split('\n')
        current_med = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_med:
                    medications.append(current_med)
                    current_med = {}
                continue
            
            # Look for medication patterns
            if line.startswith('-') or line[0].isdigit():
                if current_med:
                    medications.append(current_med)
                # Extract medication name
                med_name = re.sub(r'^[-\d\.\s]+', '', line).strip()
                current_med = {'name': med_name, 'raw': line}
            elif ':' in line:
                # Extract property
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                current_med[key] = value.strip()
        
        if current_med:
            medications.append(current_med)
        
        return medications
    
    def extract_medications_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Convenience method to extract medications from text.
        
        Args:
            text: Clinical text containing medication information
            
        Returns:
            List of dictionaries containing medication information
        """
        task = AgentTask(
            task_description="Extract all medications from clinical text",
            input_data={"clinical_text": text}
        )
        
        response = self.execute(task)
        if response and response.success:
            return response.metadata.get('medications', [])
        return []
    
    def check_drug_interactions(self, medications: List[str]) -> Optional[str]:
        """
        Convenience method to check drug interactions.
        
        Args:
            medications: List of medication names to check
            
        Returns:
            Interaction analysis text if successful, None otherwise
        """
        task = AgentTask(
            task_description="Check for drug-drug interactions",
            input_data={"medications": medications}
        )
        
        response = self.execute(task)
        if response and response.success:
            return response.result
        return None