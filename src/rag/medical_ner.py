"""
Medical Named Entity Recognition for RAG system.

Provides pattern-based and dictionary-based extraction of medical entities:
- Conditions/Diagnoses
- Medications/Drugs
- Procedures
- Anatomy/Body Parts
- Lab Tests
- Dosages
- Vital Signs
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MedicalEntityType(str, Enum):
    """Types of medical entities that can be extracted."""
    CONDITION = "condition"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    ANATOMY = "anatomy"
    LAB_TEST = "lab_test"
    DOSAGE = "dosage"
    VITAL_SIGN = "vital_sign"
    SYMPTOM = "symptom"
    FREQUENCY = "frequency"
    ROUTE = "route"


@dataclass
class MedicalEntity:
    """A medical entity extracted from text."""
    text: str
    entity_type: MedicalEntityType
    normalized_name: Optional[str] = None
    confidence: float = 1.0
    start_pos: int = 0
    end_pos: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "entity_type": self.entity_type.value,
            "normalized_name": self.normalized_name,
            "confidence": self.confidence,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "metadata": self.metadata,
        }


class MedicalNERExtractor:
    """Extracts medical entities using rule-based + dictionary approaches."""

    # Dosage patterns: "500 mg", "10 mL", "2.5 mg/mL", etc.
    DOSAGE_PATTERN = re.compile(
        r'\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|kg|ml|mL|L|units?|IU|meq|mEq|mmol)(?:/(?:kg|mL|L|day|hr|h))?\b',
        re.IGNORECASE
    )

    # Blood pressure patterns: "120/80", "140/90 mmHg"
    BP_PATTERN = re.compile(
        r'\b(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmHg|mm\s*Hg)?\b',
        re.IGNORECASE
    )

    # Heart rate patterns: "HR 72", "heart rate: 85 bpm", "pulse 90"
    HR_PATTERN = re.compile(
        r'\b(?:HR|heart\s+rate|pulse)[:\s]+(\d{2,3})(?:\s*(?:bpm|beats?(?:\s*per\s*min(?:ute)?)?))?\b',
        re.IGNORECASE
    )

    # Temperature patterns: "temp 98.6", "37.5C", "101.2F"
    TEMP_PATTERN = re.compile(
        r'\b(?:temp(?:erature)?[:\s]+)?(\d{2,3}(?:\.\d)?)\s*°?\s*([FC]|fahrenheit|celsius)?\b',
        re.IGNORECASE
    )

    # SpO2/Oxygen saturation patterns: "SpO2 98%", "O2 sat 95%"
    SPO2_PATTERN = re.compile(
        r'\b(?:SpO2|O2\s*sat(?:uration)?|oxygen\s+sat(?:uration)?)[:\s]+(\d{2,3})\s*%?\b',
        re.IGNORECASE
    )

    # Respiratory rate patterns: "RR 16", "resp rate 18"
    RR_PATTERN = re.compile(
        r'\b(?:RR|resp(?:iratory)?\s+rate)[:\s]+(\d{1,2})(?:\s*(?:breaths?(?:\s*per\s*min(?:ute)?)?))?\b',
        re.IGNORECASE
    )

    # Weight patterns: "180 lbs", "82 kg"
    WEIGHT_PATTERN = re.compile(
        r'\b(\d{2,3}(?:\.\d)?)\s*(lbs?|pounds?|kg|kilograms?)\b',
        re.IGNORECASE
    )

    # Height patterns: "5'10\"", "170 cm", "5 feet 10 inches"
    HEIGHT_PATTERN = re.compile(
        r'\b(?:(\d)[\'′]\s*(\d{1,2})[\"″]?|(\d{2,3})\s*(?:cm|centimeters?)|(\d)\s*(?:feet|ft)\.?\s*(\d{1,2})\s*(?:inches?|in)?)\b',
        re.IGNORECASE
    )

    # Frequency patterns: "twice daily", "TID", "q6h", "every 8 hours"
    FREQUENCY_PATTERNS = [
        (re.compile(r'\b(once\s+daily|QD|q\.?d\.?)\b', re.IGNORECASE), "once daily"),
        (re.compile(r'\b(twice\s+daily|BID|b\.?i\.?d\.?)\b', re.IGNORECASE), "twice daily"),
        (re.compile(r'\b(three\s+times\s+(?:a\s+)?daily|TID|t\.?i\.?d\.?)\b', re.IGNORECASE), "three times daily"),
        (re.compile(r'\b(four\s+times\s+(?:a\s+)?daily|QID|q\.?i\.?d\.?)\b', re.IGNORECASE), "four times daily"),
        (re.compile(r'\b(every\s+(\d+)\s+hours?|q(\d+)h)\b', re.IGNORECASE), "every {n} hours"),
        (re.compile(r'\b(as\s+needed|PRN|p\.?r\.?n\.?)\b', re.IGNORECASE), "as needed"),
        (re.compile(r'\b(at\s+bedtime|HS|h\.?s\.?|qhs)\b', re.IGNORECASE), "at bedtime"),
        (re.compile(r'\b(before\s+meals?|AC|a\.?c\.?)\b', re.IGNORECASE), "before meals"),
        (re.compile(r'\b(after\s+meals?|PC|p\.?c\.?)\b', re.IGNORECASE), "after meals"),
    ]

    # Route patterns: "by mouth", "PO", "IV", "subcutaneous"
    ROUTE_PATTERNS = [
        (re.compile(r'\b(by\s+mouth|oral(?:ly)?|PO|p\.?o\.?)\b', re.IGNORECASE), "oral"),
        (re.compile(r'\b(intravenous(?:ly)?|IV|i\.?v\.?)\b', re.IGNORECASE), "intravenous"),
        (re.compile(r'\b(intramuscular(?:ly)?|IM|i\.?m\.?)\b', re.IGNORECASE), "intramuscular"),
        (re.compile(r'\b(subcutaneous(?:ly)?|SQ|SC|subQ|s\.?c\.?)\b', re.IGNORECASE), "subcutaneous"),
        (re.compile(r'\b(topical(?:ly)?)\b', re.IGNORECASE), "topical"),
        (re.compile(r'\b(inhaled?|inhalation|MDI|nebulizer)\b', re.IGNORECASE), "inhalation"),
        (re.compile(r'\b(sublingual(?:ly)?|SL|s\.?l\.?)\b', re.IGNORECASE), "sublingual"),
        (re.compile(r'\b(rectal(?:ly)?|PR|p\.?r\.?)\b', re.IGNORECASE), "rectal"),
        (re.compile(r'\b(transdermal(?:ly)?|patch)\b', re.IGNORECASE), "transdermal"),
        (re.compile(r'\b(ophthalmic|eye\s+drops?)\b', re.IGNORECASE), "ophthalmic"),
        (re.compile(r'\b(otic|ear\s+drops?)\b', re.IGNORECASE), "otic"),
        (re.compile(r'\b(nasal(?:ly)?|intranasal)\b', re.IGNORECASE), "nasal"),
    ]

    # Lab test patterns
    LAB_TEST_PATTERNS = [
        (re.compile(r'\b(CBC|complete\s+blood\s+count)\b', re.IGNORECASE), "complete blood count"),
        (re.compile(r'\b(BMP|basic\s+metabolic\s+panel)\b', re.IGNORECASE), "basic metabolic panel"),
        (re.compile(r'\b(CMP|comprehensive\s+metabolic\s+panel)\b', re.IGNORECASE), "comprehensive metabolic panel"),
        (re.compile(r'\b(LFTs?|liver\s+function\s+tests?)\b', re.IGNORECASE), "liver function tests"),
        (re.compile(r'\b(lipid\s+panel|cholesterol\s+panel)\b', re.IGNORECASE), "lipid panel"),
        (re.compile(r'\b(TSH|thyroid\s+stimulating\s+hormone)\b', re.IGNORECASE), "TSH"),
        (re.compile(r'\b(HbA1c|hemoglobin\s+A1c|glycated\s+hemoglobin)\b', re.IGNORECASE), "HbA1c"),
        (re.compile(r'\b(PSA|prostate\s+specific\s+antigen)\b', re.IGNORECASE), "PSA"),
        (re.compile(r'\b(UA|urinalysis)\b', re.IGNORECASE), "urinalysis"),
        (re.compile(r'\b(PT/INR|prothrombin\s+time|INR)\b', re.IGNORECASE), "PT/INR"),
        (re.compile(r'\b(BNP|B-type\s+natriuretic\s+peptide)\b', re.IGNORECASE), "BNP"),
        (re.compile(r'\b(troponin|cardiac\s+enzymes?)\b', re.IGNORECASE), "troponin"),
        (re.compile(r'\b(CRP|C-reactive\s+protein)\b', re.IGNORECASE), "CRP"),
        (re.compile(r'\b(ESR|erythrocyte\s+sedimentation\s+rate|sed\s+rate)\b', re.IGNORECASE), "ESR"),
        (re.compile(r'\b(ABG|arterial\s+blood\s+gas)\b', re.IGNORECASE), "ABG"),
        (re.compile(r'\b(creatinine|Cr)\b', re.IGNORECASE), "creatinine"),
        (re.compile(r'\b(BUN|blood\s+urea\s+nitrogen)\b', re.IGNORECASE), "BUN"),
        (re.compile(r'\b(GFR|glomerular\s+filtration\s+rate)\b', re.IGNORECASE), "GFR"),
    ]

    # Procedure patterns
    PROCEDURE_PATTERNS = [
        (re.compile(r'\b(MRI|magnetic\s+resonance\s+imaging)\b', re.IGNORECASE), "MRI"),
        (re.compile(r'\b(CT\s+scan|CAT\s+scan|computed\s+tomography)\b', re.IGNORECASE), "CT scan"),
        (re.compile(r'\b(X-ray|radiograph)\b', re.IGNORECASE), "X-ray"),
        (re.compile(r'\b(ultrasound|sonogram|US)\b', re.IGNORECASE), "ultrasound"),
        (re.compile(r'\b(EKG|ECG|electrocardiogram)\b', re.IGNORECASE), "ECG"),
        (re.compile(r'\b(echocardiogram|echo)\b', re.IGNORECASE), "echocardiogram"),
        (re.compile(r'\b(colonoscopy)\b', re.IGNORECASE), "colonoscopy"),
        (re.compile(r'\b(endoscopy|EGD)\b', re.IGNORECASE), "endoscopy"),
        (re.compile(r'\b(biopsy)\b', re.IGNORECASE), "biopsy"),
        (re.compile(r'\b(mammogram|mammography)\b', re.IGNORECASE), "mammogram"),
        (re.compile(r'\b(PET\s+scan|positron\s+emission)\b', re.IGNORECASE), "PET scan"),
        (re.compile(r'\b(angiography|angiogram)\b', re.IGNORECASE), "angiography"),
        (re.compile(r'\b(catheterization|cardiac\s+cath)\b', re.IGNORECASE), "catheterization"),
        (re.compile(r'\b(bronchoscopy)\b', re.IGNORECASE), "bronchoscopy"),
        (re.compile(r'\b(lumbar\s+puncture|spinal\s+tap)\b', re.IGNORECASE), "lumbar puncture"),
    ]

    def __init__(self):
        """Initialize the NER extractor with dictionaries."""
        self._conditions = self._load_conditions_dict()
        self._medications = self._load_medications_dict()
        self._anatomy = self._load_anatomy_dict()
        self._symptoms = self._load_symptoms_dict()

    def _load_conditions_dict(self) -> dict[str, str]:
        """Load condition dictionary from JSON file or use built-in defaults."""
        data_path = Path(__file__).parent / "data" / "conditions.json"
        if data_path.exists():
            try:
                with open(data_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load conditions.json: {e}")

        # Built-in conditions dictionary (term -> normalized name)
        return {
            # Cardiovascular
            "hypertension": "hypertension",
            "high blood pressure": "hypertension",
            "htn": "hypertension",
            "hyperlipidemia": "hyperlipidemia",
            "high cholesterol": "hyperlipidemia",
            "coronary artery disease": "coronary artery disease",
            "cad": "coronary artery disease",
            "heart failure": "heart failure",
            "chf": "heart failure",
            "congestive heart failure": "heart failure",
            "atrial fibrillation": "atrial fibrillation",
            "afib": "atrial fibrillation",
            "a-fib": "atrial fibrillation",
            "myocardial infarction": "myocardial infarction",
            "heart attack": "myocardial infarction",
            "mi": "myocardial infarction",
            "angina": "angina",
            "chest pain": "angina",
            "dvt": "deep vein thrombosis",
            "deep vein thrombosis": "deep vein thrombosis",
            "pulmonary embolism": "pulmonary embolism",
            "pe": "pulmonary embolism",

            # Respiratory
            "asthma": "asthma",
            "copd": "chronic obstructive pulmonary disease",
            "chronic obstructive pulmonary disease": "chronic obstructive pulmonary disease",
            "emphysema": "emphysema",
            "pneumonia": "pneumonia",
            "bronchitis": "bronchitis",
            "tuberculosis": "tuberculosis",
            "tb": "tuberculosis",

            # Endocrine
            "diabetes": "diabetes mellitus",
            "diabetes mellitus": "diabetes mellitus",
            "dm": "diabetes mellitus",
            "type 2 diabetes": "type 2 diabetes mellitus",
            "t2dm": "type 2 diabetes mellitus",
            "type 1 diabetes": "type 1 diabetes mellitus",
            "t1dm": "type 1 diabetes mellitus",
            "hypothyroidism": "hypothyroidism",
            "hyperthyroidism": "hyperthyroidism",
            "obesity": "obesity",

            # Neurological
            "stroke": "cerebrovascular accident",
            "cva": "cerebrovascular accident",
            "cerebrovascular accident": "cerebrovascular accident",
            "tia": "transient ischemic attack",
            "transient ischemic attack": "transient ischemic attack",
            "seizure": "seizure disorder",
            "epilepsy": "epilepsy",
            "migraine": "migraine",
            "alzheimer's": "alzheimer's disease",
            "dementia": "dementia",
            "parkinson's": "parkinson's disease",
            "multiple sclerosis": "multiple sclerosis",
            "ms": "multiple sclerosis",

            # Gastrointestinal
            "gerd": "gastroesophageal reflux disease",
            "acid reflux": "gastroesophageal reflux disease",
            "gastroesophageal reflux": "gastroesophageal reflux disease",
            "peptic ulcer": "peptic ulcer disease",
            "ibs": "irritable bowel syndrome",
            "irritable bowel syndrome": "irritable bowel syndrome",
            "crohn's disease": "crohn's disease",
            "ulcerative colitis": "ulcerative colitis",
            "hepatitis": "hepatitis",
            "cirrhosis": "cirrhosis",
            "pancreatitis": "pancreatitis",

            # Renal
            "chronic kidney disease": "chronic kidney disease",
            "ckd": "chronic kidney disease",
            "kidney failure": "renal failure",
            "renal failure": "renal failure",
            "uti": "urinary tract infection",
            "urinary tract infection": "urinary tract infection",
            "kidney stones": "nephrolithiasis",
            "nephrolithiasis": "nephrolithiasis",

            # Musculoskeletal
            "osteoarthritis": "osteoarthritis",
            "oa": "osteoarthritis",
            "rheumatoid arthritis": "rheumatoid arthritis",
            "ra": "rheumatoid arthritis",
            "osteoporosis": "osteoporosis",
            "gout": "gout",
            "fibromyalgia": "fibromyalgia",
            "back pain": "back pain",
            "low back pain": "low back pain",

            # Psychiatric
            "depression": "major depressive disorder",
            "major depression": "major depressive disorder",
            "anxiety": "anxiety disorder",
            "anxiety disorder": "anxiety disorder",
            "bipolar disorder": "bipolar disorder",
            "schizophrenia": "schizophrenia",
            "ptsd": "post-traumatic stress disorder",
            "adhd": "attention deficit hyperactivity disorder",
            "insomnia": "insomnia",

            # Cancer
            "cancer": "malignancy",
            "malignancy": "malignancy",
            "breast cancer": "breast cancer",
            "lung cancer": "lung cancer",
            "colon cancer": "colon cancer",
            "prostate cancer": "prostate cancer",
            "leukemia": "leukemia",
            "lymphoma": "lymphoma",

            # Infectious
            "covid-19": "COVID-19",
            "covid": "COVID-19",
            "influenza": "influenza",
            "flu": "influenza",
            "hiv": "HIV infection",
            "aids": "acquired immunodeficiency syndrome",

            # Allergic/Immune
            "allergies": "allergies",
            "allergic rhinitis": "allergic rhinitis",
            "hay fever": "allergic rhinitis",
            "anaphylaxis": "anaphylaxis",
            "lupus": "systemic lupus erythematosus",
            "sle": "systemic lupus erythematosus",
        }

    def _load_medications_dict(self) -> dict[str, str]:
        """Load medication dictionary from JSON file or use built-in defaults."""
        data_path = Path(__file__).parent / "data" / "medications.json"
        if data_path.exists():
            try:
                with open(data_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load medications.json: {e}")

        # Built-in medications dictionary (term -> normalized/generic name)
        return {
            # Cardiovascular
            "aspirin": "aspirin",
            "asa": "aspirin",
            "lisinopril": "lisinopril",
            "enalapril": "enalapril",
            "ramipril": "ramipril",
            "losartan": "losartan",
            "valsartan": "valsartan",
            "metoprolol": "metoprolol",
            "atenolol": "atenolol",
            "carvedilol": "carvedilol",
            "amlodipine": "amlodipine",
            "norvasc": "amlodipine",
            "diltiazem": "diltiazem",
            "verapamil": "verapamil",
            "furosemide": "furosemide",
            "lasix": "furosemide",
            "hydrochlorothiazide": "hydrochlorothiazide",
            "hctz": "hydrochlorothiazide",
            "spironolactone": "spironolactone",
            "atorvastatin": "atorvastatin",
            "lipitor": "atorvastatin",
            "simvastatin": "simvastatin",
            "rosuvastatin": "rosuvastatin",
            "crestor": "rosuvastatin",
            "pravastatin": "pravastatin",
            "warfarin": "warfarin",
            "coumadin": "warfarin",
            "apixaban": "apixaban",
            "eliquis": "apixaban",
            "rivaroxaban": "rivaroxaban",
            "xarelto": "rivaroxaban",
            "clopidogrel": "clopidogrel",
            "plavix": "clopidogrel",
            "nitroglycerin": "nitroglycerin",
            "digoxin": "digoxin",
            "amiodarone": "amiodarone",

            # Diabetes
            "metformin": "metformin",
            "glucophage": "metformin",
            "glipizide": "glipizide",
            "glyburide": "glyburide",
            "glimepiride": "glimepiride",
            "insulin": "insulin",
            "humalog": "insulin lispro",
            "novolog": "insulin aspart",
            "lantus": "insulin glargine",
            "levemir": "insulin detemir",
            "empagliflozin": "empagliflozin",
            "jardiance": "empagliflozin",
            "dapagliflozin": "dapagliflozin",
            "farxiga": "dapagliflozin",
            "semaglutide": "semaglutide",
            "ozempic": "semaglutide",
            "wegovy": "semaglutide",
            "liraglutide": "liraglutide",
            "victoza": "liraglutide",
            "sitagliptin": "sitagliptin",
            "januvia": "sitagliptin",

            # Pain/Anti-inflammatory
            "acetaminophen": "acetaminophen",
            "tylenol": "acetaminophen",
            "ibuprofen": "ibuprofen",
            "advil": "ibuprofen",
            "motrin": "ibuprofen",
            "naproxen": "naproxen",
            "aleve": "naproxen",
            "meloxicam": "meloxicam",
            "celecoxib": "celecoxib",
            "celebrex": "celecoxib",
            "tramadol": "tramadol",
            "ultram": "tramadol",
            "hydrocodone": "hydrocodone",
            "vicodin": "hydrocodone/acetaminophen",
            "oxycodone": "oxycodone",
            "percocet": "oxycodone/acetaminophen",
            "morphine": "morphine",
            "fentanyl": "fentanyl",
            "gabapentin": "gabapentin",
            "neurontin": "gabapentin",
            "pregabalin": "pregabalin",
            "lyrica": "pregabalin",

            # Respiratory
            "albuterol": "albuterol",
            "ventolin": "albuterol",
            "proair": "albuterol",
            "ipratropium": "ipratropium",
            "atrovent": "ipratropium",
            "fluticasone": "fluticasone",
            "flovent": "fluticasone",
            "budesonide": "budesonide",
            "pulmicort": "budesonide",
            "montelukast": "montelukast",
            "singulair": "montelukast",
            "prednisone": "prednisone",
            "prednisolone": "prednisolone",
            "dexamethasone": "dexamethasone",

            # GI
            "omeprazole": "omeprazole",
            "prilosec": "omeprazole",
            "pantoprazole": "pantoprazole",
            "protonix": "pantoprazole",
            "esomeprazole": "esomeprazole",
            "nexium": "esomeprazole",
            "famotidine": "famotidine",
            "pepcid": "famotidine",
            "ranitidine": "ranitidine",
            "ondansetron": "ondansetron",
            "zofran": "ondansetron",
            "metoclopramide": "metoclopramide",
            "reglan": "metoclopramide",

            # Psychiatric
            "sertraline": "sertraline",
            "zoloft": "sertraline",
            "fluoxetine": "fluoxetine",
            "prozac": "fluoxetine",
            "escitalopram": "escitalopram",
            "lexapro": "escitalopram",
            "citalopram": "citalopram",
            "celexa": "citalopram",
            "paroxetine": "paroxetine",
            "paxil": "paroxetine",
            "venlafaxine": "venlafaxine",
            "effexor": "venlafaxine",
            "duloxetine": "duloxetine",
            "cymbalta": "duloxetine",
            "bupropion": "bupropion",
            "wellbutrin": "bupropion",
            "trazodone": "trazodone",
            "mirtazapine": "mirtazapine",
            "remeron": "mirtazapine",
            "alprazolam": "alprazolam",
            "xanax": "alprazolam",
            "lorazepam": "lorazepam",
            "ativan": "lorazepam",
            "clonazepam": "clonazepam",
            "klonopin": "clonazepam",
            "diazepam": "diazepam",
            "valium": "diazepam",
            "zolpidem": "zolpidem",
            "ambien": "zolpidem",
            "quetiapine": "quetiapine",
            "seroquel": "quetiapine",
            "aripiprazole": "aripiprazole",
            "abilify": "aripiprazole",

            # Antibiotics
            "amoxicillin": "amoxicillin",
            "augmentin": "amoxicillin/clavulanate",
            "azithromycin": "azithromycin",
            "zithromax": "azithromycin",
            "z-pack": "azithromycin",
            "ciprofloxacin": "ciprofloxacin",
            "cipro": "ciprofloxacin",
            "levofloxacin": "levofloxacin",
            "levaquin": "levofloxacin",
            "doxycycline": "doxycycline",
            "metronidazole": "metronidazole",
            "flagyl": "metronidazole",
            "cephalexin": "cephalexin",
            "keflex": "cephalexin",
            "trimethoprim-sulfamethoxazole": "trimethoprim-sulfamethoxazole",
            "bactrim": "trimethoprim-sulfamethoxazole",

            # Thyroid
            "levothyroxine": "levothyroxine",
            "synthroid": "levothyroxine",
            "methimazole": "methimazole",
            "propylthiouracil": "propylthiouracil",

            # Allergy
            "cetirizine": "cetirizine",
            "zyrtec": "cetirizine",
            "loratadine": "loratadine",
            "claritin": "loratadine",
            "fexofenadine": "fexofenadine",
            "allegra": "fexofenadine",
            "diphenhydramine": "diphenhydramine",
            "benadryl": "diphenhydramine",
        }

    def _load_anatomy_dict(self) -> dict[str, str]:
        """Load anatomy/body part dictionary."""
        return {
            # Head
            "head": "head",
            "skull": "skull",
            "brain": "brain",
            "eye": "eye",
            "eyes": "eyes",
            "ear": "ear",
            "ears": "ears",
            "nose": "nose",
            "mouth": "mouth",
            "throat": "throat",
            "neck": "neck",

            # Chest
            "chest": "chest",
            "thorax": "thorax",
            "heart": "heart",
            "lungs": "lungs",
            "lung": "lung",
            "breast": "breast",
            "ribs": "ribs",

            # Abdomen
            "abdomen": "abdomen",
            "stomach": "stomach",
            "liver": "liver",
            "gallbladder": "gallbladder",
            "pancreas": "pancreas",
            "spleen": "spleen",
            "intestine": "intestine",
            "colon": "colon",
            "appendix": "appendix",
            "kidney": "kidney",
            "kidneys": "kidneys",
            "bladder": "bladder",

            # Extremities
            "arm": "arm",
            "arms": "arms",
            "shoulder": "shoulder",
            "elbow": "elbow",
            "wrist": "wrist",
            "hand": "hand",
            "hands": "hands",
            "finger": "finger",
            "fingers": "fingers",
            "leg": "leg",
            "legs": "legs",
            "hip": "hip",
            "thigh": "thigh",
            "knee": "knee",
            "ankle": "ankle",
            "foot": "foot",
            "feet": "feet",
            "toe": "toe",
            "toes": "toes",

            # Back/Spine
            "back": "back",
            "spine": "spine",
            "vertebra": "vertebra",
            "lumbar": "lumbar spine",
            "cervical": "cervical spine",
            "thoracic": "thoracic spine",

            # Other
            "skin": "skin",
            "bone": "bone",
            "joint": "joint",
            "muscle": "muscle",
            "tendon": "tendon",
            "ligament": "ligament",
            "nerve": "nerve",
            "blood vessel": "blood vessel",
            "artery": "artery",
            "vein": "vein",
            "lymph node": "lymph node",
        }

    def _load_symptoms_dict(self) -> dict[str, str]:
        """Load symptoms dictionary."""
        return {
            # General
            "fatigue": "fatigue",
            "tiredness": "fatigue",
            "weakness": "weakness",
            "fever": "fever",
            "chills": "chills",
            "sweating": "diaphoresis",
            "weight loss": "weight loss",
            "weight gain": "weight gain",
            "malaise": "malaise",

            # Pain
            "pain": "pain",
            "headache": "headache",
            "chest pain": "chest pain",
            "abdominal pain": "abdominal pain",
            "back pain": "back pain",
            "joint pain": "joint pain",
            "muscle pain": "myalgia",

            # Respiratory
            "cough": "cough",
            "shortness of breath": "dyspnea",
            "dyspnea": "dyspnea",
            "wheezing": "wheezing",
            "sputum": "sputum production",

            # GI
            "nausea": "nausea",
            "vomiting": "vomiting",
            "diarrhea": "diarrhea",
            "constipation": "constipation",
            "bloating": "bloating",
            "heartburn": "heartburn",

            # Cardiac
            "palpitations": "palpitations",
            "chest tightness": "chest tightness",
            "edema": "edema",
            "swelling": "edema",

            # Neurological
            "dizziness": "dizziness",
            "vertigo": "vertigo",
            "numbness": "numbness",
            "tingling": "paresthesia",
            "confusion": "confusion",
            "memory loss": "memory impairment",

            # Skin
            "rash": "rash",
            "itching": "pruritus",
            "bruising": "ecchymosis",

            # Sleep
            "insomnia": "insomnia",
            "sleep problems": "sleep disturbance",
        }

    def extract(self, text: str) -> list[MedicalEntity]:
        """Extract all medical entities from text.

        Args:
            text: Input text to analyze

        Returns:
            List of extracted MedicalEntity objects
        """
        entities = []

        # Extract pattern-based entities
        entities.extend(self._extract_dosages(text))
        entities.extend(self._extract_vitals(text))
        entities.extend(self._extract_frequencies(text))
        entities.extend(self._extract_routes(text))
        entities.extend(self._extract_lab_tests(text))
        entities.extend(self._extract_procedures(text))

        # Extract dictionary-based entities
        entities.extend(self._extract_conditions(text))
        entities.extend(self._extract_medications(text))
        entities.extend(self._extract_anatomy(text))
        entities.extend(self._extract_symptoms(text))

        # Deduplicate overlapping entities
        return self._deduplicate(entities)

    def _extract_dosages(self, text: str) -> list[MedicalEntity]:
        """Extract dosage mentions from text."""
        entities = []
        for match in self.DOSAGE_PATTERN.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.DOSAGE,
                normalized_name=match.group(0).lower(),
                confidence=0.95,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"value": match.group(1), "unit": match.group(2)}
            ))
        return entities

    def _extract_vitals(self, text: str) -> list[MedicalEntity]:
        """Extract vital sign mentions from text."""
        entities = []

        # Blood pressure
        for match in self.BP_PATTERN.finditer(text):
            systolic, diastolic = match.group(1), match.group(2)
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.VITAL_SIGN,
                normalized_name=f"blood pressure {systolic}/{diastolic}",
                confidence=0.9,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"type": "blood_pressure", "systolic": systolic, "diastolic": diastolic}
            ))

        # Heart rate
        for match in self.HR_PATTERN.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.VITAL_SIGN,
                normalized_name=f"heart rate {match.group(1)}",
                confidence=0.9,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"type": "heart_rate", "value": match.group(1)}
            ))

        # Temperature
        for match in self.TEMP_PATTERN.finditer(text):
            value = match.group(1)
            unit = match.group(2) or ("F" if float(value) > 50 else "C")
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.VITAL_SIGN,
                normalized_name=f"temperature {value}°{unit}",
                confidence=0.85,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"type": "temperature", "value": value, "unit": unit}
            ))

        # SpO2
        for match in self.SPO2_PATTERN.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.VITAL_SIGN,
                normalized_name=f"oxygen saturation {match.group(1)}%",
                confidence=0.9,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"type": "spo2", "value": match.group(1)}
            ))

        # Respiratory rate
        for match in self.RR_PATTERN.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.VITAL_SIGN,
                normalized_name=f"respiratory rate {match.group(1)}",
                confidence=0.9,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"type": "respiratory_rate", "value": match.group(1)}
            ))

        # Weight
        for match in self.WEIGHT_PATTERN.finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type=MedicalEntityType.VITAL_SIGN,
                normalized_name=f"weight {match.group(1)} {match.group(2)}",
                confidence=0.85,
                start_pos=match.start(),
                end_pos=match.end(),
                metadata={"type": "weight", "value": match.group(1), "unit": match.group(2)}
            ))

        return entities

    def _extract_frequencies(self, text: str) -> list[MedicalEntity]:
        """Extract medication frequency mentions from text."""
        entities = []
        for pattern, normalized in self.FREQUENCY_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type=MedicalEntityType.FREQUENCY,
                    normalized_name=normalized,
                    confidence=0.9,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        return entities

    def _extract_routes(self, text: str) -> list[MedicalEntity]:
        """Extract medication route mentions from text."""
        entities = []
        for pattern, normalized in self.ROUTE_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type=MedicalEntityType.ROUTE,
                    normalized_name=normalized,
                    confidence=0.9,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        return entities

    def _extract_lab_tests(self, text: str) -> list[MedicalEntity]:
        """Extract lab test mentions from text."""
        entities = []
        for pattern, normalized in self.LAB_TEST_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type=MedicalEntityType.LAB_TEST,
                    normalized_name=normalized,
                    confidence=0.85,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        return entities

    def _extract_procedures(self, text: str) -> list[MedicalEntity]:
        """Extract procedure mentions from text."""
        entities = []
        for pattern, normalized in self.PROCEDURE_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type=MedicalEntityType.PROCEDURE,
                    normalized_name=normalized,
                    confidence=0.85,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        return entities

    def _extract_from_dict(
        self,
        text: str,
        dictionary: dict[str, str],
        entity_type: MedicalEntityType
    ) -> list[MedicalEntity]:
        """Extract entities using a dictionary lookup.

        Args:
            text: Input text
            dictionary: Term -> normalized name mapping
            entity_type: Type of entity being extracted

        Returns:
            List of extracted entities
        """
        entities = []
        text_lower = text.lower()

        # Sort by length (longest first) to match multi-word terms before single words
        sorted_terms = sorted(dictionary.keys(), key=len, reverse=True)

        # Track which positions have already been matched
        matched_positions = set()

        for term in sorted_terms:
            term_lower = term.lower()
            # Use word boundary regex for matching
            pattern = re.compile(r'\b' + re.escape(term_lower) + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text_lower):
                # Skip if this position already has a match
                if any(pos in matched_positions for pos in range(match.start(), match.end())):
                    continue

                # Mark positions as matched
                for pos in range(match.start(), match.end()):
                    matched_positions.add(pos)

                entities.append(MedicalEntity(
                    text=text[match.start():match.end()],
                    entity_type=entity_type,
                    normalized_name=dictionary[term],
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        return entities

    def _extract_conditions(self, text: str) -> list[MedicalEntity]:
        """Extract condition/diagnosis mentions from text."""
        return self._extract_from_dict(text, self._conditions, MedicalEntityType.CONDITION)

    def _extract_medications(self, text: str) -> list[MedicalEntity]:
        """Extract medication mentions from text."""
        return self._extract_from_dict(text, self._medications, MedicalEntityType.MEDICATION)

    def _extract_anatomy(self, text: str) -> list[MedicalEntity]:
        """Extract anatomy/body part mentions from text."""
        return self._extract_from_dict(text, self._anatomy, MedicalEntityType.ANATOMY)

    def _extract_symptoms(self, text: str) -> list[MedicalEntity]:
        """Extract symptom mentions from text."""
        return self._extract_from_dict(text, self._symptoms, MedicalEntityType.SYMPTOM)

    def _deduplicate(self, entities: list[MedicalEntity]) -> list[MedicalEntity]:
        """Remove duplicate or overlapping entities.

        Prefers entities with higher confidence and longer text matches.
        """
        if not entities:
            return []

        # Sort by position, then by length (longer first), then by confidence
        sorted_entities = sorted(
            entities,
            key=lambda e: (e.start_pos, -len(e.text), -e.confidence)
        )

        result = []
        last_end = -1

        for entity in sorted_entities:
            # Skip if this entity overlaps with a previous one
            if entity.start_pos < last_end:
                continue

            result.append(entity)
            last_end = entity.end_pos

        return result

    def extract_with_ml_classification(
        self,
        text: str,
        context: str = "",
        use_deduplication: bool = True,
        document_id: str = ""
    ) -> list[MedicalEntity]:
        """Extract entities with ML-based type classification.

        Uses the MLEntityClassifier for more accurate entity type detection
        and the EntityDeduplicator for cross-document linking.

        Args:
            text: Input text to analyze
            context: Surrounding context for better classification
            use_deduplication: Whether to use cross-document deduplication
            document_id: Document ID for deduplication tracking

        Returns:
            List of extracted MedicalEntity objects with ML-enhanced types
        """
        # Get base entities using rule-based extraction
        entities = self.extract(text)

        if not entities:
            return entities

        # Try to use ML classifier for type validation/enhancement
        try:
            from rag.entity_classifier import get_entity_classifier
            classifier = get_entity_classifier()

            for entity in entities:
                # Get context around the entity
                entity_context = text[
                    max(0, entity.start_pos - 100):
                    min(len(text), entity.end_pos + 100)
                ] if not context else context

                # Classify with ML
                result = classifier.classify(entity.text, entity_context)

                # Only update if ML has higher confidence
                if result.confidence > entity.confidence:
                    # Map EntityType to MedicalEntityType
                    ml_type = self._map_entity_type(result.predicted_type)
                    if ml_type:
                        entity.entity_type = ml_type
                        entity.confidence = result.confidence
                        entity.metadata["ml_classified"] = True
                        entity.metadata["ml_alternatives"] = [
                            (str(t.value), c) for t, c in result.alternative_types
                        ]

        except Exception as e:
            logger.debug(f"ML classification not available: {e}")

        # Try to use entity deduplicator for cross-document linking
        if use_deduplication:
            try:
                from rag.entity_deduplicator import get_entity_deduplicator
                from rag.graph_data_provider import EntityType

                deduplicator = get_entity_deduplicator()

                for entity in entities:
                    # Map to graph EntityType
                    graph_type = self._map_to_graph_type(entity.entity_type)
                    if graph_type:
                        cluster = deduplicator.deduplicate(
                            entity.text,
                            graph_type,
                            document_id
                        )
                        entity.normalized_name = cluster.canonical_name
                        entity.metadata["cluster_id"] = cluster.canonical_id
                        entity.metadata["mention_count"] = cluster.mention_count

            except Exception as e:
                logger.debug(f"Entity deduplication not available: {e}")

        return entities

    def _map_entity_type(self, entity_type) -> Optional[MedicalEntityType]:
        """Map from graph EntityType to MedicalEntityType.

        Args:
            entity_type: EntityType from graph_data_provider

        Returns:
            Corresponding MedicalEntityType or None
        """
        try:
            from rag.graph_data_provider import EntityType

            type_map = {
                EntityType.MEDICATION: MedicalEntityType.MEDICATION,
                EntityType.CONDITION: MedicalEntityType.CONDITION,
                EntityType.SYMPTOM: MedicalEntityType.SYMPTOM,
                EntityType.PROCEDURE: MedicalEntityType.PROCEDURE,
                EntityType.LAB_TEST: MedicalEntityType.LAB_TEST,
                EntityType.ANATOMY: MedicalEntityType.ANATOMY,
            }
            return type_map.get(entity_type)
        except Exception:
            return None

    def _map_to_graph_type(self, medical_type: MedicalEntityType):
        """Map from MedicalEntityType to graph EntityType.

        Args:
            medical_type: MedicalEntityType

        Returns:
            Corresponding graph EntityType or None
        """
        try:
            from rag.graph_data_provider import EntityType

            type_map = {
                MedicalEntityType.MEDICATION: EntityType.MEDICATION,
                MedicalEntityType.CONDITION: EntityType.CONDITION,
                MedicalEntityType.SYMPTOM: EntityType.SYMPTOM,
                MedicalEntityType.PROCEDURE: EntityType.PROCEDURE,
                MedicalEntityType.LAB_TEST: EntityType.LAB_TEST,
                MedicalEntityType.ANATOMY: EntityType.ANATOMY,
            }
            return type_map.get(medical_type)
        except Exception:
            return None

    def extract_to_dict(self, text: str) -> dict[str, list[dict]]:
        """Extract entities and return as dictionary grouped by type.

        Args:
            text: Input text to analyze

        Returns:
            Dictionary with entity types as keys and lists of entity dicts as values
        """
        entities = self.extract(text)

        result = {}
        for entity in entities:
            type_key = entity.entity_type.value
            if type_key not in result:
                result[type_key] = []
            result[type_key].append(entity.to_dict())

        return result


# Singleton instance
_ner_extractor: Optional[MedicalNERExtractor] = None


def get_medical_ner_extractor() -> MedicalNERExtractor:
    """Get the global medical NER extractor instance.

    Returns:
        MedicalNERExtractor instance
    """
    global _ner_extractor
    if _ner_extractor is None:
        _ner_extractor = MedicalNERExtractor()
    return _ner_extractor


def extract_medical_entities(text: str) -> list[MedicalEntity]:
    """Convenience function to extract medical entities from text.

    Args:
        text: Input text to analyze

    Returns:
        List of extracted MedicalEntity objects
    """
    extractor = get_medical_ner_extractor()
    return extractor.extract(text)


def extract_medical_entities_ml(
    text: str,
    context: str = "",
    use_deduplication: bool = True,
    document_id: str = ""
) -> list[MedicalEntity]:
    """Extract medical entities with ML-based classification enhancement.

    Uses the MLEntityClassifier for improved type detection and
    EntityDeduplicator for cross-document entity linking.

    Args:
        text: Input text to analyze
        context: Surrounding context for better classification
        use_deduplication: Whether to use cross-document deduplication
        document_id: Document ID for deduplication tracking

    Returns:
        List of extracted MedicalEntity objects with ML-enhanced types
    """
    extractor = get_medical_ner_extractor()
    return extractor.extract_with_ml_classification(
        text, context, use_deduplication, document_id
    )

# Alias for backwards compatibility
get_ner_extractor = get_medical_ner_extractor
