"""
Tests for src/processing/analysis_storage.py

Covers AnalysisStorage: save_medication/differential/compliance_analysis,
get_analyses_for_recording, get/has for each type, get_recent_* methods,
db lazy-init property, and get_analysis_storage singleton.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.analysis_storage import AnalysisStorage, get_analysis_storage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_storage(db=None):
    """Create an AnalysisStorage with an explicit mock db."""
    if db is None:
        db = MagicMock()
        db.save_analysis_result.return_value = 42
        db.get_analysis_results_for_recording.return_value = []
        db.get_recent_analysis_results.return_value = []
    return AnalysisStorage(db=db)


def _mock_db(analysis_id=42, results=None):
    """Build a mock db with configurable returns."""
    db = MagicMock()
    db.save_analysis_result.return_value = analysis_id
    db.get_analysis_results_for_recording.return_value = results or []
    db.get_recent_analysis_results.return_value = results or []
    return db


# ===========================================================================
# Init + db property
# ===========================================================================

class TestAnalysisStorageInit:
    def test_explicit_db_set(self):
        mock_db = _mock_db()
        storage = AnalysisStorage(db=mock_db)
        assert storage._db is mock_db

    def test_db_property_returns_explicit_db(self):
        mock_db = _mock_db()
        storage = AnalysisStorage(db=mock_db)
        assert storage.db is mock_db

    def test_db_property_returns_set_db(self):
        """When _db is set to a non-None value, db property returns it directly."""
        storage = AnalysisStorage(db=None)
        mock_db_instance = MagicMock()
        storage._db = mock_db_instance
        assert storage.db is mock_db_instance

    def test_db_property_none_initially(self):
        storage = AnalysisStorage(db=None)
        assert storage._db is None

    def test_type_constants(self):
        assert AnalysisStorage.TYPE_MEDICATION == "medication"
        assert AnalysisStorage.TYPE_DIFFERENTIAL == "differential"
        assert AnalysisStorage.TYPE_COMPLIANCE == "compliance"


# ===========================================================================
# save_medication_analysis
# ===========================================================================

class TestSaveMedicationAnalysis:
    def test_returns_analysis_id_on_success(self):
        storage = _make_storage(_mock_db(analysis_id=99))
        result = storage.save_medication_analysis("Metformin review")
        assert result == 99

    def test_calls_db_with_medication_type(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_medication_analysis("Aspirin")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_type"] == "medication"

    def test_passes_result_text(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_medication_analysis("Drug interactions found")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["result_text"] == "Drug interactions found"

    def test_passes_recording_id(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_medication_analysis("text", recording_id=7)
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["recording_id"] == 7

    def test_default_analysis_subtype(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_medication_analysis("text")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_subtype"] == "comprehensive"

    def test_custom_analysis_subtype(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_medication_analysis("text", analysis_subtype="interactions")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_subtype"] == "interactions"

    def test_passes_result_json(self):
        db = _mock_db()
        storage = _make_storage(db)
        json_data = {"medications": ["Aspirin"]}
        storage.save_medication_analysis("text", result_json=json_data)
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["result_json"] == json_data

    def test_returns_none_on_exception(self):
        db = _mock_db()
        db.save_analysis_result.side_effect = RuntimeError("DB error")
        storage = _make_storage(db)
        result = storage.save_medication_analysis("text")
        assert result is None

    def test_passes_metadata(self):
        db = _mock_db()
        storage = _make_storage(db)
        metadata = {"count": 3}
        storage.save_medication_analysis("text", metadata=metadata)
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["metadata"] == metadata


# ===========================================================================
# save_differential_diagnosis
# ===========================================================================

class TestSaveDifferentialDiagnosis:
    def test_returns_id_on_success(self):
        storage = _make_storage(_mock_db(analysis_id=55))
        result = storage.save_differential_diagnosis("Chest pain DDx")
        assert result == 55

    def test_calls_db_with_differential_type(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_differential_diagnosis("DDx text")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_type"] == "differential"

    def test_passes_recording_id(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_differential_diagnosis("text", recording_id=12)
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["recording_id"] == 12

    def test_returns_none_on_exception(self):
        db = _mock_db()
        db.save_analysis_result.side_effect = Exception("timeout")
        storage = _make_storage(db)
        assert storage.save_differential_diagnosis("text") is None

    def test_default_analysis_subtype_is_comprehensive(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_differential_diagnosis("text")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_subtype"] == "comprehensive"


# ===========================================================================
# save_compliance_analysis
# ===========================================================================

class TestSaveComplianceAnalysis:
    def test_returns_id_on_success(self):
        storage = _make_storage(_mock_db(analysis_id=77))
        result = storage.save_compliance_analysis("Guideline compliance")
        assert result == 77

    def test_calls_db_with_compliance_type(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_compliance_analysis("text")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_type"] == "compliance"

    def test_default_analysis_subtype_is_guidelines(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.save_compliance_analysis("text")
        call_kwargs = db.save_analysis_result.call_args[1]
        assert call_kwargs["analysis_subtype"] == "guidelines"

    def test_returns_none_on_exception(self):
        db = _mock_db()
        db.save_analysis_result.side_effect = RuntimeError("fail")
        storage = _make_storage(db)
        assert storage.save_compliance_analysis("text") is None


# ===========================================================================
# get_analyses_for_recording
# ===========================================================================

class TestGetAnalysesForRecording:
    def test_returns_dict_with_all_three_types(self):
        storage = _make_storage()
        result = storage.get_analyses_for_recording(1)
        assert set(result.keys()) == {"medication", "differential", "compliance"}

    def test_all_none_when_no_results(self):
        storage = _make_storage()
        result = storage.get_analyses_for_recording(1)
        assert result["medication"] is None
        assert result["differential"] is None
        assert result["compliance"] is None

    def test_returns_first_result_for_each_type(self):
        db = MagicMock()
        med = {"id": 1, "type": "medication"}
        diff = {"id": 2, "type": "differential"}
        comp = {"id": 3, "type": "compliance"}

        def side_effect(recording_id, analysis_type):
            if analysis_type == "medication":
                return [med]
            if analysis_type == "differential":
                return [diff]
            if analysis_type == "compliance":
                return [comp]
            return []

        db.get_analysis_results_for_recording.side_effect = side_effect
        storage = AnalysisStorage(db=db)
        result = storage.get_analyses_for_recording(1)
        assert result["medication"] == med
        assert result["differential"] == diff
        assert result["compliance"] == comp

    def test_returns_partial_results_when_some_missing(self):
        db = MagicMock()
        db.get_analysis_results_for_recording.side_effect = lambda **kw: (
            [{"id": 1}] if kw["analysis_type"] == "medication" else []
        )
        storage = AnalysisStorage(db=db)
        result = storage.get_analyses_for_recording(1)
        assert result["medication"] is not None
        assert result["differential"] is None

    def test_returns_empty_result_on_db_exception(self):
        db = MagicMock()
        db.get_analysis_results_for_recording.side_effect = RuntimeError("DB error")
        storage = AnalysisStorage(db=db)
        result = storage.get_analyses_for_recording(1)
        assert result == {"medication": None, "differential": None, "compliance": None}


# ===========================================================================
# get_medication_analysis / has_medication_analysis
# ===========================================================================

class TestGetMedicationAnalysis:
    def test_returns_first_result_when_exists(self):
        db = _mock_db(results=[{"id": 1, "text": "Med analysis"}])
        storage = _make_storage(db)
        result = storage.get_medication_analysis(1)
        assert result == {"id": 1, "text": "Med analysis"}

    def test_returns_none_when_empty(self):
        storage = _make_storage()
        result = storage.get_medication_analysis(1)
        assert result is None

    def test_returns_none_on_exception(self):
        db = _mock_db()
        db.get_analysis_results_for_recording.side_effect = RuntimeError("fail")
        storage = _make_storage(db)
        result = storage.get_medication_analysis(1)
        assert result is None

    def test_has_medication_analysis_true_when_exists(self):
        db = _mock_db(results=[{"id": 1}])
        storage = _make_storage(db)
        assert storage.has_medication_analysis(1) is True

    def test_has_medication_analysis_false_when_empty(self):
        storage = _make_storage()
        assert storage.has_medication_analysis(1) is False


# ===========================================================================
# get_differential_diagnosis / has_differential_diagnosis
# ===========================================================================

class TestGetDifferentialDiagnosis:
    def test_returns_first_result_when_exists(self):
        db = _mock_db(results=[{"id": 2, "text": "DDx"}])
        storage = _make_storage(db)
        result = storage.get_differential_diagnosis(1)
        assert result == {"id": 2, "text": "DDx"}

    def test_returns_none_when_empty(self):
        storage = _make_storage()
        assert storage.get_differential_diagnosis(1) is None

    def test_returns_none_on_exception(self):
        db = _mock_db()
        db.get_analysis_results_for_recording.side_effect = RuntimeError("fail")
        storage = _make_storage(db)
        assert storage.get_differential_diagnosis(1) is None

    def test_has_differential_diagnosis_true_when_exists(self):
        db = _mock_db(results=[{"id": 2}])
        storage = _make_storage(db)
        assert storage.has_differential_diagnosis(1) is True

    def test_has_differential_diagnosis_false_when_empty(self):
        storage = _make_storage()
        assert storage.has_differential_diagnosis(1) is False


# ===========================================================================
# get_compliance_analysis / has_compliance_analysis
# ===========================================================================

class TestGetComplianceAnalysis:
    def test_returns_first_result_when_exists(self):
        db = _mock_db(results=[{"id": 3, "text": "Compliance OK"}])
        storage = _make_storage(db)
        result = storage.get_compliance_analysis(1)
        assert result == {"id": 3, "text": "Compliance OK"}

    def test_returns_none_when_empty(self):
        storage = _make_storage()
        assert storage.get_compliance_analysis(1) is None

    def test_returns_none_on_exception(self):
        db = _mock_db()
        db.get_analysis_results_for_recording.side_effect = RuntimeError("fail")
        storage = _make_storage(db)
        assert storage.get_compliance_analysis(1) is None

    def test_has_compliance_analysis_true_when_exists(self):
        db = _mock_db(results=[{"id": 3}])
        storage = _make_storage(db)
        assert storage.has_compliance_analysis(1) is True

    def test_has_compliance_analysis_false_when_empty(self):
        storage = _make_storage()
        assert storage.has_compliance_analysis(1) is False


# ===========================================================================
# get_recent_medication_analyses
# ===========================================================================

class TestGetRecentMedicationAnalyses:
    def test_returns_list(self):
        storage = _make_storage()
        result = storage.get_recent_medication_analyses()
        assert isinstance(result, list)

    def test_returns_results_from_db(self):
        db = _mock_db(results=[{"id": 1}, {"id": 2}])
        storage = _make_storage(db)
        result = storage.get_recent_medication_analyses()
        assert len(result) == 2

    def test_passes_limit_to_db(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.get_recent_medication_analyses(limit=5)
        db.get_recent_analysis_results.assert_called_once_with(
            analysis_type="medication", limit=5
        )

    def test_default_limit_is_10(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.get_recent_medication_analyses()
        db.get_recent_analysis_results.assert_called_once_with(
            analysis_type="medication", limit=10
        )

    def test_returns_empty_list_on_exception(self):
        db = _mock_db()
        db.get_recent_analysis_results.side_effect = RuntimeError("fail")
        storage = _make_storage(db)
        result = storage.get_recent_medication_analyses()
        assert result == []


# ===========================================================================
# get_recent_differential_diagnoses
# ===========================================================================

class TestGetRecentDifferentialDiagnoses:
    def test_returns_list(self):
        storage = _make_storage()
        result = storage.get_recent_differential_diagnoses()
        assert isinstance(result, list)

    def test_passes_limit_to_db(self):
        db = _mock_db()
        storage = _make_storage(db)
        storage.get_recent_differential_diagnoses(limit=3)
        db.get_recent_analysis_results.assert_called_once_with(
            analysis_type="differential", limit=3
        )

    def test_returns_empty_list_on_exception(self):
        db = _mock_db()
        db.get_recent_analysis_results.side_effect = RuntimeError("fail")
        storage = _make_storage(db)
        assert storage.get_recent_differential_diagnoses() == []


# ===========================================================================
# get_analysis_storage singleton
# ===========================================================================

class TestGetAnalysisStorage:
    def test_returns_analysis_storage_instance(self):
        import processing.analysis_storage as module
        module._analysis_storage = None  # Reset singleton
        storage = get_analysis_storage()
        assert isinstance(storage, AnalysisStorage)
        module._analysis_storage = None  # Cleanup

    def test_returns_same_instance_on_repeated_calls(self):
        import processing.analysis_storage as module
        module._analysis_storage = None
        s1 = get_analysis_storage()
        s2 = get_analysis_storage()
        assert s1 is s2
        module._analysis_storage = None  # Cleanup
