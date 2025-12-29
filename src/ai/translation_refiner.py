"""
Translation Refinement Module

Provides hybrid translation refinement using LLM to improve
medical terminology accuracy in Google/DeepL translations.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Optional, List

from ai.ai import call_ai
from settings.settings import SETTINGS


@dataclass
class RefinementResult:
    """Result of translation refinement."""
    original_translation: str
    refined_translation: str
    was_refined: bool
    confidence_score: float
    medical_terms_detected: List[str]


class TranslationRefiner:
    """Refines translations using LLM for medical terminology accuracy.

    Uses a hybrid approach: fast Google/DeepL translation first,
    then optional LLM refinement for medical content.
    """

    # Prompt templates for medical translation refinement
    MEDICAL_REFINEMENT_PROMPT = """You are a medical translation specialist. Review this translation for medical accuracy.

Source text ({source_lang}): {source_text}

Initial translation ({target_lang}): {initial_translation}

Instructions:
1. If the translation contains medical terms, medications, symptoms, or clinical concepts, provide a refined translation that uses proper medical terminology
2. Preserve the original meaning while improving medical accuracy
3. If the translation is already accurate, return it unchanged
4. Keep the same natural conversational tone appropriate for patient-provider communication
5. Do NOT add explanations or notes - return ONLY the refined translation text

Return ONLY the refined translation, nothing else."""

    MEDICAL_SYSTEM_MESSAGE = """You are a bilingual medical professional specializing in patient-provider communication. Your task is to ensure medical translations are accurate and use proper terminology while remaining understandable to patients. You are fluent in both languages and understand medical concepts in context. Always respond with just the translation, no explanations."""

    # Medical content indicators for detecting when refinement may be needed
    MEDICAL_INDICATORS = [
        # English symptoms
        'pain', 'ache', 'swelling', 'bleeding', 'fever', 'nausea', 'vomiting',
        'dizziness', 'fatigue', 'weakness', 'numbness', 'tingling', 'cough',
        'shortness', 'breath', 'chest', 'headache', 'migraine',
        # Body parts
        'heart', 'lung', 'liver', 'kidney', 'stomach', 'intestine', 'brain',
        'spine', 'joint', 'muscle', 'bone', 'artery', 'vein',
        # Medical terms
        'diagnosis', 'treatment', 'medication', 'prescription', 'dosage',
        'injection', 'surgery', 'procedure', 'symptoms', 'condition',
        'chronic', 'acute', 'allergy', 'allergic', 'infection', 'inflammation',
        # Units and dosing
        'mg', 'ml', 'mcg', 'twice daily', 'three times', 'once daily',
        'before meals', 'after meals', 'with food', 'on empty stomach',
        # Spanish medical terms
        'dolor', 'fiebre', 'medicamento', 'receta', 'dosis', 'sintoma',
        'enfermedad', 'tratamiento', 'cirugia', 'inyeccion', 'pastilla',
        'alergia', 'infeccion', 'presion', 'sangre', 'corazon', 'pulmon'
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._load_settings()

    def _load_settings(self):
        """Load refinement settings from application settings."""
        translation_settings = SETTINGS.get("translation", {})
        self.refinement_enabled = translation_settings.get("llm_refinement_enabled", False)
        self.refinement_provider = translation_settings.get("refinement_provider", "openai")
        self.refinement_model = translation_settings.get("refinement_model", "gpt-3.5-turbo")
        self.refinement_temperature = translation_settings.get("refinement_temperature", 0.1)

    def reload_settings(self):
        """Reload settings from application settings."""
        self._load_settings()

    def should_refine(self, text: str) -> bool:
        """Determine if text likely contains medical content worth refining.

        Args:
            text: Text to analyze

        Returns:
            True if text contains medical indicators
        """
        if not self.refinement_enabled:
            return False

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in self.MEDICAL_INDICATORS)

    def refine_translation(
        self,
        source_text: str,
        initial_translation: str,
        source_lang: str,
        target_lang: str,
        force_refinement: bool = False
    ) -> RefinementResult:
        """Refine a translation using LLM for medical accuracy.

        Args:
            source_text: Original text before translation
            initial_translation: Translation from Google/DeepL
            source_lang: Source language code
            target_lang: Target language code
            force_refinement: If True, always refine even without medical indicators

        Returns:
            RefinementResult with original and refined translations
        """
        # Check if refinement should be performed
        should_process = force_refinement or (
            self.should_refine(source_text) or self.should_refine(initial_translation)
        )

        if not should_process:
            return RefinementResult(
                original_translation=initial_translation,
                refined_translation=initial_translation,
                was_refined=False,
                confidence_score=1.0,
                medical_terms_detected=[]
            )

        try:
            # Build the refinement prompt
            prompt = self.MEDICAL_REFINEMENT_PROMPT.format(
                source_lang=source_lang,
                target_lang=target_lang,
                source_text=source_text,
                initial_translation=initial_translation
            )

            # Call LLM for refinement
            self.logger.debug(f"Refining translation with LLM: {self.refinement_model}")
            refined = call_ai(
                model=self.refinement_model,
                system_message=self.MEDICAL_SYSTEM_MESSAGE,
                prompt=prompt,
                temperature=self.refinement_temperature
            )

            # Clean up result
            refined = refined.strip()

            # Remove any quotes if the LLM wrapped the response
            if refined.startswith('"') and refined.endswith('"'):
                refined = refined[1:-1]
            if refined.startswith("'") and refined.endswith("'"):
                refined = refined[1:-1]

            # Check if refinement actually changed the translation
            was_refined = refined.lower() != initial_translation.lower()

            # Detect medical terms found
            medical_terms = self._extract_medical_terms(source_text + " " + initial_translation)

            return RefinementResult(
                original_translation=initial_translation,
                refined_translation=refined,
                was_refined=was_refined,
                confidence_score=0.9 if was_refined else 1.0,
                medical_terms_detected=medical_terms
            )

        except Exception as e:
            self.logger.error(f"LLM refinement failed: {e}")
            return RefinementResult(
                original_translation=initial_translation,
                refined_translation=initial_translation,
                was_refined=False,
                confidence_score=0.5,
                medical_terms_detected=[]
            )

    def _extract_medical_terms(self, text: str) -> List[str]:
        """Extract potential medical terms from text.

        Args:
            text: Text to analyze

        Returns:
            List of detected medical indicator terms
        """
        text_lower = text.lower()
        return [term for term in self.MEDICAL_INDICATORS if term in text_lower]


# Singleton instance
_refiner: Optional[TranslationRefiner] = None
_refiner_lock = threading.Lock()


def get_translation_refiner() -> TranslationRefiner:
    """Get the global translation refiner instance.

    Returns:
        TranslationRefiner singleton instance
    """
    global _refiner
    if _refiner is None:
        with _refiner_lock:
            if _refiner is None:
                _refiner = TranslationRefiner()
    return _refiner
