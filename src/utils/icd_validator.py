"""
ICD Code Validator

Validates ICD-9 and ICD-10 diagnostic codes with pattern matching and
common code lookup. Supports both code systems as requested.

Usage:
    validator = ICDValidator()
    result = validator.validate("J06.9")  # Common cold, ICD-10
    if result.is_valid:
        print(f"Valid {result.code_system}: {result.description}")
"""

import re
from typing import Optional, List, Dict, NamedTuple
from dataclasses import dataclass
from enum import Enum

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ICDCodeSystem(Enum):
    """Supported ICD code systems."""
    ICD9 = "ICD-9"
    ICD10 = "ICD-10"
    UNKNOWN = "Unknown"


@dataclass
class ICDValidationResult:
    """Result of ICD code validation."""
    code: str
    is_valid: bool
    code_system: ICDCodeSystem
    description: Optional[str] = None
    warning: Optional[str] = None
    suggested_code: Optional[str] = None


# ICD-10 pattern: Letter followed by 2 digits, optional decimal and more digits
# Example: J06.9, E11.65, M54.5
ICD10_PATTERN = re.compile(r'^[A-Z]\d{2}(\.\d{1,4})?$', re.IGNORECASE)

# ICD-9 pattern: 3-5 digits with optional decimal after 3rd digit
# Example: 250.00, 401.9, 780.79
ICD9_PATTERN = re.compile(r'^\d{3}(\.\d{1,2})?$')

# E-codes (external causes) for ICD-9: E followed by 3-4 digits
ICD9_ECODE_PATTERN = re.compile(r'^E\d{3}(\.\d)?$', re.IGNORECASE)

# V-codes (supplementary classification) for ICD-9: V followed by 2 digits
ICD9_VCODE_PATTERN = re.compile(r'^V\d{2}(\.\d{1,2})?$', re.IGNORECASE)


# Common ICD-10 codes with descriptions (comprehensive medical code database)
COMMON_ICD10_CODES: Dict[str, str] = {
    # ==================== RESPIRATORY ====================
    "J06.9": "Acute upper respiratory infection, unspecified",
    "J00": "Acute nasopharyngitis (common cold)",
    "J01.90": "Acute sinusitis, unspecified",
    "J02.9": "Acute pharyngitis, unspecified",
    "J03.90": "Acute tonsillitis, unspecified",
    "J04.0": "Acute laryngitis",
    "J11.1": "Influenza due to unidentified influenza virus with other respiratory manifestations",
    "J18.9": "Pneumonia, unspecified organism",
    "J18.1": "Lobar pneumonia, unspecified organism",
    "J12.89": "Other viral pneumonia",
    "J15.9": "Unspecified bacterial pneumonia",
    "J20.9": "Acute bronchitis, unspecified",
    "J21.9": "Acute bronchiolitis, unspecified",
    "J30.9": "Allergic rhinitis, unspecified",
    "J30.1": "Allergic rhinitis due to pollen",
    "J34.2": "Deviated nasal septum",
    "J40": "Bronchitis, not specified as acute or chronic",
    "J42": "Unspecified chronic bronchitis",
    "J44.0": "COPD with acute lower respiratory infection",
    "J44.1": "COPD with acute exacerbation",
    "J44.9": "Chronic obstructive pulmonary disease, unspecified",
    "J45.20": "Mild intermittent asthma, uncomplicated",
    "J45.30": "Mild persistent asthma, uncomplicated",
    "J45.40": "Moderate persistent asthma, uncomplicated",
    "J45.50": "Severe persistent asthma, uncomplicated",
    "J45.909": "Asthma, unspecified, uncomplicated",
    "J45.998": "Asthma, unspecified, other",
    "J84.10": "Pulmonary fibrosis, unspecified",
    "J90": "Pleural effusion, not elsewhere classified",
    "J93.9": "Pneumothorax, unspecified",
    "J96.00": "Acute respiratory failure, unspecified",

    # ==================== CARDIOVASCULAR ====================
    "I10": "Essential (primary) hypertension",
    "I11.9": "Hypertensive heart disease without heart failure",
    "I12.9": "Hypertensive chronic kidney disease",
    "I20.0": "Unstable angina",
    "I20.9": "Angina pectoris, unspecified",
    "I21.3": "ST elevation (STEMI) myocardial infarction of unspecified site",
    "I21.4": "Non-ST elevation (NSTEMI) myocardial infarction",
    "I25.10": "Atherosclerotic heart disease of native coronary artery",
    "I25.2": "Old myocardial infarction",
    "I25.9": "Chronic ischemic heart disease, unspecified",
    "I26.99": "Other pulmonary embolism without acute cor pulmonale",
    "I27.0": "Primary pulmonary hypertension",
    "I42.9": "Cardiomyopathy, unspecified",
    "I47.1": "Supraventricular tachycardia",
    "I47.2": "Ventricular tachycardia",
    "I48.0": "Paroxysmal atrial fibrillation",
    "I48.1": "Persistent atrial fibrillation",
    "I48.2": "Chronic atrial fibrillation",
    "I48.91": "Unspecified atrial fibrillation",
    "I49.9": "Cardiac arrhythmia, unspecified",
    "I50.1": "Left ventricular failure, unspecified",
    "I50.22": "Chronic systolic heart failure",
    "I50.32": "Chronic diastolic heart failure",
    "I50.9": "Heart failure, unspecified",
    "I63.9": "Cerebral infarction, unspecified",
    "I65.29": "Occlusion and stenosis of carotid artery",
    "I70.0": "Atherosclerosis of aorta",
    "I73.9": "Peripheral vascular disease, unspecified",
    "I80.10": "Phlebitis of femoral vein",
    "I82.401": "Acute embolism and thrombosis of unspecified deep veins",
    "I83.90": "Varicose veins of unspecified lower extremity",
    "I87.2": "Venous insufficiency (chronic)",

    # ==================== ENDOCRINE/METABOLIC ====================
    "E03.9": "Hypothyroidism, unspecified",
    "E04.1": "Nontoxic single thyroid nodule",
    "E05.90": "Thyrotoxicosis, unspecified",
    "E06.3": "Autoimmune thyroiditis",
    "E10.9": "Type 1 diabetes mellitus without complications",
    "E10.65": "Type 1 diabetes mellitus with hyperglycemia",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "E11.65": "Type 2 diabetes mellitus with hyperglycemia",
    "E11.21": "Type 2 diabetes mellitus with diabetic nephropathy",
    "E11.22": "Type 2 diabetes mellitus with diabetic chronic kidney disease",
    "E11.311": "Type 2 diabetes with diabetic retinopathy with macular edema",
    "E11.40": "Type 2 diabetes mellitus with diabetic neuropathy, unspecified",
    "E11.42": "Type 2 diabetes mellitus with diabetic polyneuropathy",
    "E13.9": "Other specified diabetes mellitus without complications",
    "E16.2": "Hypoglycemia, unspecified",
    "E27.1": "Primary adrenocortical insufficiency",
    "E27.40": "Unspecified adrenocortical insufficiency",
    "E29.1": "Testicular hypofunction",
    "E34.9": "Endocrine disorder, unspecified",
    "E55.9": "Vitamin D deficiency, unspecified",
    "E56.1": "Deficiency of vitamin K",
    "E61.1": "Iron deficiency",
    "E66.01": "Morbid obesity due to excess calories",
    "E66.9": "Obesity, unspecified",
    "E78.0": "Pure hypercholesterolemia",
    "E78.1": "Pure hypertriglyceridemia",
    "E78.2": "Mixed hyperlipidemia",
    "E78.5": "Hyperlipidemia, unspecified",
    "E79.0": "Hyperuricemia without signs of inflammatory arthritis",
    "E83.52": "Hypercalcemia",
    "E87.1": "Hypo-osmolality and hyponatremia",
    "E87.6": "Hypokalemia",
    "E88.89": "Other specified metabolic disorders",

    # ==================== MENTAL HEALTH ====================
    "F10.10": "Alcohol use disorder, mild",
    "F10.20": "Alcohol use disorder, moderate",
    "F10.239": "Alcohol dependence with withdrawal, unspecified",
    "F11.10": "Opioid use disorder, mild",
    "F11.20": "Opioid use disorder, moderate",
    "F12.10": "Cannabis use disorder, mild",
    "F17.210": "Nicotine dependence, cigarettes, uncomplicated",
    "F17.200": "Nicotine dependence, unspecified, uncomplicated",
    "F20.9": "Schizophrenia, unspecified",
    "F31.9": "Bipolar disorder, unspecified",
    "F32.0": "Major depressive disorder, single episode, mild",
    "F32.1": "Major depressive disorder, single episode, moderate",
    "F32.2": "Major depressive disorder, single episode, severe",
    "F32.9": "Major depressive disorder, single episode, unspecified",
    "F33.0": "Major depressive disorder, recurrent, mild",
    "F33.1": "Major depressive disorder, recurrent, moderate",
    "F33.9": "Major depressive disorder, recurrent, unspecified",
    "F40.10": "Social phobia, unspecified",
    "F41.0": "Panic disorder without agoraphobia",
    "F41.1": "Generalized anxiety disorder",
    "F41.9": "Anxiety disorder, unspecified",
    "F42.9": "Obsessive-compulsive disorder, unspecified",
    "F43.10": "Post-traumatic stress disorder, unspecified",
    "F43.20": "Adjustment disorder, unspecified",
    "F43.23": "Adjustment disorder with mixed anxiety and depressed mood",
    "F50.00": "Anorexia nervosa, unspecified",
    "F50.2": "Bulimia nervosa",
    "F51.01": "Primary insomnia",
    "F90.9": "Attention-deficit hyperactivity disorder, unspecified type",

    # ==================== MUSCULOSKELETAL ====================
    "M05.79": "Rheumatoid arthritis with rheumatoid factor",
    "M06.9": "Rheumatoid arthritis, unspecified",
    "M10.9": "Gout, unspecified",
    "M13.9": "Arthritis, unspecified",
    "M15.9": "Polyosteoarthritis, unspecified",
    "M16.9": "Osteoarthritis of hip, unspecified",
    "M17.0": "Primary osteoarthritis, bilateral knees",
    "M17.11": "Primary osteoarthritis, right knee",
    "M17.12": "Primary osteoarthritis, left knee",
    "M17.9": "Osteoarthritis of knee, unspecified",
    "M19.90": "Unspecified osteoarthritis, unspecified site",
    "M25.50": "Pain in unspecified joint",
    "M25.511": "Pain in right shoulder",
    "M25.512": "Pain in left shoulder",
    "M25.561": "Pain in right knee",
    "M25.562": "Pain in left knee",
    "M25.571": "Pain in right ankle and joints of right foot",
    "M32.9": "Systemic lupus erythematosus, unspecified",
    "M35.3": "Polymyalgia rheumatica",
    "M45.9": "Ankylosing spondylitis of unspecified sites in spine",
    "M47.816": "Spondylosis without myelopathy, lumbar region",
    "M47.817": "Spondylosis without myelopathy, lumbosacral region",
    "M50.20": "Other cervical disc displacement, unspecified cervical region",
    "M51.16": "Intervertebral disc disorders with radiculopathy, lumbar region",
    "M54.2": "Cervicalgia",
    "M54.5": "Low back pain",
    "M54.6": "Pain in thoracic spine",
    "M62.830": "Muscle spasm of back",
    "M75.10": "Rotator cuff tear or rupture, not specified as traumatic",
    "M76.50": "Patellar tendinitis, unspecified knee",
    "M77.10": "Lateral epicondylitis",
    "M79.1": "Myalgia",
    "M79.3": "Panniculitis, unspecified",
    "M79.7": "Fibromyalgia",
    "M80.00XA": "Age-related osteoporosis with current pathological fracture",
    "M81.0": "Age-related osteoporosis without current pathological fracture",

    # ==================== GASTROINTESTINAL ====================
    "K04.7": "Periapical abscess without sinus",
    "K08.9": "Disorder of teeth and supporting structures, unspecified",
    "K12.1": "Other forms of stomatitis",
    "K20.9": "Esophagitis, unspecified",
    "K21.0": "Gastro-esophageal reflux disease with esophagitis",
    "K21.9": "Gastro-esophageal reflux disease without esophagitis",
    "K25.9": "Gastric ulcer, unspecified",
    "K26.9": "Duodenal ulcer, unspecified",
    "K29.00": "Acute gastritis without bleeding",
    "K29.50": "Unspecified chronic gastritis without bleeding",
    "K29.70": "Gastritis, unspecified, without bleeding",
    "K30": "Functional dyspepsia",
    "K35.80": "Unspecified acute appendicitis",
    "K40.90": "Unilateral inguinal hernia, without obstruction or gangrene",
    "K50.90": "Crohn's disease, unspecified, without complications",
    "K51.90": "Ulcerative colitis, unspecified, without complications",
    "K52.9": "Noninfective gastroenteritis and colitis, unspecified",
    "K56.69": "Other intestinal obstruction",
    "K57.30": "Diverticulosis of large intestine without perforation or abscess",
    "K57.90": "Diverticulosis of intestine, part unspecified, without perforation",
    "K58.0": "Irritable bowel syndrome with diarrhea",
    "K58.1": "Irritable bowel syndrome with constipation",
    "K58.9": "Irritable bowel syndrome without diarrhea",
    "K59.00": "Constipation, unspecified",
    "K62.5": "Hemorrhage of anus and rectum",
    "K64.9": "Unspecified hemorrhoids",
    "K70.30": "Alcoholic cirrhosis of liver without ascites",
    "K74.60": "Unspecified cirrhosis of liver",
    "K75.81": "Nonalcoholic steatohepatitis (NASH)",
    "K76.0": "Fatty (change of) liver, not elsewhere classified",
    "K80.20": "Calculus of gallbladder without cholecystitis",
    "K85.90": "Acute pancreatitis, unspecified",
    "K86.1": "Other chronic pancreatitis",

    # ==================== GENITOURINARY ====================
    "N10": "Acute pyelonephritis",
    "N11.9": "Chronic tubulo-interstitial nephritis, unspecified",
    "N13.30": "Unspecified hydronephrosis",
    "N17.9": "Acute kidney failure, unspecified",
    "N18.1": "Chronic kidney disease, stage 1",
    "N18.2": "Chronic kidney disease, stage 2",
    "N18.3": "Chronic kidney disease, stage 3",
    "N18.4": "Chronic kidney disease, stage 4",
    "N18.5": "Chronic kidney disease, stage 5",
    "N18.6": "End stage renal disease",
    "N18.9": "Chronic kidney disease, unspecified",
    "N20.0": "Calculus of kidney",
    "N20.1": "Calculus of ureter",
    "N28.1": "Cyst of kidney, acquired",
    "N30.00": "Acute cystitis without hematuria",
    "N30.90": "Cystitis, unspecified without hematuria",
    "N32.81": "Overactive bladder",
    "N39.0": "Urinary tract infection, site not specified",
    "N39.41": "Urge incontinence",
    "N39.46": "Mixed incontinence",
    "N40.0": "Benign prostatic hyperplasia without lower urinary tract symptoms",
    "N40.1": "Benign prostatic hyperplasia with lower urinary tract symptoms",
    "N41.0": "Acute prostatitis",
    "N41.1": "Chronic prostatitis",
    "N42.30": "Unspecified dysplasia of prostate",
    "N48.1": "Balanitis",
    "N52.9": "Male erectile dysfunction, unspecified",
    "N63.0": "Unspecified lump in unspecified breast",
    "N80.9": "Endometriosis, unspecified",
    "N81.2": "Incomplete uterovaginal prolapse",
    "N83.20": "Unspecified ovarian cysts",
    "N85.00": "Endometrial hyperplasia, unspecified",
    "N89.8": "Other specified noninflammatory disorders of vagina",
    "N91.2": "Amenorrhea, unspecified",
    "N92.0": "Excessive and frequent menstruation with regular cycle",
    "N92.6": "Irregular menstruation, unspecified",
    "N94.6": "Dysmenorrhea, unspecified",
    "N95.1": "Menopausal and female climacteric states",

    # ==================== NEUROLOGICAL ====================
    "G20": "Parkinson's disease",
    "G25.0": "Essential tremor",
    "G30.9": "Alzheimer's disease, unspecified",
    "G31.84": "Mild cognitive impairment",
    "G35": "Multiple sclerosis",
    "G40.909": "Epilepsy, unspecified, not intractable",
    "G43.009": "Migraine without aura, not intractable, without status migrainosus",
    "G43.109": "Migraine with aura, not intractable, without status migrainosus",
    "G43.709": "Chronic migraine without aura, not intractable",
    "G43.909": "Migraine, unspecified, not intractable",
    "G44.209": "Tension-type headache, unspecified, not intractable",
    "G44.219": "Episodic tension-type headache, not intractable",
    "G44.229": "Chronic tension-type headache, not intractable",
    "G45.9": "Transient cerebral ischemic attack, unspecified",
    "G47.00": "Insomnia, unspecified",
    "G47.10": "Hypersomnia, unspecified",
    "G47.33": "Obstructive sleep apnea",
    "G50.0": "Trigeminal neuralgia",
    "G51.0": "Bell's palsy",
    "G56.00": "Carpal tunnel syndrome, unspecified upper limb",
    "G57.10": "Meralgia paresthetica, unspecified lower limb",
    "G62.9": "Polyneuropathy, unspecified",
    "G89.29": "Other chronic pain",
    "G89.4": "Chronic pain syndrome",
    "G91.9": "Hydrocephalus, unspecified",
    "G93.40": "Encephalopathy, unspecified",

    # ==================== SKIN ====================
    "L01.00": "Impetigo, unspecified",
    "L02.91": "Cutaneous abscess, unspecified",
    "L03.90": "Cellulitis, unspecified",
    "L08.9": "Local infection of the skin and subcutaneous tissue, unspecified",
    "L20.9": "Atopic dermatitis, unspecified",
    "L21.9": "Seborrheic dermatitis, unspecified",
    "L23.9": "Allergic contact dermatitis, unspecified cause",
    "L25.9": "Unspecified contact dermatitis, unspecified cause",
    "L29.9": "Pruritus, unspecified",
    "L30.9": "Dermatitis, unspecified",
    "L40.0": "Psoriasis vulgaris",
    "L40.9": "Psoriasis, unspecified",
    "L50.9": "Urticaria, unspecified",
    "L60.0": "Ingrowing nail",
    "L60.3": "Nail dystrophy",
    "L70.0": "Acne vulgaris",
    "L72.0": "Epidermal cyst",
    "L73.2": "Hidradenitis suppurativa",
    "L80": "Vitiligo",
    "L82.1": "Other seborrheic keratosis",
    "L90.5": "Scar conditions and fibrosis of skin",
    "L98.9": "Disorder of the skin and subcutaneous tissue, unspecified",

    # ==================== INFECTIOUS ====================
    "A04.72": "Enterocolitis due to Clostridium difficile, recurrent",
    "A08.4": "Viral intestinal infection, unspecified",
    "A09": "Infectious gastroenteritis and colitis, unspecified",
    "A41.9": "Sepsis, unspecified organism",
    "A49.9": "Bacterial infection, unspecified",
    "B00.9": "Herpesviral infection, unspecified",
    "B02.9": "Zoster without complications",
    "B34.9": "Viral infection, unspecified",
    "B35.1": "Tinea unguium (onychomycosis)",
    "B35.3": "Tinea pedis (athlete's foot)",
    "B37.0": "Candidal stomatitis",
    "B37.3": "Candidiasis of vulva and vagina",
    "B86": "Scabies",
    "B97.89": "Other viral agents as the cause of diseases classified elsewhere",

    # ==================== SYMPTOMS/SIGNS ====================
    "R00.0": "Tachycardia, unspecified",
    "R00.1": "Bradycardia, unspecified",
    "R00.2": "Palpitations",
    "R03.0": "Elevated blood-pressure reading, without diagnosis of hypertension",
    "R05": "Cough",
    "R05.9": "Cough, unspecified",
    "R06.00": "Dyspnea, unspecified",
    "R06.02": "Shortness of breath",
    "R06.2": "Wheezing",
    "R07.89": "Other chest pain",
    "R07.9": "Chest pain, unspecified",
    "R09.81": "Nasal congestion",
    "R10.0": "Acute abdomen",
    "R10.10": "Upper abdominal pain, unspecified",
    "R10.30": "Lower abdominal pain, unspecified",
    "R10.9": "Unspecified abdominal pain",
    "R11.0": "Nausea",
    "R11.10": "Vomiting, unspecified",
    "R11.2": "Nausea with vomiting, unspecified",
    "R13.10": "Dysphagia, unspecified",
    "R19.7": "Diarrhea, unspecified",
    "R21": "Rash and other nonspecific skin eruption",
    "R22.2": "Localized swelling, mass and lump, trunk",
    "R25.1": "Tremor, unspecified",
    "R26.0": "Ataxic gait",
    "R26.89": "Other abnormalities of gait and mobility",
    "R29.6": "Repeated falls",
    "R31.9": "Hematuria, unspecified",
    "R35.0": "Frequency of micturition",
    "R35.1": "Nocturia",
    "R40.20": "Unspecified coma",
    "R41.0": "Disorientation, unspecified",
    "R41.82": "Altered mental status, unspecified",
    "R42": "Dizziness and giddiness",
    "R50.9": "Fever, unspecified",
    "R51": "Headache",
    "R51.9": "Headache, unspecified",
    "R53.1": "Weakness",
    "R53.81": "Other malaise",
    "R53.83": "Other fatigue",
    "R55": "Syncope and collapse",
    "R56.9": "Unspecified convulsions",
    "R60.0": "Localized edema",
    "R60.9": "Edema, unspecified",
    "R63.0": "Anorexia",
    "R63.4": "Abnormal weight loss",
    "R63.5": "Abnormal weight gain",
    "R68.84": "Jaw pain",
    "R73.01": "Impaired fasting glucose",
    "R73.02": "Impaired glucose tolerance (oral)",
    "R73.09": "Other abnormal glucose",
    "R79.89": "Other specified abnormal findings of blood chemistry",

    # ==================== INJURY/TRAUMA ====================
    "S00.93XA": "Unspecified superficial injury of unspecified part of head, initial encounter",
    "S06.0X0A": "Concussion without loss of consciousness, initial encounter",
    "S09.90XA": "Unspecified injury of head, initial encounter",
    "S22.31XA": "Fracture of one rib, right side, initial encounter",
    "S22.32XA": "Fracture of one rib, left side, initial encounter",
    "S32.9XXA": "Fracture of unspecified parts of lumbosacral spine and pelvis",
    "S42.001A": "Fracture of unspecified part of right clavicle, initial encounter",
    "S52.501A": "Unspecified fracture of the lower end of right radius, initial encounter",
    "S62.609A": "Fracture of unspecified phalanx of unspecified finger, initial encounter",
    "S72.001A": "Fracture of unspecified part of neck of right femur, initial encounter",
    "S82.001A": "Unspecified fracture of right patella, initial encounter",
    "S82.101A": "Unspecified fracture of upper end of right tibia, initial encounter",
    "S83.511A": "Sprain of anterior cruciate ligament of right knee, initial encounter",
    "S86.011A": "Strain of right Achilles tendon, initial encounter",
    "S93.401A": "Sprain of unspecified ligament of right ankle, initial encounter",
    "T14.90XA": "Injury, unspecified, initial encounter",
    "T78.40XA": "Allergy, unspecified, initial encounter",
    "T88.7XXA": "Unspecified adverse effect of drug or medicament, initial encounter",

    # ==================== ONCOLOGY ====================
    "C18.9": "Malignant neoplasm of colon, unspecified",
    "C34.90": "Malignant neoplasm of unspecified part of bronchus or lung",
    "C50.919": "Malignant neoplasm of unspecified site of unspecified female breast",
    "C61": "Malignant neoplasm of prostate",
    "C73": "Malignant neoplasm of thyroid gland",
    "D12.6": "Benign neoplasm of colon, unspecified",
    "D17.9": "Benign lipomatous neoplasm, unspecified",
    "D22.9": "Melanocytic nevi, unspecified",
    "D24.9": "Benign neoplasm of unspecified breast",
    "D25.9": "Leiomyoma of uterus, unspecified",
    "D48.9": "Neoplasm of uncertain behavior, unspecified",

    # ==================== HEMATOLOGIC ====================
    "D50.9": "Iron deficiency anemia, unspecified",
    "D51.9": "Vitamin B12 deficiency anemia, unspecified",
    "D52.9": "Folate deficiency anemia, unspecified",
    "D64.9": "Anemia, unspecified",
    "D68.9": "Coagulation defect, unspecified",
    "D69.6": "Thrombocytopenia, unspecified",
    "D72.829": "Elevated white blood cell count, unspecified",
    "D89.9": "Disorder involving the immune mechanism, unspecified",

    # ==================== EYE/EAR ====================
    "H04.129": "Dry eye syndrome of unspecified lacrimal gland",
    "H10.9": "Unspecified conjunctivitis",
    "H26.9": "Unspecified cataract",
    "H35.30": "Unspecified macular degeneration",
    "H40.10X0": "Unspecified open-angle glaucoma, stage unspecified",
    "H52.4": "Presbyopia",
    "H53.9": "Unspecified visual disturbance",
    "H54.7": "Unspecified visual loss",
    "H60.90": "Unspecified otitis externa",
    "H65.90": "Unspecified nonsuppurative otitis media, unspecified ear",
    "H66.90": "Otitis media, unspecified, unspecified ear",
    "H81.10": "Benign paroxysmal vertigo, unspecified ear",
    "H81.399": "Other peripheral vertigo, unspecified ear",
    "H91.90": "Unspecified hearing loss, unspecified ear",
    "H93.19": "Tinnitus, unspecified ear",

    # ==================== PREGNANCY ====================
    "O09.90": "Supervision of high risk pregnancy, unspecified, unspecified trimester",
    "O13.9": "Gestational hypertension, unspecified trimester",
    "O14.90": "Unspecified pre-eclampsia, unspecified trimester",
    "O21.0": "Mild hyperemesis gravidarum",
    "O24.419": "Gestational diabetes mellitus in pregnancy, unspecified control",
    "O26.20": "Pregnancy care for patient with recurrent pregnancy loss",
    "O47.9": "False labor, unspecified",
    "O99.019": "Anemia complicating pregnancy, unspecified trimester",
    "Z33.1": "Pregnant state, incidental",
    "Z34.00": "Encounter for supervision of normal first pregnancy, unspecified trimester",

    # ==================== SCREENING/PREVENTIVE ====================
    "Z00.00": "Encounter for general adult medical examination without abnormal findings",
    "Z00.01": "Encounter for general adult medical examination with abnormal findings",
    "Z01.10": "Encounter for examination of ears and hearing without abnormal findings",
    "Z01.00": "Encounter for examination of eyes and vision without abnormal findings",
    "Z12.11": "Encounter for screening for malignant neoplasm of colon",
    "Z12.31": "Encounter for screening mammogram for malignant neoplasm of breast",
    "Z13.1": "Encounter for screening for diabetes mellitus",
    "Z13.220": "Encounter for screening for lipoid disorders",
    "Z23": "Encounter for immunization",
    "Z71.3": "Dietary counseling and surveillance",
    "Z76.0": "Encounter for issue of repeat prescription",
    "Z87.891": "Personal history of nicotine dependence",
}


# Common ICD-9 codes with descriptions (comprehensive for legacy support)
COMMON_ICD9_CODES: Dict[str, str] = {
    # ==================== RESPIRATORY ====================
    "460": "Acute nasopharyngitis (common cold)",
    "461.9": "Acute sinusitis, unspecified",
    "462": "Acute pharyngitis",
    "463": "Acute tonsillitis",
    "464.00": "Acute laryngitis without mention of obstruction",
    "465.9": "Acute upper respiratory infections of unspecified site",
    "466.0": "Acute bronchitis",
    "466.11": "Acute bronchiolitis due to respiratory syncytial virus",
    "466.19": "Acute bronchiolitis due to other infectious organisms",
    "477.9": "Allergic rhinitis, cause unspecified",
    "480.9": "Viral pneumonia, unspecified",
    "481": "Pneumococcal pneumonia",
    "486": "Pneumonia, organism unspecified",
    "487.1": "Influenza with other respiratory manifestations",
    "490": "Bronchitis, not specified as acute or chronic",
    "491.9": "Unspecified chronic bronchitis",
    "492.8": "Other emphysema",
    "493.90": "Asthma, unspecified",
    "493.00": "Extrinsic asthma, unspecified",
    "493.20": "Chronic obstructive asthma, unspecified",
    "496": "Chronic airway obstruction, not elsewhere classified",
    "511.9": "Unspecified pleural effusion",
    "512.89": "Other pneumothorax",
    "518.81": "Acute respiratory failure",

    # ==================== CARDIOVASCULAR ====================
    "401.1": "Benign essential hypertension",
    "401.9": "Unspecified essential hypertension",
    "402.91": "Unspecified hypertensive heart disease with heart failure",
    "410.9": "Acute myocardial infarction, unspecified site",
    "411.1": "Intermediate coronary syndrome",
    "413.9": "Other and unspecified angina pectoris",
    "414.00": "Coronary atherosclerosis of unspecified type of vessel",
    "414.01": "Coronary atherosclerosis of native coronary artery",
    "415.19": "Other pulmonary embolism and infarction",
    "416.0": "Primary pulmonary hypertension",
    "425.4": "Other primary cardiomyopathies",
    "427.0": "Paroxysmal supraventricular tachycardia",
    "427.1": "Paroxysmal ventricular tachycardia",
    "427.31": "Atrial fibrillation",
    "427.32": "Atrial flutter",
    "427.9": "Cardiac dysrhythmia, unspecified",
    "428.0": "Congestive heart failure, unspecified",
    "428.20": "Systolic heart failure, unspecified",
    "428.30": "Diastolic heart failure, unspecified",
    "434.91": "Cerebral artery occlusion, unspecified with cerebral infarction",
    "435.9": "Unspecified transient cerebral ischemia",
    "440.9": "Generalized and unspecified atherosclerosis",
    "443.9": "Peripheral vascular disease, unspecified",
    "451.19": "Phlebitis and thrombophlebitis of other deep vessels of lower extremities",
    "453.40": "Acute venous embolism and thrombosis of unspecified deep vessels",
    "454.9": "Varicose veins of lower extremities without ulcer or inflammation",

    # ==================== ENDOCRINE/METABOLIC ====================
    "242.90": "Thyrotoxicosis without mention of goiter or other cause",
    "244.9": "Unspecified hypothyroidism",
    "245.2": "Chronic lymphocytic thyroiditis",
    "250.00": "Diabetes mellitus type II without complications",
    "250.01": "Diabetes mellitus type I without complications",
    "250.40": "Diabetes with renal manifestations, type II or unspecified",
    "250.50": "Diabetes with ophthalmic manifestations, type II or unspecified",
    "250.60": "Diabetes with neurological manifestations, type II or unspecified",
    "251.2": "Hypoglycemia, unspecified",
    "255.41": "Glucocorticoid deficiency",
    "268.9": "Unspecified vitamin D deficiency",
    "272.0": "Pure hypercholesterolemia",
    "272.1": "Pure hypertriglyceridemia",
    "272.2": "Mixed hyperlipidemia",
    "272.4": "Other and unspecified hyperlipidemia",
    "274.9": "Gout, unspecified",
    "275.42": "Hypercalcemia",
    "276.1": "Hyposmolality and/or hyponatremia",
    "276.8": "Hypopotassemia",
    "278.00": "Obesity, unspecified",
    "278.01": "Morbid obesity",

    # ==================== MENTAL HEALTH ====================
    "291.81": "Alcohol withdrawal",
    "295.90": "Unspecified schizophrenia",
    "296.20": "Major depressive disorder, single episode, unspecified",
    "296.30": "Major depressive disorder, recurrent episode, unspecified",
    "296.80": "Bipolar disorder, unspecified",
    "300.00": "Anxiety state, unspecified",
    "300.01": "Panic disorder without agoraphobia",
    "300.02": "Generalized anxiety disorder",
    "300.3": "Obsessive-compulsive disorders",
    "300.4": "Dysthymic disorder",
    "303.90": "Other and unspecified alcohol dependence, unspecified",
    "304.00": "Opioid type dependence, unspecified",
    "305.1": "Tobacco use disorder",
    "307.42": "Persistent disorder of initiating or maintaining sleep",
    "309.0": "Adjustment disorder with depressed mood",
    "309.24": "Adjustment disorder with anxiety",
    "309.28": "Adjustment disorder with mixed anxiety and depressed mood",
    "309.81": "Posttraumatic stress disorder",
    "311": "Depressive disorder, not elsewhere classified",
    "314.01": "Attention deficit disorder with hyperactivity",

    # ==================== MUSCULOSKELETAL ====================
    "710.0": "Systemic lupus erythematosus",
    "714.0": "Rheumatoid arthritis",
    "715.00": "Osteoarthrosis, generalized, site unspecified",
    "715.90": "Osteoarthrosis, unspecified whether generalized or localized",
    "715.96": "Osteoarthrosis, unspecified, lower leg",
    "716.90": "Arthropathy, unspecified, site unspecified",
    "719.41": "Pain in joint, shoulder region",
    "719.46": "Pain in joint, lower leg",
    "720.0": "Ankylosing spondylitis",
    "721.3": "Lumbosacral spondylosis without myelopathy",
    "722.10": "Displacement of lumbar intervertebral disc without myelopathy",
    "722.52": "Degeneration of lumbar or lumbosacral intervertebral disc",
    "723.1": "Cervicalgia",
    "724.2": "Lumbago",
    "724.5": "Backache, unspecified",
    "726.10": "Rotator cuff syndrome of shoulder",
    "726.64": "Patellar tendinitis",
    "726.31": "Medial epicondylitis",
    "726.32": "Lateral epicondylitis",
    "728.71": "Plantar fascial fibromatosis",
    "729.1": "Myalgia and myositis, unspecified",
    "729.5": "Pain in limb",
    "733.00": "Osteoporosis, unspecified",
    "729.0": "Rheumatism, unspecified and fibrositis",

    # ==================== GASTROINTESTINAL ====================
    "530.11": "Reflux esophagitis",
    "530.81": "Esophageal reflux",
    "531.90": "Gastric ulcer, unspecified, without mention of hemorrhage or perforation",
    "532.90": "Duodenal ulcer, unspecified, without mention of hemorrhage or perforation",
    "535.00": "Acute gastritis, without mention of hemorrhage",
    "535.50": "Unspecified gastritis and gastroduodenitis, without mention of hemorrhage",
    "536.8": "Dyspepsia and other specified disorders of function of stomach",
    "540.9": "Acute appendicitis without mention of peritonitis",
    "550.90": "Inguinal hernia, without obstruction or gangrene",
    "555.9": "Regional enteritis of unspecified site",
    "556.9": "Ulcerative colitis, unspecified",
    "558.9": "Other and unspecified noninfectious gastroenteritis and colitis",
    "560.9": "Unspecified intestinal obstruction",
    "562.10": "Diverticulosis of colon (without mention of hemorrhage)",
    "564.00": "Constipation, unspecified",
    "564.1": "Irritable bowel syndrome",
    "569.3": "Hemorrhage of rectum and anus",
    "571.40": "Chronic hepatitis, unspecified",
    "571.5": "Cirrhosis of liver without mention of alcohol",
    "571.8": "Other chronic nonalcoholic liver disease",
    "574.20": "Calculus of gallbladder without mention of cholecystitis",
    "577.0": "Acute pancreatitis",
    "577.1": "Chronic pancreatitis",
    "455.6": "Unspecified hemorrhoids",

    # ==================== GENITOURINARY ====================
    "580.9": "Acute glomerulonephritis with unspecified pathological lesion in kidney",
    "584.9": "Acute kidney failure, unspecified",
    "585.3": "Chronic kidney disease, Stage III",
    "585.9": "Chronic kidney disease, unspecified",
    "590.10": "Acute pyelonephritis without lesion of renal medullary necrosis",
    "591": "Hydronephrosis",
    "592.0": "Calculus of kidney",
    "592.1": "Calculus of ureter",
    "593.2": "Cyst of kidney, acquired",
    "595.0": "Acute cystitis",
    "595.9": "Cystitis, unspecified",
    "596.51": "Hypertonicity of bladder",
    "599.0": "Urinary tract infection, site not specified",
    "599.70": "Hematuria, unspecified",
    "600.00": "Hypertrophy (benign) of prostate without urinary obstruction",
    "600.01": "Hypertrophy (benign) of prostate with urinary obstruction",
    "601.0": "Acute prostatitis",
    "601.1": "Chronic prostatitis",
    "607.84": "Impotence of organic origin",
    "611.72": "Lump or mass in breast",
    "617.9": "Endometriosis, site unspecified",
    "618.04": "Incomplete uterovaginal prolapse",
    "620.2": "Other and unspecified ovarian cyst",
    "625.3": "Dysmenorrhea",
    "626.0": "Absence of menstruation",
    "626.2": "Excessive or frequent menstruation",
    "627.2": "Symptomatic menopausal or female climacteric states",

    # ==================== NEUROLOGICAL ====================
    "332.0": "Paralysis agitans (Parkinson's disease)",
    "331.0": "Alzheimer's disease",
    "340": "Multiple sclerosis",
    "345.90": "Epilepsy, unspecified, without mention of intractable epilepsy",
    "346.10": "Migraine with aura, without mention of intractable migraine",
    "346.90": "Migraine, unspecified, without mention of intractable migraine",
    "307.81": "Tension headache",
    "350.1": "Trigeminal neuralgia",
    "351.0": "Bell's palsy",
    "354.0": "Carpal tunnel syndrome",
    "355.1": "Meralgia paresthetica",
    "356.9": "Unspecified idiopathic peripheral neuropathy",
    "780.02": "Transient alteration of awareness",
    "780.09": "Other alteration of consciousness",
    "780.4": "Dizziness and giddiness",
    "780.50": "Sleep disturbance, unspecified",
    "780.52": "Insomnia, unspecified",
    "327.23": "Obstructive sleep apnea (adult) (pediatric)",
    "333.1": "Essential and other specified forms of tremor",
    "338.29": "Other chronic pain",

    # ==================== SKIN ====================
    "684": "Impetigo",
    "682.9": "Cellulitis and abscess of unspecified sites",
    "686.9": "Unspecified local infection of skin and subcutaneous tissue",
    "691.8": "Other atopic dermatitis and related conditions",
    "690.10": "Seborrheic dermatitis, unspecified",
    "692.9": "Contact dermatitis and other eczema, unspecified cause",
    "693.1": "Dermatitis due to food taken internally",
    "696.1": "Other psoriasis",
    "698.9": "Unspecified pruritic disorder",
    "700": "Corns and callosities",
    "703.0": "Ingrowing nail",
    "706.1": "Other acne",
    "708.9": "Urticaria, unspecified",
    "709.9": "Unspecified disorder of skin and subcutaneous tissue",

    # ==================== INFECTIOUS ====================
    "008.45": "Intestinal infection due to Clostridium difficile",
    "008.8": "Intestinal infection due to other organism, not elsewhere classified",
    "009.0": "Infectious colitis, enteritis, and gastroenteritis",
    "038.9": "Unspecified septicemia",
    "041.9": "Bacterial infection, unspecified, in conditions classified elsewhere",
    "054.9": "Herpes simplex without mention of complication",
    "053.9": "Herpes zoster without mention of complication",
    "079.99": "Unspecified viral infection",
    "110.1": "Dermatophytosis of nail (tinea unguium)",
    "110.4": "Dermatophytosis of foot (tinea pedis)",
    "112.0": "Candidiasis of mouth (thrush)",
    "112.1": "Candidiasis of vulva and vagina",
    "133.0": "Scabies",

    # ==================== SYMPTOMS/SIGNS ====================
    "780.01": "Coma",
    "780.09": "Other alteration of consciousness",
    "780.39": "Other convulsions",
    "780.4": "Dizziness and giddiness",
    "780.6": "Fever and other physiologic disturbances of temperature regulation",
    "780.79": "Other malaise and fatigue",
    "782.1": "Rash and other nonspecific skin eruption",
    "782.3": "Edema",
    "783.0": "Anorexia",
    "783.21": "Loss of weight",
    "783.1": "Abnormal weight gain",
    "784.0": "Headache",
    "785.0": "Tachycardia, unspecified",
    "785.1": "Palpitations",
    "786.05": "Shortness of breath",
    "786.09": "Other dyspnea and respiratory abnormality",
    "786.2": "Cough",
    "786.50": "Chest pain, unspecified",
    "787.01": "Nausea with vomiting",
    "787.02": "Nausea alone",
    "787.03": "Vomiting alone",
    "787.91": "Diarrhea",
    "788.41": "Urinary frequency",
    "788.43": "Nocturia",
    "789.00": "Abdominal pain, unspecified site",
    "789.30": "Abdominal or pelvic swelling, mass, or lump, unspecified site",
    "780.2": "Syncope and collapse",
    "780.93": "Memory loss",
    "780.97": "Altered mental status",
    "784.3": "Aphasia",
    "784.7": "Epistaxis",
    "790.29": "Other abnormal glucose",
    "793.80": "Abnormal mammogram, unspecified",
    "796.2": "Elevated blood pressure reading without diagnosis of hypertension",
    "799.3": "Debility, unspecified",

    # ==================== INJURY ====================
    "830.0": "Closed dislocation of jaw",
    "845.00": "Sprains and strains of ankle, unspecified site",
    "847.2": "Sprains and strains of lumbar",
    "850.0": "Concussion with no loss of consciousness",
    "873.40": "Open wound of face, unspecified site",
    "959.9": "Injury, other and unspecified",
    "995.20": "Unspecified adverse effect of unspecified drug, medicinal and biological substance",
    "995.3": "Allergy, unspecified",

    # ==================== SCREENING/PREVENTIVE ====================
    "V70.0": "Routine general medical examination at a health care facility",
    "V72.31": "Routine gynecological examination",
    "V76.12": "Other screening mammogram",
    "V76.51": "Special screening for malignant neoplasms of colon",
    "V77.1": "Special screening for diabetes mellitus",
    "V06.9": "Need for prophylactic vaccination and inoculation against unspecified infectious disease",
    "V15.82": "History of tobacco use",
}


class ICDValidator:
    """
    Validates ICD-9 and ICD-10 diagnostic codes.

    Supports:
    - Pattern-based format validation
    - Common code lookup with descriptions
    - Flexible code normalization

    Example:
        validator = ICDValidator()

        # Validate a code
        result = validator.validate("J06.9")
        print(result.is_valid)  # True
        print(result.code_system)  # ICDCodeSystem.ICD10
        print(result.description)  # "Acute upper respiratory infection, unspecified"

        # Validate multiple codes
        results = validator.validate_batch(["J06.9", "250.00", "INVALID"])
    """

    def __init__(
        self,
        icd10_codes: Optional[Dict[str, str]] = None,
        icd9_codes: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the validator.

        Args:
            icd10_codes: Optional custom ICD-10 code dictionary
            icd9_codes: Optional custom ICD-9 code dictionary
        """
        self.icd10_codes = icd10_codes or COMMON_ICD10_CODES
        self.icd9_codes = icd9_codes or COMMON_ICD9_CODES

    def validate(self, code: str) -> ICDValidationResult:
        """
        Validate an ICD code and return detailed result.

        Args:
            code: The ICD code to validate

        Returns:
            ICDValidationResult with validation status and details
        """
        if not code:
            return ICDValidationResult(
                code=code,
                is_valid=False,
                code_system=ICDCodeSystem.UNKNOWN,
                warning="Empty code provided"
            )

        # Normalize the code
        normalized = self._normalize_code(code)

        # Determine code system and validate format
        code_system = self._detect_code_system(normalized)

        if code_system == ICDCodeSystem.UNKNOWN:
            return ICDValidationResult(
                code=code,
                is_valid=False,
                code_system=ICDCodeSystem.UNKNOWN,
                warning="Invalid ICD code format"
            )

        # Look up description
        description = self._lookup_description(normalized, code_system)

        # Check if it's a known valid code
        is_known = description is not None

        # Even if not in our lookup table, format-valid codes might be correct
        # We'll mark them as valid but with a warning
        result = ICDValidationResult(
            code=normalized,
            is_valid=True,  # Format is valid
            code_system=code_system,
            description=description
        )

        if not is_known:
            result.warning = (
                f"Code {normalized} has valid {code_system.value} format but is not in "
                "the common codes database. Please verify with official ICD reference."
            )

        return result

    def validate_batch(self, codes: List[str]) -> List[ICDValidationResult]:
        """
        Validate multiple ICD codes.

        Args:
            codes: List of ICD codes to validate

        Returns:
            List of ICDValidationResult objects
        """
        return [self.validate(code) for code in codes]

    def is_valid_format(self, code: str) -> bool:
        """
        Quick check if code has valid ICD format.

        Args:
            code: The ICD code to check

        Returns:
            True if format is valid for either ICD-9 or ICD-10
        """
        normalized = self._normalize_code(code)
        return self._detect_code_system(normalized) != ICDCodeSystem.UNKNOWN

    def get_description(self, code: str) -> Optional[str]:
        """
        Get description for an ICD code if available.

        Args:
            code: The ICD code

        Returns:
            Description string or None if not found
        """
        normalized = self._normalize_code(code)
        code_system = self._detect_code_system(normalized)
        return self._lookup_description(normalized, code_system)

    def suggest_similar_codes(self, code: str, limit: int = 5) -> List[str]:
        """
        Suggest similar valid codes for a potentially incorrect code.

        Args:
            code: The code to find similar codes for
            limit: Maximum number of suggestions

        Returns:
            List of similar code suggestions
        """
        normalized = self._normalize_code(code)
        suggestions = []

        # Determine likely code system
        code_system = self._detect_code_system(normalized)

        if code_system == ICDCodeSystem.ICD10 or normalized[0].isalpha():
            # Search ICD-10 codes
            prefix = normalized[:3] if len(normalized) >= 3 else normalized
            for valid_code in self.icd10_codes.keys():
                if valid_code.startswith(prefix):
                    suggestions.append(valid_code)
                    if len(suggestions) >= limit:
                        break
        else:
            # Search ICD-9 codes
            prefix = normalized[:3] if len(normalized) >= 3 else normalized
            for valid_code in self.icd9_codes.keys():
                if valid_code.startswith(prefix):
                    suggestions.append(valid_code)
                    if len(suggestions) >= limit:
                        break

        return suggestions

    def _normalize_code(self, code: str) -> str:
        """Normalize an ICD code for consistent processing."""
        # Remove extra whitespace
        normalized = code.strip()

        # Uppercase letters (ICD-10 codes use uppercase)
        normalized = normalized.upper()

        # Remove common prefixes if present
        for prefix in ["ICD-10:", "ICD-9:", "ICD10:", "ICD9:", "ICD:"]:
            if normalized.upper().startswith(prefix.upper()):
                normalized = normalized[len(prefix):].strip()

        return normalized

    def _detect_code_system(self, code: str) -> ICDCodeSystem:
        """Detect which ICD code system a code belongs to."""
        if not code:
            return ICDCodeSystem.UNKNOWN

        # ICD-10: Starts with letter
        if ICD10_PATTERN.match(code):
            return ICDCodeSystem.ICD10

        # ICD-9: Numeric only
        if ICD9_PATTERN.match(code):
            return ICDCodeSystem.ICD9

        # ICD-9 E-codes (external causes)
        if ICD9_ECODE_PATTERN.match(code):
            return ICDCodeSystem.ICD9

        # ICD-9 V-codes (supplementary classification)
        if ICD9_VCODE_PATTERN.match(code):
            return ICDCodeSystem.ICD9

        return ICDCodeSystem.UNKNOWN

    def _lookup_description(
        self,
        code: str,
        code_system: ICDCodeSystem
    ) -> Optional[str]:
        """Look up description for a code in the appropriate database."""
        if code_system == ICDCodeSystem.ICD10:
            return self.icd10_codes.get(code)
        elif code_system == ICDCodeSystem.ICD9:
            return self.icd9_codes.get(code)
        return None


def extract_icd_codes(text: str) -> List[str]:
    """
    Extract potential ICD codes from text.

    Args:
        text: Text that may contain ICD codes

    Returns:
        List of potential ICD codes found
    """
    codes = []

    # ICD-10 pattern in text
    icd10_matches = re.findall(r'[A-Z]\d{2}(?:\.\d{1,4})?', text, re.IGNORECASE)
    codes.extend(icd10_matches)

    # ICD-9 pattern in text (3 digits, optional decimal)
    icd9_matches = re.findall(r'\b\d{3}(?:\.\d{1,2})?\b', text)
    codes.extend(icd9_matches)

    # Remove duplicates while preserving order
    seen = set()
    unique_codes = []
    for code in codes:
        upper_code = code.upper()
        if upper_code not in seen:
            seen.add(upper_code)
            unique_codes.append(upper_code)

    return unique_codes


# Module-level validator instance for convenience
_default_validator: Optional[ICDValidator] = None


def get_validator() -> ICDValidator:
    """Get the default ICD validator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = ICDValidator()
    return _default_validator


def validate_code(code: str) -> ICDValidationResult:
    """Convenience function to validate a single code."""
    return get_validator().validate(code)


def validate_codes(codes: List[str]) -> List[ICDValidationResult]:
    """Convenience function to validate multiple codes."""
    return get_validator().validate_batch(codes)
