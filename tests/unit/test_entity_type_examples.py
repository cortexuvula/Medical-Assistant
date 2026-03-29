"""
Tests for ENTITY_TYPE_EXAMPLES dict in src/rag/data/generate_prototypes.py.

This is a pure data structure — no network calls or heavy dependencies required.
The module imports utils.structured_logging and lives inside the rag package,
whose __init__.py pulls in pydantic and other heavy deps.  We stub everything
needed before touching the import machinery so the test has zero runtime deps
beyond the stdlib.
"""

import sys
import importlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
src_root = project_root / "src"

# Insert src onto the path first so our stubs win.
for p in (str(project_root), str(src_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Stub every heavy dependency before anything in the rag tree is imported.
# Order matters: stub parent packages before sub-packages.
_STUBS = [
    "utils.structured_logging",
    "pydantic",
    "rag",
    "rag.models",
    "rag.search_config",
    "rag.data",
]
for _mod in _STUBS:
    sys.modules.setdefault(_mod, MagicMock())

# Now import the target module directly, bypassing rag/__init__.py entirely.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "rag.data.generate_prototypes",
    src_root / "rag" / "data" / "generate_prototypes.py",
)
_mod = _ilu.module_from_spec(_spec)
sys.modules["rag.data.generate_prototypes"] = _mod
_spec.loader.exec_module(_mod)

ENTITY_TYPE_EXAMPLES = _mod.ENTITY_TYPE_EXAMPLES

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {"medication", "condition", "symptom", "procedure", "lab_test", "anatomy"}
EXPECTED_COUNT_PER_CATEGORY = 20


# ===========================================================================
# TestEntityTypeExamplesStructure
# ===========================================================================


class TestEntityTypeExamplesStructure:
    """Top-level structural guarantees for the ENTITY_TYPE_EXAMPLES dict."""

    def test_is_dict(self):
        assert isinstance(ENTITY_TYPE_EXAMPLES, dict)

    def test_has_exactly_six_keys(self):
        assert len(ENTITY_TYPE_EXAMPLES) == 6

    def test_keys_are_exactly_expected_set(self):
        assert set(ENTITY_TYPE_EXAMPLES.keys()) == EXPECTED_KEYS

    def test_each_value_is_a_list(self):
        for key, value in ENTITY_TYPE_EXAMPLES.items():
            assert isinstance(value, list), f"Value for '{key}' is not a list"

    @pytest.mark.parametrize("category", sorted(EXPECTED_KEYS))
    def test_each_category_has_exactly_20_entries(self, category):
        assert len(ENTITY_TYPE_EXAMPLES[category]) == EXPECTED_COUNT_PER_CATEGORY

    def test_all_entries_are_non_empty_strings(self):
        for key, entries in ENTITY_TYPE_EXAMPLES.items():
            for entry in entries:
                assert isinstance(entry, str), f"Entry in '{key}' is not a string: {entry!r}"
                assert entry, f"Empty string found in '{key}'"

    def test_no_duplicate_entries_within_any_category(self):
        for key, entries in ENTITY_TYPE_EXAMPLES.items():
            assert len(entries) == len(set(entries)), (
                f"Duplicate entries found in '{key}'"
            )

    def test_no_entry_is_just_whitespace(self):
        for key, entries in ENTITY_TYPE_EXAMPLES.items():
            for entry in entries:
                assert entry.strip(), f"Whitespace-only entry found in '{key}': {entry!r}"

    def test_all_entries_contain_at_least_one_space(self):
        """All entries are multi-word phrases, not bare single tokens."""
        for key, entries in ENTITY_TYPE_EXAMPLES.items():
            for entry in entries:
                assert " " in entry, (
                    f"Single-word entry (no space) found in '{key}': {entry!r}"
                )

    @pytest.mark.parametrize("category", sorted(EXPECTED_KEYS))
    def test_parametrized_each_category_has_20_entries(self, category):
        """Redundant parametrized form for per-category visibility in test output."""
        assert len(ENTITY_TYPE_EXAMPLES[category]) == EXPECTED_COUNT_PER_CATEGORY


# ===========================================================================
# TestMedicationExamples
# ===========================================================================


class TestMedicationExamples:
    """Detailed checks for the 'medication' category."""

    @pytest.fixture(autouse=True)
    def category(self):
        self.entries = ENTITY_TYPE_EXAMPLES["medication"]

    def test_is_list(self):
        assert isinstance(self.entries, list)

    def test_has_20_entries(self):
        assert len(self.entries) == 20

    def test_contains_metoprolol(self):
        assert "metoprolol 50mg tablet" in self.entries

    def test_contains_warfarin(self):
        assert "warfarin anticoagulant" in self.entries

    def test_contains_metformin(self):
        assert "metformin diabetes pill" in self.entries

    def test_contains_aspirin(self):
        assert "aspirin antiplatelet therapy" in self.entries

    def test_contains_atorvastatin(self):
        assert "atorvastatin cholesterol drug" in self.entries

    def test_contains_insulin_glargine(self):
        assert "insulin glargine injection" in self.entries

    def test_contains_sertraline(self):
        assert "sertraline antidepressant SSRI" in self.entries

    def test_all_entries_are_strings(self):
        for entry in self.entries:
            assert isinstance(entry, str)

    def test_no_duplicate_entries(self):
        assert len(self.entries) == len(set(self.entries))

    def test_all_are_non_empty(self):
        for entry in self.entries:
            assert entry.strip()


# ===========================================================================
# TestConditionExamples
# ===========================================================================


class TestConditionExamples:
    """Detailed checks for the 'condition' category."""

    @pytest.fixture(autouse=True)
    def category(self):
        self.entries = ENTITY_TYPE_EXAMPLES["condition"]

    def test_contains_hypertension(self):
        assert "hypertension high blood pressure" in self.entries

    def test_contains_type2_diabetes(self):
        assert "type 2 diabetes mellitus" in self.entries

    def test_contains_coronary_artery_disease(self):
        assert "coronary artery disease CAD" in self.entries

    def test_contains_atrial_fibrillation(self):
        assert "atrial fibrillation arrhythmia" in self.entries

    def test_contains_pneumonia(self):
        assert "pneumonia lung infection" in self.entries

    def test_contains_chronic_kidney_disease(self):
        assert "chronic kidney disease CKD" in self.entries

    def test_has_20_entries(self):
        assert len(self.entries) == 20

    def test_all_entries_are_non_empty_strings(self):
        for entry in self.entries:
            assert isinstance(entry, str)
            assert entry.strip()


# ===========================================================================
# TestSymptomExamples
# ===========================================================================


class TestSymptomExamples:
    """Detailed checks for the 'symptom' category."""

    @pytest.fixture(autouse=True)
    def category(self):
        self.entries = ENTITY_TYPE_EXAMPLES["symptom"]

    def test_contains_chest_pain(self):
        assert "chest pain angina discomfort" in self.entries

    def test_contains_shortness_of_breath(self):
        assert "shortness of breath dyspnea" in self.entries

    def test_contains_headache(self):
        assert "headache cephalgia" in self.entries

    def test_contains_fatigue(self):
        assert "fatigue tiredness exhaustion" in self.entries

    def test_contains_nausea(self):
        assert "nausea feeling sick to stomach" in self.entries

    def test_contains_fever(self):
        assert "fever elevated temperature pyrexia" in self.entries

    def test_has_20_entries(self):
        assert len(self.entries) == 20

    def test_all_entries_are_non_empty_strings(self):
        for entry in self.entries:
            assert isinstance(entry, str)
            assert entry.strip()


# ===========================================================================
# TestProcedureExamples
# ===========================================================================


class TestProcedureExamples:
    """Detailed checks for the 'procedure' category."""

    @pytest.fixture(autouse=True)
    def category(self):
        self.entries = ENTITY_TYPE_EXAMPLES["procedure"]

    def test_contains_mri(self):
        assert "MRI magnetic resonance imaging scan" in self.entries

    def test_contains_ct_scan(self):
        assert "CT computed tomography scan" in self.entries

    def test_contains_colonoscopy(self):
        assert "colonoscopy bowel examination" in self.entries

    def test_contains_echocardiogram(self):
        assert "echocardiogram cardiac ultrasound echo" in self.entries

    def test_contains_biopsy(self):
        assert "biopsy tissue sampling" in self.entries

    def test_contains_xray(self):
        assert "X-ray radiograph imaging" in self.entries

    def test_has_20_entries(self):
        assert len(self.entries) == 20

    def test_all_entries_are_non_empty_strings(self):
        for entry in self.entries:
            assert isinstance(entry, str)
            assert entry.strip()


# ===========================================================================
# TestLabTestExamples
# ===========================================================================


class TestLabTestExamples:
    """Detailed checks for the 'lab_test' category."""

    @pytest.fixture(autouse=True)
    def category(self):
        self.entries = ENTITY_TYPE_EXAMPLES["lab_test"]

    def test_contains_cbc(self):
        assert "complete blood count CBC hemogram" in self.entries

    def test_contains_hba1c(self):
        assert "hemoglobin A1c HbA1c glycated" in self.entries

    def test_contains_tsh(self):
        assert "thyroid stimulating hormone TSH" in self.entries

    def test_contains_troponin(self):
        assert "troponin cardiac enzyme marker" in self.entries

    def test_contains_lipid_panel(self):
        assert "lipid panel cholesterol triglycerides" in self.entries

    def test_contains_creatinine(self):
        assert "creatinine renal function" in self.entries

    def test_has_20_entries(self):
        assert len(self.entries) == 20

    def test_all_entries_are_non_empty_strings(self):
        for entry in self.entries:
            assert isinstance(entry, str)
            assert entry.strip()


# ===========================================================================
# TestAnatomyExamples
# ===========================================================================


class TestAnatomyExamples:
    """Detailed checks for the 'anatomy' category."""

    @pytest.fixture(autouse=True)
    def category(self):
        self.entries = ENTITY_TYPE_EXAMPLES["anatomy"]

    def test_contains_heart(self):
        assert "heart cardiac muscle organ" in self.entries

    def test_contains_lung(self):
        assert "lung pulmonary respiratory organ" in self.entries

    def test_contains_liver(self):
        assert "liver hepatic organ" in self.entries

    def test_contains_kidney(self):
        assert "kidney renal organ" in self.entries

    def test_contains_brain(self):
        assert "brain cerebral nervous system" in self.entries

    def test_contains_coronary_artery(self):
        assert "coronary artery cardiac vessel" in self.entries

    def test_has_20_entries(self):
        assert len(self.entries) == 20

    def test_all_entries_are_non_empty_strings(self):
        for entry in self.entries:
            assert isinstance(entry, str)
            assert entry.strip()


# ===========================================================================
# TestCrossCategory
# ===========================================================================


class TestCrossCategory:
    """Tests that span multiple or all categories."""

    def test_no_cross_category_duplicates(self):
        """No entry may appear in more than one category."""
        all_entries = [e for lst in ENTITY_TYPE_EXAMPLES.values() for e in lst]
        assert len(all_entries) == len(set(all_entries)), (
            "One or more entries appear in multiple categories"
        )

    def test_total_entry_count_is_120(self):
        all_entries = [e for lst in ENTITY_TYPE_EXAMPLES.values() for e in lst]
        assert len(all_entries) == 6 * 20

    @pytest.mark.parametrize("category", sorted(EXPECTED_KEYS))
    def test_each_key_is_present(self, category):
        assert category in ENTITY_TYPE_EXAMPLES

    @pytest.mark.parametrize("category", sorted(EXPECTED_KEYS))
    def test_each_category_contains_at_least_one_lowercase_letter(self, category):
        """Medical terminology entries should contain lowercase letters."""
        entries = ENTITY_TYPE_EXAMPLES[category]
        for entry in entries:
            assert any(c.islower() for c in entry), (
                f"Entry in '{category}' has no lowercase letters: {entry!r}"
            )

    @pytest.mark.parametrize("category", sorted(EXPECTED_KEYS))
    def test_no_leading_or_trailing_whitespace_in_entries(self, category):
        entries = ENTITY_TYPE_EXAMPLES[category]
        for entry in entries:
            assert entry == entry.strip(), (
                f"Leading/trailing whitespace in '{category}': {entry!r}"
            )

    def test_all_category_lists_are_non_empty(self):
        for key, entries in ENTITY_TYPE_EXAMPLES.items():
            assert len(entries) > 0, f"Category '{key}' is empty"

    def test_medication_and_condition_share_no_entries(self):
        med = set(ENTITY_TYPE_EXAMPLES["medication"])
        cond = set(ENTITY_TYPE_EXAMPLES["condition"])
        assert med.isdisjoint(cond)

    def test_symptom_and_procedure_share_no_entries(self):
        symp = set(ENTITY_TYPE_EXAMPLES["symptom"])
        proc = set(ENTITY_TYPE_EXAMPLES["procedure"])
        assert symp.isdisjoint(proc)

    def test_lab_test_and_anatomy_share_no_entries(self):
        lab = set(ENTITY_TYPE_EXAMPLES["lab_test"])
        anat = set(ENTITY_TYPE_EXAMPLES["anatomy"])
        assert lab.isdisjoint(anat)
