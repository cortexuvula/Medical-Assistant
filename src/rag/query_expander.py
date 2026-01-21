"""
Medical query expansion for RAG system.

Provides bidirectional expansion of:
- Medical abbreviations (HTN ↔ hypertension)
- Medical synonyms (heart attack ↔ myocardial infarction)
- Lay terms ↔ medical terminology
"""

import logging
import re
from typing import Optional

from rag.models import QueryExpansion
from rag.search_config import SearchQualityConfig, get_search_quality_config

logger = logging.getLogger(__name__)


# Medical abbreviations dictionary (abbreviation -> expansions)
MEDICAL_ABBREVIATIONS: dict[str, list[str]] = {
    # Cardiovascular
    "mi": ["myocardial infarction", "heart attack"],
    "cad": ["coronary artery disease", "coronary heart disease"],
    "chf": ["congestive heart failure", "heart failure"],
    "htn": ["hypertension", "high blood pressure"],
    "afib": ["atrial fibrillation", "a-fib"],
    "dvt": ["deep vein thrombosis", "deep venous thrombosis"],
    "pe": ["pulmonary embolism"],
    "cvd": ["cardiovascular disease", "heart disease"],
    "bp": ["blood pressure"],
    "hr": ["heart rate"],
    "ecg": ["electrocardiogram", "ekg"],
    "ekg": ["electrocardiogram", "ecg"],

    # Respiratory
    "copd": ["chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
    "sob": ["shortness of breath", "dyspnea"],
    "ards": ["acute respiratory distress syndrome"],
    "uri": ["upper respiratory infection", "cold"],
    "lrti": ["lower respiratory tract infection"],
    "tb": ["tuberculosis"],
    "pna": ["pneumonia"],

    # Endocrine/Metabolic
    "dm": ["diabetes mellitus", "diabetes"],
    "t2dm": ["type 2 diabetes", "diabetes mellitus type 2", "adult onset diabetes"],
    "t1dm": ["type 1 diabetes", "diabetes mellitus type 1", "juvenile diabetes"],
    "dka": ["diabetic ketoacidosis"],
    "hhs": ["hyperosmolar hyperglycemic state"],
    "tsh": ["thyroid stimulating hormone"],
    "hba1c": ["glycated hemoglobin", "hemoglobin a1c", "a1c"],
    "a1c": ["glycated hemoglobin", "hemoglobin a1c", "hba1c"],

    # Neurological
    "cva": ["cerebrovascular accident", "stroke"],
    "tia": ["transient ischemic attack", "mini stroke"],
    "ms": ["multiple sclerosis"],
    "als": ["amyotrophic lateral sclerosis", "lou gehrig disease"],
    "ha": ["headache", "cephalgia"],
    "loc": ["loss of consciousness", "syncope"],
    "sz": ["seizure", "convulsion"],

    # Gastrointestinal
    "gi": ["gastrointestinal", "digestive"],
    "gerd": ["gastroesophageal reflux disease", "acid reflux", "heartburn"],
    "ibs": ["irritable bowel syndrome"],
    "ibd": ["inflammatory bowel disease", "crohns disease", "ulcerative colitis"],
    "n/v": ["nausea and vomiting", "nausea vomiting"],
    "bm": ["bowel movement", "stool"],
    "gu": ["genitourinary"],

    # Renal
    "ckd": ["chronic kidney disease", "renal failure"],
    "akf": ["acute kidney failure", "acute renal failure"],
    "esrd": ["end stage renal disease", "kidney failure"],
    "uti": ["urinary tract infection", "bladder infection"],
    "bun": ["blood urea nitrogen"],
    "gfr": ["glomerular filtration rate"],

    # Hematology/Oncology
    "wbc": ["white blood cell", "leukocyte"],
    "rbc": ["red blood cell", "erythrocyte"],
    "plt": ["platelet", "thrombocyte"],
    "hgb": ["hemoglobin"],
    "hct": ["hematocrit"],
    "ca": ["cancer", "carcinoma"],
    "mets": ["metastases", "metastatic disease"],

    # Infectious Disease
    "hiv": ["human immunodeficiency virus", "aids virus"],
    "aids": ["acquired immunodeficiency syndrome"],
    "mrsa": ["methicillin resistant staphylococcus aureus"],
    "c diff": ["clostridioides difficile", "clostridium difficile"],

    # Musculoskeletal
    "oa": ["osteoarthritis", "degenerative joint disease"],
    "ra": ["rheumatoid arthritis"],
    "fx": ["fracture", "broken bone"],
    "rom": ["range of motion"],
    "lbp": ["low back pain", "lower back pain"],

    # Pain/Symptoms
    "cp": ["chest pain"],
    "abd": ["abdominal", "belly"],
    "prn": ["as needed"],
    "po": ["by mouth", "oral"],

    # General Medical
    "hx": ["history"],
    "pmh": ["past medical history", "medical history"],
    "fhx": ["family history"],
    "shx": ["social history"],
    "ros": ["review of systems"],
    "pe": ["physical exam", "physical examination"],
    "dx": ["diagnosis"],
    "ddx": ["differential diagnosis"],
    "tx": ["treatment", "therapy"],
    "rx": ["prescription", "medication"],
    "sx": ["symptoms", "surgery"],
    "bmi": ["body mass index"],
    "vs": ["vital signs"],
    "npo": ["nothing by mouth", "nil per os"],
    "qd": ["once daily", "every day"],
    "bid": ["twice daily", "twice a day"],
    "tid": ["three times daily", "three times a day"],
    "qid": ["four times daily", "four times a day"],
}

# Reverse mapping (full term -> abbreviations)
TERM_TO_ABBREVIATIONS: dict[str, list[str]] = {}
for abbr, terms in MEDICAL_ABBREVIATIONS.items():
    for term in terms:
        term_lower = term.lower()
        if term_lower not in TERM_TO_ABBREVIATIONS:
            TERM_TO_ABBREVIATIONS[term_lower] = []
        if abbr not in TERM_TO_ABBREVIATIONS[term_lower]:
            TERM_TO_ABBREVIATIONS[term_lower].append(abbr)


# Medical synonyms dictionary (term -> synonyms)
MEDICAL_SYNONYMS: dict[str, list[str]] = {
    # Cardiovascular conditions
    "heart attack": ["myocardial infarction", "cardiac event", "coronary event", "mi"],
    "myocardial infarction": ["heart attack", "cardiac event", "coronary event"],
    "high blood pressure": ["hypertension", "elevated bp", "htn"],
    "hypertension": ["high blood pressure", "elevated bp"],
    "heart failure": ["cardiac failure", "congestive heart failure", "chf"],
    "irregular heartbeat": ["arrhythmia", "cardiac arrhythmia", "heart rhythm disorder"],
    "arrhythmia": ["irregular heartbeat", "heart rhythm disorder"],
    "chest pain": ["angina", "cardiac pain", "thoracic pain"],
    "angina": ["chest pain", "angina pectoris", "cardiac pain"],

    # Respiratory conditions
    "breathing difficulty": ["dyspnea", "shortness of breath", "respiratory distress"],
    "dyspnea": ["shortness of breath", "breathing difficulty", "respiratory distress"],
    "asthma": ["bronchial asthma", "reactive airway disease"],
    "pneumonia": ["lung infection", "chest infection", "pna"],
    "cough": ["tussis"],

    # Neurological conditions
    "stroke": ["cerebrovascular accident", "cva", "brain attack"],
    "cerebrovascular accident": ["stroke", "brain attack"],
    "headache": ["cephalgia", "head pain", "ha"],
    "migraine": ["migraine headache", "vascular headache"],
    "seizure": ["convulsion", "epileptic episode", "fit"],
    "dizziness": ["vertigo", "lightheadedness", "disequilibrium"],
    "numbness": ["paresthesia", "loss of sensation"],
    "weakness": ["asthenia", "debility"],
    "memory loss": ["amnesia", "cognitive impairment", "forgetfulness"],
    "confusion": ["disorientation", "altered mental status", "delirium"],

    # Gastrointestinal conditions
    "heartburn": ["acid reflux", "gerd", "gastroesophageal reflux"],
    "acid reflux": ["heartburn", "gerd", "gastroesophageal reflux"],
    "stomach pain": ["abdominal pain", "gastric pain", "epigastric pain"],
    "abdominal pain": ["stomach pain", "belly pain", "gastric pain"],
    "nausea": ["queasiness", "upset stomach"],
    "vomiting": ["emesis", "throwing up"],
    "diarrhea": ["loose stools", "frequent bowel movements"],
    "constipation": ["difficulty passing stool", "infrequent bowel movements"],
    "bloating": ["abdominal distension", "gas", "flatulence"],

    # Metabolic conditions
    "diabetes": ["diabetes mellitus", "dm", "high blood sugar"],
    "high blood sugar": ["hyperglycemia", "elevated glucose"],
    "low blood sugar": ["hypoglycemia"],
    "obesity": ["overweight", "excess weight"],
    "weight loss": ["weight reduction", "losing weight"],
    "weight gain": ["weight increase", "gaining weight"],

    # Musculoskeletal
    "back pain": ["dorsalgia", "spinal pain", "lumbago"],
    "joint pain": ["arthralgia", "articular pain"],
    "arthritis": ["joint inflammation", "arthritic condition"],
    "muscle pain": ["myalgia", "muscular pain"],
    "swelling": ["edema", "inflammation"],

    # General symptoms
    "fatigue": ["tiredness", "exhaustion", "lethargy", "malaise"],
    "fever": ["pyrexia", "elevated temperature", "febrile"],
    "chills": ["rigors", "shivering"],
    "pain": ["discomfort", "ache", "soreness"],
    "rash": ["skin eruption", "dermatitis", "exanthem"],
    "itching": ["pruritus", "itchy skin"],
    "infection": ["infectious disease", "sepsis"],
    "inflammation": ["swelling", "inflammatory response"],
    "bleeding": ["hemorrhage", "blood loss"],
    "bruising": ["contusion", "ecchymosis"],

    # Psychiatric
    "depression": ["depressive disorder", "major depression", "low mood"],
    "anxiety": ["anxiety disorder", "nervousness", "anxiousness"],
    "insomnia": ["sleep disorder", "sleeplessness", "difficulty sleeping"],

    # Medications (common)
    "aspirin": ["acetylsalicylic acid", "asa"],
    "tylenol": ["acetaminophen", "paracetamol"],
    "ibuprofen": ["advil", "motrin", "nsaid"],
    "blood thinner": ["anticoagulant", "warfarin", "coumadin"],
    "statin": ["cholesterol medication", "lipitor", "atorvastatin"],
    "beta blocker": ["metoprolol", "atenolol", "propranolol"],
    "ace inhibitor": ["lisinopril", "enalapril", "ramipril"],
    "insulin": ["diabetes medication", "humalog", "novolog"],
    "antibiotic": ["antimicrobial", "antibacterial"],
    "painkiller": ["analgesic", "pain medication", "pain reliever"],
}

# Build reverse synonym mapping
REVERSE_SYNONYMS: dict[str, list[str]] = {}
for term, synonyms in MEDICAL_SYNONYMS.items():
    term_lower = term.lower()
    for syn in synonyms:
        syn_lower = syn.lower()
        if syn_lower not in REVERSE_SYNONYMS:
            REVERSE_SYNONYMS[syn_lower] = []
        if term_lower not in REVERSE_SYNONYMS[syn_lower]:
            REVERSE_SYNONYMS[syn_lower].append(term_lower)


class MedicalQueryExpander:
    """Expands medical queries with synonyms and abbreviations."""

    def __init__(self, config: Optional[SearchQualityConfig] = None):
        """Initialize the query expander.

        Args:
            config: Search quality configuration
        """
        self.config = config or get_search_quality_config()

    def expand_query(self, query: str) -> QueryExpansion:
        """Expand a query with medical terminology.

        Args:
            query: Original search query

        Returns:
            QueryExpansion with expanded terms
        """
        expansion = QueryExpansion(original_query=query)

        if not self.config.enable_query_expansion:
            expansion.expanded_query = query
            return expansion

        # Tokenize query
        words = self._tokenize(query)

        # Track expansions
        all_expanded_terms = []

        # Expand abbreviations
        if self.config.expand_abbreviations:
            abbr_expansions = self._expand_abbreviations(words)
            expansion.abbreviation_expansions = abbr_expansions
            for terms in abbr_expansions.values():
                all_expanded_terms.extend(terms[:self.config.max_expansion_terms])

        # Expand synonyms
        if self.config.expand_synonyms:
            syn_expansions = self._expand_synonyms(words, query.lower())
            expansion.synonym_expansions = syn_expansions
            for terms in syn_expansions.values():
                all_expanded_terms.extend(terms[:self.config.max_expansion_terms])

        # Deduplicate and limit
        seen = set()
        unique_terms = []
        for term in all_expanded_terms:
            term_lower = term.lower()
            if term_lower not in seen and term_lower != query.lower():
                seen.add(term_lower)
                unique_terms.append(term)

        expansion.expanded_terms = unique_terms

        # Build expanded query string
        expansion.expanded_query = self._build_expanded_query(query, unique_terms)

        logger.debug(
            f"Query expansion: '{query}' -> {len(unique_terms)} additional terms"
        )

        return expansion

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words and phrases.

        Args:
            text: Input text

        Returns:
            List of tokens (words and multi-word phrases)
        """
        # Normalize
        text = text.lower().strip()

        # Extract individual words
        words = re.findall(r'\b\w+\b', text)

        # Also extract 2-word and 3-word phrases
        phrases = []
        for i in range(len(words)):
            if i + 1 < len(words):
                phrases.append(f"{words[i]} {words[i+1]}")
            if i + 2 < len(words):
                phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")

        return words + phrases

    def _expand_abbreviations(self, tokens: list[str]) -> dict[str, list[str]]:
        """Expand medical abbreviations.

        Args:
            tokens: List of query tokens

        Returns:
            Dictionary of abbreviation -> expansions
        """
        expansions = {}

        for token in tokens:
            token_lower = token.lower()

            # Check if token is an abbreviation
            if token_lower in MEDICAL_ABBREVIATIONS:
                expansions[token_lower] = MEDICAL_ABBREVIATIONS[token_lower][
                    :self.config.max_expansion_terms
                ]

            # Check if token is a full term that has abbreviations
            if token_lower in TERM_TO_ABBREVIATIONS:
                abbrs = TERM_TO_ABBREVIATIONS[token_lower]
                if token_lower not in expansions:
                    expansions[token_lower] = []
                expansions[token_lower].extend(abbrs[:self.config.max_expansion_terms])

        return expansions

    def _expand_synonyms(
        self,
        tokens: list[str],
        full_query: str
    ) -> dict[str, list[str]]:
        """Expand medical synonyms.

        Args:
            tokens: List of query tokens
            full_query: Full query string for phrase matching

        Returns:
            Dictionary of term -> synonyms
        """
        expansions = {}

        # Check tokens
        for token in tokens:
            token_lower = token.lower()

            # Check in primary synonyms
            if token_lower in MEDICAL_SYNONYMS:
                expansions[token_lower] = MEDICAL_SYNONYMS[token_lower][
                    :self.config.max_expansion_terms
                ]

            # Check in reverse synonyms
            if token_lower in REVERSE_SYNONYMS:
                if token_lower not in expansions:
                    expansions[token_lower] = []
                expansions[token_lower].extend(
                    REVERSE_SYNONYMS[token_lower][:self.config.max_expansion_terms]
                )

        # Also check full query for multi-word matches
        for phrase in MEDICAL_SYNONYMS.keys():
            if phrase in full_query and phrase not in expansions:
                expansions[phrase] = MEDICAL_SYNONYMS[phrase][
                    :self.config.max_expansion_terms
                ]

        for phrase in REVERSE_SYNONYMS.keys():
            if phrase in full_query:
                if phrase not in expansions:
                    expansions[phrase] = []
                expansions[phrase].extend(
                    REVERSE_SYNONYMS[phrase][:self.config.max_expansion_terms]
                )

        return expansions

    def _build_expanded_query(
        self,
        original: str,
        expanded_terms: list[str]
    ) -> str:
        """Build an expanded query string for search.

        Args:
            original: Original query
            expanded_terms: List of expanded terms

        Returns:
            Expanded query string suitable for search
        """
        if not expanded_terms:
            return original

        # Combine original with top expanded terms
        all_terms = [original] + expanded_terms[:5]  # Limit to avoid overly broad search
        return " OR ".join(all_terms)

    def get_search_terms(self, expansion: QueryExpansion) -> list[str]:
        """Get all search terms from an expansion.

        Args:
            expansion: Query expansion result

        Returns:
            List of unique search terms
        """
        return expansion.get_all_search_terms()


# Singleton instance
_expander: Optional[MedicalQueryExpander] = None


def get_query_expander() -> MedicalQueryExpander:
    """Get the global query expander instance.

    Returns:
        MedicalQueryExpander instance
    """
    global _expander
    if _expander is None:
        _expander = MedicalQueryExpander()
    return _expander


def reset_query_expander():
    """Reset the global query expander instance."""
    global _expander
    _expander = None


def expand_medical_query(query: str) -> QueryExpansion:
    """Convenience function to expand a medical query.

    Args:
        query: Search query

    Returns:
        QueryExpansion with expanded terms
    """
    expander = get_query_expander()
    return expander.expand_query(query)
