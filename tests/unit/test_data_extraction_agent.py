"""
Unit tests for DataExtractionAgent.

Tests cover:
- Extraction type determination
- Vital signs extraction
- Laboratory values extraction
- Medications extraction
- Diagnoses extraction with ICD codes
- Procedures extraction
- Structured JSON output
"""

import pytest
import json
from unittest.mock import Mock, patch

from ai.agents.data_extraction import DataExtractionAgent
from ai.agents.models import AgentConfig, AgentTask, AgentResponse
from ai.agents.ai_caller import MockAICaller


@pytest.fixture
def extraction_agent(mock_ai_caller):
    """Create a DataExtractionAgent with mock AI caller."""
    return DataExtractionAgent(ai_caller=mock_ai_caller)


class TestExtractionTypeRouting:
    """Tests for extraction type determination."""

    def test_determine_vitals_type(self, extraction_agent):
        """Test detection of vital signs extraction."""
        task = AgentTask(
            task_description="Extract vital signs from the note",
            input_data={}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "vitals"

    def test_determine_labs_type(self, extraction_agent):
        """Test detection of laboratory values extraction."""
        task = AgentTask(
            task_description="Extract laboratory values",
            input_data={}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "labs"

    def test_determine_medications_type(self, extraction_agent):
        """Test detection of medications extraction."""
        task = AgentTask(
            task_description="Extract all medications",
            input_data={}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "medications"

    def test_determine_diagnoses_type(self, extraction_agent):
        """Test detection of diagnoses extraction."""
        task = AgentTask(
            task_description="Extract diagnoses with ICD codes",
            input_data={}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "diagnoses"

    def test_determine_procedures_type(self, extraction_agent):
        """Test detection of procedures extraction."""
        task = AgentTask(
            task_description="Extract procedures",
            input_data={}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "procedures"

    def test_determine_comprehensive_default(self, extraction_agent):
        """Test default to comprehensive extraction."""
        task = AgentTask(
            task_description="Extract all clinical data",
            input_data={}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "comprehensive"

    def test_explicit_extraction_type(self, extraction_agent):
        """Test explicit extraction type in input_data."""
        task = AgentTask(
            task_description="Extract data",
            input_data={"extraction_type": "medications"}
        )

        extraction_type = extraction_agent._determine_extraction_type(task)

        assert extraction_type == "medications"


class TestVitalSignsExtraction:
    """Tests for vital signs extraction."""

    def test_extract_blood_pressure(self, extraction_agent):
        """Test extraction of blood pressure."""
        text = "BP: 140/90 mmHg"
        vitals = extraction_agent._parse_vital_signs(text)

        assert len(vitals) >= 1
        bp_vitals = [v for v in vitals if v["type"] == "blood_pressure"]
        assert len(bp_vitals) >= 1

    def test_extract_heart_rate(self, extraction_agent):
        """Test extraction of heart rate."""
        text = "Heart Rate: 88 bpm"
        vitals = extraction_agent._parse_vital_signs(text)

        hr_vitals = [v for v in vitals if v["type"] == "heart_rate"]
        assert len(hr_vitals) >= 1

    def test_extract_temperature(self, extraction_agent):
        """Test extraction of temperature."""
        text = "Temp: 98.6°F"
        vitals = extraction_agent._parse_vital_signs(text)

        temp_vitals = [v for v in vitals if v["type"] == "temperature"]
        assert len(temp_vitals) >= 1

    def test_extract_oxygen_saturation(self, extraction_agent):
        """Test extraction of oxygen saturation."""
        text = "O2 Sat: 97% on room air"
        vitals = extraction_agent._parse_vital_signs(text)

        o2_vitals = [v for v in vitals if v["type"] == "oxygen_saturation"]
        assert len(o2_vitals) >= 1

    def test_extract_multiple_vitals(self, extraction_agent):
        """Test extraction of multiple vital signs."""
        text = """Vitals:
        BP: 120/80 mmHg
        HR: 72 bpm
        Temp: 98.2°F
        RR: 16/min
        O2: 98%"""

        vitals = extraction_agent._parse_vital_signs(text)

        assert len(vitals) >= 4


class TestLabValuesExtraction:
    """Tests for laboratory values extraction."""

    def test_extract_basic_lab(self, extraction_agent):
        """Test extraction of basic lab value."""
        text = "Hemoglobin: 14.2 g/dL (13.5-17.5)"
        labs = extraction_agent._parse_lab_values(text)

        assert len(labs) >= 1
        assert any("Hemoglobin" in lab.get("test", "") for lab in labs)

    def test_extract_lab_with_reference(self, extraction_agent):
        """Test extraction of lab with reference range."""
        text = "Glucose: 110 mg/dL (ref: 70-100)"
        labs = extraction_agent._parse_lab_values(text)

        if labs:
            assert "reference" in labs[0] or "110" in labs[0].get("value", "")


class TestMedicationsExtraction:
    """Tests for medications extraction."""

    def test_extract_medication_name(self, extraction_agent):
        """Test extraction of medication name."""
        text = "- Lisinopril 10mg PO daily"
        name = extraction_agent._extract_medication_name(text)

        assert "Lisinopril" in name or "lisinopril" in name.lower()

    def test_extract_dosage(self, extraction_agent):
        """Test extraction of medication dosage."""
        text = "Metformin 500mg twice daily"
        dosage = extraction_agent._extract_dosage(text)

        assert "500" in dosage
        assert "mg" in dosage.lower()

    def test_extract_frequency_bid(self, extraction_agent):
        """Test extraction of BID frequency."""
        text = "Take medication BID"
        frequency = extraction_agent._extract_frequency(text)

        assert "bid" in frequency.lower()

    def test_extract_frequency_daily(self, extraction_agent):
        """Test extraction of daily frequency."""
        text = "Once daily in the morning"
        frequency = extraction_agent._extract_frequency(text)

        assert "daily" in frequency.lower() or "once" in frequency.lower()

    def test_parse_medications(self, extraction_agent):
        """Test parsing multiple medications."""
        text = """Medications:
        - Lisinopril 10mg daily
        - Metformin 500mg BID
        - Aspirin 81mg daily"""

        meds = extraction_agent._parse_medications(text)

        assert len(meds) >= 2


class TestDiagnosesExtraction:
    """Tests for diagnoses extraction with ICD codes."""

    def test_parse_diagnosis_with_icd(self, extraction_agent):
        """Test parsing diagnosis with ICD code."""
        text = "- Type 2 Diabetes Mellitus (E11.9)"
        diagnoses = extraction_agent._parse_diagnoses(text)

        assert len(diagnoses) >= 1
        assert diagnoses[0]["icd_code"] == "E11.9"

    def test_parse_diagnosis_without_icd(self, extraction_agent):
        """Test parsing diagnosis without ICD code."""
        text = "- Hypertension"
        diagnoses = extraction_agent._parse_diagnoses(text)

        assert len(diagnoses) >= 1
        assert "hypertension" in diagnoses[0]["description"].lower()

    def test_parse_multiple_diagnoses(self, extraction_agent):
        """Test parsing multiple diagnoses."""
        # The _parse_diagnoses method expects lines with '-' or 'diagnos' keyword
        text = """Assessment:
        - Type 2 Diabetes (E11.9)
        - Essential Hypertension (I10)
        - Hyperlipidemia (E78.5)"""

        diagnoses = extraction_agent._parse_diagnoses(text)

        assert len(diagnoses) >= 2


class TestProceduresExtraction:
    """Tests for procedures extraction."""

    def test_determine_status_completed(self, extraction_agent):
        """Test status determination for completed procedures."""
        text = "ECG performed today"
        status = extraction_agent._determine_procedure_status(text)

        assert status == "completed"

    def test_determine_status_planned(self, extraction_agent):
        """Test status determination for planned procedures."""
        text = "MRI scheduled for next week"
        status = extraction_agent._determine_procedure_status(text)

        assert status == "planned"

    def test_determine_status_pending(self, extraction_agent):
        """Test status determination for pending procedures."""
        text = "Awaiting lab results"
        status = extraction_agent._determine_procedure_status(text)

        assert status == "pending"

    def test_parse_procedures(self, extraction_agent):
        """Test parsing procedures."""
        text = """Procedures:
        - ECG completed 01/15/2024
        - CT scan pending"""

        procedures = extraction_agent._parse_procedures(text)

        assert len(procedures) >= 1


class TestComprehensiveExtraction:
    """Tests for comprehensive data extraction."""

    def test_extract_all_data(self, extraction_agent, mock_ai_caller, sample_clinical_text):
        """Test comprehensive extraction."""
        mock_ai_caller.default_response = json.dumps({
            "vital_signs": [{"name": "blood_pressure", "value": "145/92 mmHg"}],
            "laboratory_values": [{"test": "Hemoglobin", "value": 14.2}],
            "medications": [{"name": "Lisinopril", "dosage": "10mg"}],
            "diagnoses": [{"description": "Hypertension", "icd10_code": "I10"}],
            "procedures": []
        })

        task = AgentTask(
            task_description="Extract all clinical data",
            input_data={"clinical_text": sample_clinical_text}
        )

        response = extraction_agent.execute(task)

        assert response.success is True
        assert "counts" in response.metadata
        assert response.metadata["counts"]["total"] > 0

    def test_extract_all_json_format(self, extraction_agent, mock_ai_caller, sample_clinical_text):
        """Test JSON output format."""
        mock_ai_caller.default_response = '{"vital_signs": [], "medications": []}'

        task = AgentTask(
            task_description="Extract data",
            input_data={
                "clinical_text": sample_clinical_text,
                "output_format": "json"
            }
        )

        response = extraction_agent.execute(task)

        assert response.success is True
        # Result should be valid JSON
        parsed = json.loads(response.result)
        assert isinstance(parsed, dict)

    def test_extract_without_clinical_text(self, extraction_agent, mock_ai_caller):
        """Test extraction without clinical text."""
        task = AgentTask(
            task_description="Extract data",
            input_data={}
        )

        response = extraction_agent.execute(task)

        assert response.success is False
        assert "No clinical text" in response.error


class TestStructuredJSONExtraction:
    """Tests for structured JSON extraction."""

    def test_structured_json_schema(self, extraction_agent):
        """Test that the JSON schema is well-defined."""
        schema = extraction_agent.COMPREHENSIVE_EXTRACTION_SCHEMA

        assert "vital_signs" in schema["properties"]
        assert "laboratory_values" in schema["properties"]
        assert "medications" in schema["properties"]
        assert "diagnoses" in schema["properties"]
        assert "procedures" in schema["properties"]

    def test_extract_structured_json(self, extraction_agent, mock_ai_caller, sample_clinical_text):
        """Test structured JSON extraction method."""
        mock_ai_caller.default_response = json.dumps({
            "vital_signs": [{"name": "BP", "value": "140/90"}],
            "laboratory_values": [],
            "medications": [],
            "diagnoses": [],
            "procedures": []
        })

        result = extraction_agent._extract_structured_json(sample_clinical_text, None)

        assert result is not None
        assert "vital_signs" in result

    def test_extract_structured_json_fallback(self, extraction_agent, mock_ai_caller, sample_clinical_text):
        """Test fallback when structured extraction fails."""
        mock_ai_caller.default_response = "Invalid JSON response"

        result = extraction_agent._extract_structured_json(sample_clinical_text, None)

        # Should return None to trigger fallback
        assert result is None


class TestOutputFormatting:
    """Tests for output formatting."""

    def test_format_as_text(self, extraction_agent):
        """Test formatting as readable text."""
        parsed_data = {
            "vital_signs": [{"name": "blood_pressure", "value": "120/80", "unit": "mmHg"}],
            "laboratory_values": [{"test": "Glucose", "value": 95, "unit": "mg/dL"}],
            "medications": [{"name": "Aspirin", "dosage": "81mg", "frequency": "daily"}],
            "diagnoses": [{"description": "Hypertension", "icd10_code": "I10"}],
            "procedures": []
        }

        text = extraction_agent._format_as_text(parsed_data)

        assert "VITAL SIGNS" in text
        assert "blood_pressure" in text.lower()
        assert "MEDICATIONS" in text
        assert "Aspirin" in text

    def test_format_as_text_empty(self, extraction_agent):
        """Test formatting empty data."""
        parsed_data = {
            "vital_signs": [],
            "laboratory_values": [],
            "medications": [],
            "diagnoses": [],
            "procedures": []
        }

        text = extraction_agent._format_as_text(parsed_data)

        assert "No clinical data extracted" in text

    def test_count_extracted_items(self, extraction_agent):
        """Test counting extracted items."""
        parsed_data = {
            "vital_signs": [{"name": "BP"}, {"name": "HR"}],
            "laboratory_values": [{"test": "Glucose"}],
            "medications": [{"name": "Med1"}, {"name": "Med2"}, {"name": "Med3"}],
            "diagnoses": [{"description": "Dx1"}],
            "procedures": []
        }

        counts = extraction_agent._count_extracted_items(parsed_data)

        assert counts["vital_signs"] == 2
        assert counts["laboratory_values"] == 1
        assert counts["medications"] == 3
        assert counts["diagnoses"] == 1
        assert counts["procedures"] == 0
        assert counts["total"] == 7


class TestClinicalTextSources:
    """Tests for different clinical text sources."""

    def test_get_clinical_text_from_input(self, extraction_agent):
        """Test getting text from clinical_text field."""
        task = AgentTask(
            task_description="Extract",
            input_data={"clinical_text": "Patient text here"}
        )

        text = extraction_agent._get_clinical_text(task)

        assert text == "Patient text here"

    def test_get_clinical_text_from_soap(self, extraction_agent):
        """Test getting text from soap_note field."""
        task = AgentTask(
            task_description="Extract",
            input_data={"soap_note": "SOAP note text"}
        )

        text = extraction_agent._get_clinical_text(task)

        assert text == "SOAP note text"

    def test_get_clinical_text_from_transcript(self, extraction_agent):
        """Test getting text from transcript field."""
        task = AgentTask(
            task_description="Extract",
            input_data={"transcript": "Transcript text"}
        )

        text = extraction_agent._get_clinical_text(task)

        assert text == "Transcript text"

    def test_get_clinical_text_priority(self, extraction_agent):
        """Test that clinical_text has priority."""
        task = AgentTask(
            task_description="Extract",
            input_data={
                "clinical_text": "Primary text",
                "soap_note": "Secondary text",
                "transcript": "Tertiary text"
            }
        )

        text = extraction_agent._get_clinical_text(task)

        assert text == "Primary text"


class TestConvenienceMethods:
    """Tests for convenience methods."""

    def test_extract_all_from_text(self, extraction_agent, mock_ai_caller, sample_clinical_text):
        """Test the extract_all_from_text convenience method."""
        mock_ai_caller.default_response = json.dumps({
            "vital_signs": [{"name": "BP", "value": "120/80"}],
            "laboratory_values": [],
            "medications": [],
            "diagnoses": [],
            "procedures": []
        })

        result = extraction_agent.extract_all_from_text(sample_clinical_text)

        assert result is not None
        assert "vital_signs" in result

    def test_extract_all_from_text_failure(self, extraction_agent, mock_ai_caller):
        """Test convenience method when extraction fails."""
        mock_ai_caller.call = Mock(side_effect=Exception("API error"))

        result = extraction_agent.extract_all_from_text("Test text")

        assert result is None


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_exists(self):
        """Test that default config is properly defined."""
        assert DataExtractionAgent.DEFAULT_CONFIG is not None
        assert DataExtractionAgent.DEFAULT_CONFIG.name == "DataExtractionAgent"

    def test_default_config_zero_temperature(self):
        """Test temperature is zero for consistent extraction."""
        assert DataExtractionAgent.DEFAULT_CONFIG.temperature == 0.0

    def test_default_config_model(self):
        """Test default model selection."""
        # Uses faster model for extraction tasks
        assert "gpt" in DataExtractionAgent.DEFAULT_CONFIG.model.lower()

    def test_system_prompt_extraction_guidance(self):
        """Test system prompt includes extraction guidance."""
        prompt = DataExtractionAgent.DEFAULT_CONFIG.system_prompt.lower()
        assert "extract" in prompt
        assert "json" in prompt
