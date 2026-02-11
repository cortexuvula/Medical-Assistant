"""
Lightweight Medical Code Lookup for Knowledge Graph Enrichment.

Best-effort term-to-code mapper for common medical conditions and medications.
Uses static dictionaries with ~100 common mappings each.
Non-blocking: returns None for unknown terms.

Code systems:
- ICD-10-CM for conditions/diagnoses
- RxNorm concept names for medications
"""

from typing import Optional


# Common ICD-10-CM codes for frequently encountered conditions
ICD10_CODES: dict[str, str] = {
    # Cardiovascular
    "hypertension": "I10",
    "essential hypertension": "I10",
    "htn": "I10",
    "heart failure": "I50.9",
    "chf": "I50.9",
    "congestive heart failure": "I50.9",
    "atrial fibrillation": "I48.91",
    "afib": "I48.91",
    "coronary artery disease": "I25.10",
    "cad": "I25.10",
    "myocardial infarction": "I21.9",
    "mi": "I21.9",
    "heart attack": "I21.9",
    "deep vein thrombosis": "I82.90",
    "dvt": "I82.90",
    "pulmonary embolism": "I26.99",
    "pe": "I26.99",
    "hyperlipidemia": "E78.5",
    "aortic stenosis": "I35.0",
    # Endocrine
    "diabetes mellitus": "E11.9",
    "diabetes": "E11.9",
    "type 2 diabetes": "E11.9",
    "t2dm": "E11.9",
    "dm": "E11.9",
    "type 1 diabetes": "E10.9",
    "t1dm": "E10.9",
    "diabetic ketoacidosis": "E13.10",
    "dka": "E13.10",
    "hypothyroidism": "E03.9",
    "hyperthyroidism": "E05.90",
    "obesity": "E66.9",
    # Respiratory
    "copd": "J44.1",
    "chronic obstructive pulmonary disease": "J44.1",
    "asthma": "J45.909",
    "pneumonia": "J18.9",
    "pna": "J18.9",
    "acute respiratory distress syndrome": "J80",
    "ards": "J80",
    "upper respiratory infection": "J06.9",
    "uri": "J06.9",
    "tuberculosis": "A15.9",
    "tb": "A15.9",
    # Neurological
    "stroke": "I63.9",
    "cva": "I63.9",
    "cerebrovascular accident": "I63.9",
    "transient ischemic attack": "G45.9",
    "tia": "G45.9",
    "epilepsy": "G40.909",
    "seizure": "R56.9",
    "migraine": "G43.909",
    "alzheimer disease": "G30.9",
    "parkinson disease": "G20",
    "multiple sclerosis": "G35",
    "ms": "G35",
    # Gastrointestinal
    "gerd": "K21.0",
    "gastroesophageal reflux": "K21.0",
    "peptic ulcer": "K27.9",
    "cirrhosis": "K74.60",
    "hepatitis": "K73.9",
    "crohn disease": "K50.90",
    "ulcerative colitis": "K51.90",
    "ibs": "K58.9",
    "irritable bowel syndrome": "K58.9",
    # Renal
    "chronic kidney disease": "N18.9",
    "ckd": "N18.9",
    "acute kidney injury": "N17.9",
    "aki": "N17.9",
    "end stage renal disease": "N18.6",
    "esrd": "N18.6",
    # Psychiatric
    "depression": "F32.9",
    "major depressive disorder": "F32.9",
    "mdd": "F32.9",
    "anxiety": "F41.9",
    "generalized anxiety disorder": "F41.1",
    "gad": "F41.1",
    "bipolar disorder": "F31.9",
    "schizophrenia": "F20.9",
    "ptsd": "F43.10",
    # Musculoskeletal
    "osteoarthritis": "M19.90",
    "rheumatoid arthritis": "M06.9",
    "osteoporosis": "M81.0",
    "gout": "M10.9",
    "back pain": "M54.5",
    # Infectious
    "sepsis": "A41.9",
    "urinary tract infection": "N39.0",
    "uti": "N39.0",
    "cellulitis": "L03.90",
    "hiv": "B20",
    # Oncology
    "breast cancer": "C50.919",
    "lung cancer": "C34.90",
    "colon cancer": "C18.9",
    "prostate cancer": "C61",
    # Other
    "anemia": "D64.9",
    "iron deficiency anemia": "D50.9",
}


# Common medication names mapped to RxNorm-style concept names
RXNORM_CODES: dict[str, str] = {
    # Cardiovascular
    "metoprolol": "RxNorm:6918",
    "lisinopril": "RxNorm:29046",
    "amlodipine": "RxNorm:17767",
    "atorvastatin": "RxNorm:83367",
    "rosuvastatin": "RxNorm:301542",
    "losartan": "RxNorm:52175",
    "valsartan": "RxNorm:69749",
    "hydrochlorothiazide": "RxNorm:5487",
    "hctz": "RxNorm:5487",
    "furosemide": "RxNorm:4603",
    "warfarin": "RxNorm:11289",
    "apixaban": "RxNorm:1364430",
    "rivaroxaban": "RxNorm:1114195",
    "clopidogrel": "RxNorm:32968",
    "aspirin": "RxNorm:1191",
    "nitroglycerin": "RxNorm:7417",
    "digoxin": "RxNorm:3407",
    "amiodarone": "RxNorm:703",
    "carvedilol": "RxNorm:20352",
    "spironolactone": "RxNorm:9997",
    # Endocrine
    "metformin": "RxNorm:6809",
    "insulin": "RxNorm:5856",
    "glipizide": "RxNorm:4815",
    "glyburide": "RxNorm:4821",
    "sitagliptin": "RxNorm:593411",
    "empagliflozin": "RxNorm:1545653",
    "semaglutide": "RxNorm:1991302",
    "liraglutide": "RxNorm:475968",
    "levothyroxine": "RxNorm:10582",
    # Pain/Inflammation
    "acetaminophen": "RxNorm:161",
    "ibuprofen": "RxNorm:5640",
    "naproxen": "RxNorm:7258",
    "gabapentin": "RxNorm:25480",
    "pregabalin": "RxNorm:187832",
    "tramadol": "RxNorm:10689",
    "morphine": "RxNorm:7052",
    "oxycodone": "RxNorm:7804",
    "prednisone": "RxNorm:8640",
    "methylprednisolone": "RxNorm:6902",
    # Psychiatric
    "sertraline": "RxNorm:36437",
    "fluoxetine": "RxNorm:4493",
    "escitalopram": "RxNorm:321988",
    "venlafaxine": "RxNorm:39786",
    "duloxetine": "RxNorm:72625",
    "bupropion": "RxNorm:42347",
    "alprazolam": "RxNorm:596",
    "lorazepam": "RxNorm:6470",
    "quetiapine": "RxNorm:51272",
    "aripiprazole": "RxNorm:89013",
    "lithium": "RxNorm:6448",
    # Respiratory
    "albuterol": "RxNorm:435",
    "fluticasone": "RxNorm:41126",
    "montelukast": "RxNorm:88249",
    "ipratropium": "RxNorm:7213",
    "tiotropium": "RxNorm:274783",
    # GI
    "omeprazole": "RxNorm:7646",
    "pantoprazole": "RxNorm:40790",
    "ondansetron": "RxNorm:26225",
    "metoclopramide": "RxNorm:6915",
    # Antibiotics
    "amoxicillin": "RxNorm:723",
    "azithromycin": "RxNorm:18631",
    "ciprofloxacin": "RxNorm:2551",
    "levofloxacin": "RxNorm:82122",
    "doxycycline": "RxNorm:3640",
    "trimethoprim": "RxNorm:10831",
    "vancomycin": "RxNorm:11124",
    "cephalexin": "RxNorm:2231",
    # Anticoagulants (additional)
    "heparin": "RxNorm:5224",
    "enoxaparin": "RxNorm:67108",
}


def lookup_icd10(condition: str) -> Optional[str]:
    """Look up ICD-10-CM code for a medical condition.

    Best-effort lookup using a static dictionary of ~100 common conditions.

    Args:
        condition: Medical condition name or abbreviation

    Returns:
        ICD-10-CM code string, or None if not found
    """
    if not condition:
        return None
    return ICD10_CODES.get(condition.lower().strip())


def lookup_rxnorm(medication: str) -> Optional[str]:
    """Look up RxNorm code for a medication.

    Best-effort lookup using a static dictionary of ~80 common medications.

    Args:
        medication: Medication name

    Returns:
        RxNorm code string, or None if not found
    """
    if not medication:
        return None
    return RXNORM_CODES.get(medication.lower().strip())


def enrich_entity_codes(name: str, entity_type: str) -> dict[str, str]:
    """Look up medical codes for an entity based on its type.

    Args:
        name: Entity name (condition or medication name)
        entity_type: Entity type string (e.g., "condition", "medication")

    Returns:
        Dict of code_system -> code mappings (may be empty)
    """
    codes = {}
    entity_type_lower = entity_type.lower() if entity_type else ""

    if entity_type_lower in ("condition", "symptom", "diagnosis"):
        icd = lookup_icd10(name)
        if icd:
            codes["icd10"] = icd

    if entity_type_lower in ("medication", "drug"):
        rxnorm = lookup_rxnorm(name)
        if rxnorm:
            codes["rxnorm"] = rxnorm

    # Try both if entity type is generic
    if entity_type_lower in ("entity", "unknown", ""):
        icd = lookup_icd10(name)
        if icd:
            codes["icd10"] = icd
        rxnorm = lookup_rxnorm(name)
        if rxnorm:
            codes["rxnorm"] = rxnorm

    return codes
