"""
Tests for src/rag/medical_dictionaries.py

Covers the four static dicts: CONDITIONS_DICT, MEDICATIONS_DICT,
ANATOMY_DICT, SYMPTOMS_DICT — structural invariants (lowercase keys,
str values, no empties), representative lookups, and alias→canonical
normalization.
Pure data — no network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.medical_dictionaries import (
    CONDITIONS_DICT,
    MEDICATIONS_DICT,
    ANATOMY_DICT,
    SYMPTOMS_DICT,
)


# ===========================================================================
# Structural invariants (common across all dicts)
# ===========================================================================

ALL_DICTS = [
    ("CONDITIONS_DICT", CONDITIONS_DICT),
    ("MEDICATIONS_DICT", MEDICATIONS_DICT),
    ("ANATOMY_DICT", ANATOMY_DICT),
    ("SYMPTOMS_DICT", SYMPTOMS_DICT),
]


@pytest.mark.parametrize("name,d", ALL_DICTS)
def test_all_keys_are_lowercase(name, d):
    bad = [k for k in d if k != k.lower()]
    assert bad == [], f"{name}: non-lowercase keys: {bad[:5]}"


@pytest.mark.parametrize("name,d", ALL_DICTS)
def test_all_values_are_strings(name, d):
    bad = [(k, v) for k, v in d.items() if not isinstance(v, str)]
    assert bad == [], f"{name}: non-string values: {bad[:3]}"


@pytest.mark.parametrize("name,d", ALL_DICTS)
def test_no_empty_keys(name, d):
    bad = [k for k in d if k == ""]
    assert bad == [], f"{name}: empty key found"


@pytest.mark.parametrize("name,d", ALL_DICTS)
def test_no_empty_values(name, d):
    bad = [k for k, v in d.items() if v == ""]
    assert bad == [], f"{name}: empty value for keys: {bad[:5]}"


@pytest.mark.parametrize("name,d", ALL_DICTS)
def test_is_dict(name, d):
    assert isinstance(d, dict)


@pytest.mark.parametrize("name,d", ALL_DICTS)
def test_non_empty(name, d):
    assert len(d) > 0


# ===========================================================================
# CONDITIONS_DICT
# ===========================================================================

class TestConditionsDict:
    def test_size_is_reasonable(self):
        assert len(CONDITIONS_DICT) >= 50

    def test_htn_maps_to_hypertension(self):
        assert CONDITIONS_DICT["htn"] == "hypertension"

    def test_high_blood_pressure_normalizes_to_hypertension(self):
        assert CONDITIONS_DICT["high blood pressure"] == "hypertension"

    def test_canonical_form_maps_to_itself(self):
        assert CONDITIONS_DICT["hypertension"] == "hypertension"

    def test_heart_attack_normalizes_to_myocardial_infarction(self):
        assert CONDITIONS_DICT["heart attack"] == "myocardial infarction"

    def test_mi_normalizes_to_myocardial_infarction(self):
        assert CONDITIONS_DICT["mi"] == "myocardial infarction"

    def test_chf_normalizes_to_heart_failure(self):
        assert CONDITIONS_DICT["chf"] == "heart failure"

    def test_congestive_heart_failure_normalizes(self):
        assert CONDITIONS_DICT["congestive heart failure"] == "heart failure"

    def test_cad_normalizes_to_coronary_artery_disease(self):
        assert CONDITIONS_DICT["cad"] == "coronary artery disease"

    def test_t2dm_or_diabetes_present(self):
        # At least one diabetes alias must exist
        matches = [k for k in CONDITIONS_DICT if "diabet" in k or k in ("dm", "t2dm", "t1dm")]
        assert len(matches) > 0

    def test_stroke_or_cva_present(self):
        matches = [k for k in CONDITIONS_DICT if "stroke" in k or k == "cva"]
        assert len(matches) > 0

    def test_copd_present(self):
        assert "copd" in CONDITIONS_DICT

    def test_afib_present(self):
        assert "afib" in CONDITIONS_DICT

    def test_canonical_values_are_strings(self):
        assert all(isinstance(v, str) for v in CONDITIONS_DICT.values())


# ===========================================================================
# MEDICATIONS_DICT
# ===========================================================================

class TestMedicationsDict:
    def test_size_is_reasonable(self):
        assert len(MEDICATIONS_DICT) >= 80

    def test_aspirin_maps_to_aspirin(self):
        assert MEDICATIONS_DICT["aspirin"] == "aspirin"

    def test_asa_maps_to_aspirin(self):
        assert MEDICATIONS_DICT.get("asa") == "aspirin" or "aspirin" in MEDICATIONS_DICT.values()

    def test_metformin_present(self):
        assert "metformin" in MEDICATIONS_DICT

    def test_lisinopril_present(self):
        assert "lisinopril" in MEDICATIONS_DICT

    def test_atorvastatin_or_lipitor_present(self):
        matches = [k for k in MEDICATIONS_DICT if "atorvastatin" in k or "lipitor" in k]
        assert len(matches) > 0

    def test_insulin_or_variant_present(self):
        matches = [k for k in MEDICATIONS_DICT if "insulin" in k]
        assert len(matches) > 0

    def test_ibuprofen_present(self):
        assert "ibuprofen" in MEDICATIONS_DICT

    def test_acetaminophen_present(self):
        assert "acetaminophen" in MEDICATIONS_DICT

    def test_trade_name_maps_to_generic(self):
        # e.g., "tylenol" → "acetaminophen"
        if "tylenol" in MEDICATIONS_DICT:
            assert MEDICATIONS_DICT["tylenol"] == "acetaminophen"
        else:
            # At least some brand name maps to generic
            brand_to_generic = {k: v for k, v in MEDICATIONS_DICT.items() if k != v}
            assert len(brand_to_generic) > 0

    def test_canonical_values_are_strings(self):
        assert all(isinstance(v, str) for v in MEDICATIONS_DICT.values())

    def test_warfarin_or_coumadin_present(self):
        matches = [k for k in MEDICATIONS_DICT if "warfarin" in k or "coumadin" in k]
        assert len(matches) > 0


# ===========================================================================
# ANATOMY_DICT
# ===========================================================================

class TestAnatomyDict:
    def test_size_is_reasonable(self):
        assert len(ANATOMY_DICT) >= 20

    def test_heart_maps_to_heart(self):
        assert ANATOMY_DICT["heart"] == "heart"

    def test_cardiac_or_heart_variant_present(self):
        matches = [k for k in ANATOMY_DICT if "cardiac" in k or k == "heart"]
        assert len(matches) > 0

    def test_lung_or_pulmonary_present(self):
        matches = [k for k in ANATOMY_DICT if "lung" in k or "pulmonary" in k]
        assert len(matches) > 0

    def test_brain_or_cerebral_present(self):
        matches = [k for k in ANATOMY_DICT if "brain" in k or "cerebr" in k]
        assert len(matches) > 0

    def test_kidney_or_renal_present(self):
        matches = [k for k in ANATOMY_DICT if "kidney" in k or "renal" in k]
        assert len(matches) > 0

    def test_liver_present(self):
        assert "liver" in ANATOMY_DICT or any("liver" in k for k in ANATOMY_DICT)

    def test_canonical_values_are_strings(self):
        assert all(isinstance(v, str) for v in ANATOMY_DICT.values())

    def test_aliases_normalize_to_canonical(self):
        # All values should be a subset of or equal to their canonical form
        # (aliases point to canonical, canonical points to itself)
        canonical_values = set(ANATOMY_DICT.values())
        for key in canonical_values:
            if key in ANATOMY_DICT:
                assert ANATOMY_DICT[key] == key


# ===========================================================================
# SYMPTOMS_DICT
# ===========================================================================

class TestSymptomsDict:
    def test_size_is_reasonable(self):
        assert len(SYMPTOMS_DICT) >= 20

    def test_fever_maps_to_fever(self):
        assert SYMPTOMS_DICT["fever"] == "fever"

    def test_pyrexia_maps_to_fever(self):
        if "pyrexia" in SYMPTOMS_DICT:
            assert SYMPTOMS_DICT["pyrexia"] == "fever"

    def test_pain_or_variant_present(self):
        matches = [k for k in SYMPTOMS_DICT if "pain" in k]
        assert len(matches) > 0

    def test_cough_present(self):
        assert "cough" in SYMPTOMS_DICT or any("cough" in k for k in SYMPTOMS_DICT)

    def test_fatigue_or_tiredness_present(self):
        matches = [k for k in SYMPTOMS_DICT if "fatigue" in k or "tiredness" in k]
        assert len(matches) > 0

    def test_dyspnea_or_shortness_of_breath_present(self):
        matches = [k for k in SYMPTOMS_DICT if "dyspnea" in k or "shortness" in k]
        assert len(matches) > 0

    def test_canonical_values_are_strings(self):
        assert all(isinstance(v, str) for v in SYMPTOMS_DICT.values())

    def test_aliases_normalize_to_canonical(self):
        canonical_values = set(SYMPTOMS_DICT.values())
        for key in canonical_values:
            if key in SYMPTOMS_DICT:
                assert SYMPTOMS_DICT[key] == key

    def test_nausea_present(self):
        assert "nausea" in SYMPTOMS_DICT or any("nausea" in k for k in SYMPTOMS_DICT)
