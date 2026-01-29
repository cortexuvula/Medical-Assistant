"""
Generate entity type prototype embeddings.

This script generates average embeddings for each entity type
from a list of example terms. These prototypes are used by
MLEntityClassifier for semantic entity classification.

Usage:
    python -m src.rag.data.generate_prototypes
"""

import json
import logging
from datetime import datetime

from utils.structured_logging import get_logger
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

# Example terms for each entity type
# These are used to generate prototype embeddings
ENTITY_TYPE_EXAMPLES = {
    "medication": [
        "metoprolol 50mg tablet",
        "lisinopril blood pressure medication",
        "atorvastatin cholesterol drug",
        "metformin diabetes pill",
        "aspirin antiplatelet therapy",
        "omeprazole acid reducer",
        "levothyroxine thyroid hormone",
        "albuterol bronchodilator inhaler",
        "insulin glargine injection",
        "warfarin anticoagulant",
        "prednisone corticosteroid",
        "gabapentin nerve pain medication",
        "sertraline antidepressant SSRI",
        "amlodipine calcium channel blocker",
        "furosemide diuretic water pill",
        "clopidogrel blood thinner",
        "pantoprazole proton pump inhibitor",
        "tramadol pain reliever opioid",
        "losartan ARB antihypertensive",
        "montelukast asthma controller",
    ],
    "condition": [
        "hypertension high blood pressure",
        "type 2 diabetes mellitus",
        "coronary artery disease CAD",
        "congestive heart failure CHF",
        "chronic obstructive pulmonary disease COPD",
        "atrial fibrillation arrhythmia",
        "chronic kidney disease CKD",
        "major depressive disorder depression",
        "osteoarthritis degenerative joint disease",
        "hyperlipidemia high cholesterol",
        "gastroesophageal reflux disease GERD",
        "hypothyroidism underactive thyroid",
        "asthma reactive airway disease",
        "anxiety disorder generalized anxiety",
        "pneumonia lung infection",
        "urinary tract infection UTI",
        "cerebrovascular accident stroke CVA",
        "myocardial infarction heart attack MI",
        "deep vein thrombosis DVT blood clot",
        "rheumatoid arthritis autoimmune",
    ],
    "symptom": [
        "chest pain angina discomfort",
        "shortness of breath dyspnea",
        "headache cephalgia",
        "nausea feeling sick to stomach",
        "fatigue tiredness exhaustion",
        "dizziness lightheadedness vertigo",
        "abdominal pain stomach ache",
        "cough productive nonproductive",
        "swelling edema fluid retention",
        "fever elevated temperature pyrexia",
        "palpitations racing heart",
        "numbness tingling paresthesia",
        "weakness muscle loss strength",
        "back pain lumbar discomfort",
        "joint pain arthralgia",
        "rash skin eruption dermatitis",
        "insomnia sleep difficulty",
        "weight loss unintentional",
        "blurred vision visual changes",
        "constipation bowel irregularity",
    ],
    "procedure": [
        "coronary artery bypass graft CABG surgery",
        "cardiac catheterization angiogram",
        "colonoscopy bowel examination",
        "MRI magnetic resonance imaging scan",
        "CT computed tomography scan",
        "echocardiogram cardiac ultrasound echo",
        "EKG ECG electrocardiogram heart tracing",
        "endoscopy EGD upper GI scope",
        "biopsy tissue sampling",
        "X-ray radiograph imaging",
        "ultrasound sonogram imaging",
        "PET scan positron emission tomography",
        "laparoscopy minimally invasive surgery",
        "appendectomy appendix removal",
        "cholecystectomy gallbladder removal",
        "total knee replacement arthroplasty",
        "hip replacement orthopedic surgery",
        "lumbar puncture spinal tap",
        "bronchoscopy airway examination",
        "mammogram breast imaging screening",
    ],
    "lab_test": [
        "complete blood count CBC hemogram",
        "basic metabolic panel BMP chemistry",
        "comprehensive metabolic panel CMP",
        "lipid panel cholesterol triglycerides",
        "hemoglobin A1c HbA1c glycated",
        "thyroid stimulating hormone TSH",
        "liver function tests LFTs hepatic panel",
        "prothrombin time PT INR coagulation",
        "urinalysis UA urine test",
        "blood urea nitrogen BUN kidney",
        "creatinine renal function",
        "glomerular filtration rate GFR",
        "troponin cardiac enzyme marker",
        "BNP natriuretic peptide heart failure",
        "C-reactive protein CRP inflammation",
        "erythrocyte sedimentation rate ESR",
        "arterial blood gas ABG",
        "PSA prostate specific antigen",
        "vitamin D 25-hydroxy level",
        "ferritin iron stores anemia",
    ],
    "anatomy": [
        "heart cardiac muscle organ",
        "lung pulmonary respiratory organ",
        "liver hepatic organ",
        "kidney renal organ",
        "brain cerebral nervous system",
        "stomach gastric organ",
        "colon large intestine bowel",
        "spine vertebral column backbone",
        "femur thigh bone leg",
        "coronary artery cardiac vessel",
        "carotid artery neck blood vessel",
        "aorta great vessel heart",
        "pancreas digestive endocrine gland",
        "thyroid gland neck endocrine",
        "prostate gland male reproductive",
        "shoulder joint glenohumeral",
        "knee joint patellofemoral",
        "hip joint acetabulum femoral",
        "esophagus swallowing tube",
        "gallbladder biliary organ",
    ],
}


def generate_prototypes(output_path: Path = None):
    """Generate prototype embeddings for each entity type.

    Args:
        output_path: Path to save the prototypes JSON file
    """
    if output_path is None:
        output_path = Path(__file__).parent / "entity_prototypes.json"

    try:
        from rag.embedding_manager import EmbeddingManager
    except ImportError:
        logger.error("Could not import EmbeddingManager. Make sure you're running from project root.")
        return

    logger.info("Initializing embedding manager...")
    embedding_manager = EmbeddingManager()

    prototypes = {}

    for entity_type, examples in ENTITY_TYPE_EXAMPLES.items():
        logger.info(f"Generating prototype for {entity_type} ({len(examples)} examples)...")

        try:
            # Generate embeddings for all examples
            response = embedding_manager.generate_embeddings(examples)
            embeddings = response.embeddings

            if not embeddings:
                logger.warning(f"No embeddings generated for {entity_type}")
                prototypes[entity_type] = []
                continue

            # Calculate centroid (average) embedding
            num_dims = len(embeddings[0])
            centroid = [0.0] * num_dims

            for emb in embeddings:
                for i, val in enumerate(emb):
                    centroid[i] += val

            centroid = [v / len(embeddings) for v in centroid]

            # Normalize the centroid
            import math
            norm = math.sqrt(sum(v * v for v in centroid))
            if norm > 0:
                centroid = [v / norm for v in centroid]

            prototypes[entity_type] = centroid
            logger.info(f"  Generated {num_dims}-dimensional prototype")

        except Exception as e:
            logger.error(f"Failed to generate prototype for {entity_type}: {e}")
            prototypes[entity_type] = []

    # Save prototypes
    output_data = {
        "_description": "Entity type prototype embeddings for ML classification",
        "_version": "1.0",
        "_generated": datetime.now().isoformat(),
        "_model": embedding_manager.model,
        "_dimensions": embedding_manager.dimensions,
        **prototypes
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"Saved prototypes to {output_path}")


if __name__ == "__main__":
    generate_prototypes()
