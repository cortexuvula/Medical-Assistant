"""Tests for Medical Named Entity Recognition extractor."""

import unittest

from rag.medical_ner import (
    MedicalNERExtractor,
    MedicalEntity,
    MedicalEntityType,
    get_medical_ner_extractor,
    extract_medical_entities,
)


class TestMedicalEntityType(unittest.TestCase):
    """Tests for MedicalEntityType enum."""

    def test_all_types_exist(self):
        expected = {
            "condition", "medication", "procedure", "anatomy",
            "lab_test", "dosage", "vital_sign", "symptom",
            "frequency", "route"
        }
        actual = {t.value for t in MedicalEntityType}
        self.assertEqual(actual, expected)

    def test_string_enum(self):
        self.assertEqual(MedicalEntityType.MEDICATION.value, "medication")
        self.assertIn("MEDICATION", str(MedicalEntityType.MEDICATION))


class TestMedicalEntity(unittest.TestCase):
    """Tests for MedicalEntity dataclass."""

    def test_to_dict(self):
        entity = MedicalEntity(
            text="aspirin",
            entity_type=MedicalEntityType.MEDICATION,
            normalized_name="aspirin",
            confidence=0.8,
            start_pos=10,
            end_pos=17,
        )
        d = entity.to_dict()
        self.assertEqual(d["text"], "aspirin")
        self.assertEqual(d["entity_type"], "medication")
        self.assertEqual(d["normalized_name"], "aspirin")
        self.assertEqual(d["confidence"], 0.8)
        self.assertEqual(d["start_pos"], 10)
        self.assertEqual(d["end_pos"], 17)

    def test_defaults(self):
        entity = MedicalEntity(text="test", entity_type=MedicalEntityType.CONDITION)
        self.assertIsNone(entity.normalized_name)
        self.assertEqual(entity.confidence, 1.0)
        self.assertEqual(entity.start_pos, 0)
        self.assertEqual(entity.metadata, {})


class TestDosageExtraction(unittest.TestCase):
    """Tests for dosage pattern extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_mg(self):
        entities = self.extractor._extract_dosages("Take 500 mg twice daily")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].entity_type, MedicalEntityType.DOSAGE)
        self.assertEqual(entities[0].metadata["value"], "500")
        self.assertEqual(entities[0].metadata["unit"], "mg")

    def test_mcg(self):
        entities = self.extractor._extract_dosages("Levothyroxine 75 mcg daily")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].metadata["unit"], "mcg")

    def test_ml(self):
        entities = self.extractor._extract_dosages("Administer 10 mL orally")
        self.assertEqual(len(entities), 1)

    def test_decimal_dosage(self):
        entities = self.extractor._extract_dosages("Dosage: 2.5 mg per day")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].metadata["value"], "2.5")

    def test_units(self):
        entities = self.extractor._extract_dosages("Insulin 10 units at bedtime")
        self.assertEqual(len(entities), 1)

    def test_no_dosage(self):
        entities = self.extractor._extract_dosages("Patient feels well today")
        self.assertEqual(len(entities), 0)


class TestVitalSignExtraction(unittest.TestCase):
    """Tests for vital sign pattern extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_blood_pressure(self):
        entities = self.extractor._extract_vitals("BP 120/80 mmHg")
        bp = [e for e in entities if e.metadata.get("type") == "blood_pressure"]
        self.assertEqual(len(bp), 1)
        self.assertEqual(bp[0].metadata["systolic"], "120")
        self.assertEqual(bp[0].metadata["diastolic"], "80")

    def test_heart_rate(self):
        entities = self.extractor._extract_vitals("HR 72 bpm")
        hr = [e for e in entities if e.metadata.get("type") == "heart_rate"]
        self.assertEqual(len(hr), 1)
        self.assertEqual(hr[0].metadata["value"], "72")

    def test_heart_rate_alternate(self):
        entities = self.extractor._extract_vitals("pulse 90")
        hr = [e for e in entities if e.metadata.get("type") == "heart_rate"]
        self.assertEqual(len(hr), 1)

    def test_spo2(self):
        entities = self.extractor._extract_vitals("SpO2 98%")
        spo2 = [e for e in entities if e.metadata.get("type") == "spo2"]
        self.assertEqual(len(spo2), 1)
        self.assertEqual(spo2[0].metadata["value"], "98")

    def test_respiratory_rate(self):
        entities = self.extractor._extract_vitals("RR 16")
        rr = [e for e in entities if e.metadata.get("type") == "respiratory_rate"]
        self.assertEqual(len(rr), 1)

    def test_weight(self):
        entities = self.extractor._extract_vitals("Weight: 180 lbs")
        wt = [e for e in entities if e.metadata.get("type") == "weight"]
        self.assertEqual(len(wt), 1)

    def test_no_vitals(self):
        entities = self.extractor._extract_vitals("Patient denies chest pain")
        self.assertEqual(len(entities), 0)


class TestMedicationExtraction(unittest.TestCase):
    """Tests for medication dictionary extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_generic_name(self):
        entities = self.extractor._extract_medications("Patient takes metformin daily")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].entity_type, MedicalEntityType.MEDICATION)
        self.assertEqual(entities[0].normalized_name, "metformin")

    def test_brand_name(self):
        entities = self.extractor._extract_medications("Started on Zoloft 50mg")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].normalized_name, "sertraline")

    def test_multiple_meds(self):
        entities = self.extractor._extract_medications(
            "Taking metformin, lisinopril, and aspirin"
        )
        self.assertGreaterEqual(len(entities), 3)

    def test_case_insensitive(self):
        entities = self.extractor._extract_medications("METFORMIN 500mg BID")
        self.assertEqual(len(entities), 1)

    def test_abbreviation(self):
        entities = self.extractor._extract_medications("Prescribed ASA 81mg daily")
        meds = [e for e in entities if e.normalized_name == "aspirin"]
        self.assertEqual(len(meds), 1)

    def test_no_medication(self):
        entities = self.extractor._extract_medications("Patient has a headache")
        self.assertEqual(len(entities), 0)

    def test_word_boundary(self):
        """Medication name should not match inside other words."""
        entities = self.extractor._extract_medications("The forecast is good")
        # "cast" should not match any medication
        self.assertEqual(len(entities), 0)


class TestConditionExtraction(unittest.TestCase):
    """Tests for condition dictionary extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_common_condition(self):
        entities = self.extractor._extract_conditions("History of hypertension")
        self.assertTrue(len(entities) >= 1)
        self.assertEqual(entities[0].entity_type, MedicalEntityType.CONDITION)

    def test_abbreviation(self):
        entities = self.extractor._extract_conditions("Patient has COPD")
        copd = [e for e in entities if "copd" in (e.normalized_name or "").lower()
                or "chronic obstructive" in (e.normalized_name or "").lower()]
        self.assertTrue(len(copd) >= 1)

    def test_multiple_conditions(self):
        entities = self.extractor._extract_conditions(
            "History of diabetes and hypertension"
        )
        self.assertGreaterEqual(len(entities), 2)


class TestLabTestExtraction(unittest.TestCase):
    """Tests for lab test pattern extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_cbc(self):
        entities = self.extractor._extract_lab_tests("Order CBC and BMP")
        self.assertGreaterEqual(len(entities), 2)
        types = {e.normalized_name for e in entities}
        self.assertIn("complete blood count", types)
        self.assertIn("basic metabolic panel", types)

    def test_hba1c(self):
        entities = self.extractor._extract_lab_tests("HbA1c is 7.2%")
        self.assertTrue(any(e.normalized_name == "HbA1c" for e in entities))

    def test_full_name(self):
        entities = self.extractor._extract_lab_tests("Order thyroid stimulating hormone")
        self.assertTrue(any(e.normalized_name == "TSH" for e in entities))


class TestProcedureExtraction(unittest.TestCase):
    """Tests for procedure pattern extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_mri(self):
        entities = self.extractor._extract_procedures("Order MRI of the knee")
        self.assertTrue(any(e.normalized_name == "MRI" for e in entities))

    def test_ct_scan(self):
        entities = self.extractor._extract_procedures("CT scan of the chest")
        self.assertTrue(any(e.normalized_name == "CT scan" for e in entities))

    def test_xray(self):
        entities = self.extractor._extract_procedures("Chest X-ray ordered")
        self.assertTrue(any(e.normalized_name == "X-ray" for e in entities))


class TestFrequencyExtraction(unittest.TestCase):
    """Tests for frequency pattern extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_bid(self):
        entities = self.extractor._extract_frequencies("Take BID")
        self.assertTrue(any(e.normalized_name == "twice daily" for e in entities))

    def test_prn(self):
        entities = self.extractor._extract_frequencies("Use as needed")
        self.assertTrue(any(e.normalized_name == "as needed" for e in entities))

    def test_once_daily(self):
        entities = self.extractor._extract_frequencies("Take once daily")
        self.assertTrue(any(e.normalized_name == "once daily" for e in entities))


class TestRouteExtraction(unittest.TestCase):
    """Tests for route pattern extraction."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_oral(self):
        entities = self.extractor._extract_routes("Take by mouth")
        self.assertTrue(any(e.normalized_name == "oral" for e in entities))

    def test_po(self):
        entities = self.extractor._extract_routes("Administer PO")
        self.assertTrue(any(e.normalized_name == "oral" for e in entities))

    def test_iv(self):
        entities = self.extractor._extract_routes("Give IV")
        self.assertTrue(any(e.normalized_name == "intravenous" for e in entities))

    def test_subcutaneous(self):
        entities = self.extractor._extract_routes("Inject subcutaneously")
        self.assertTrue(any(e.normalized_name == "subcutaneous" for e in entities))


class TestFullExtraction(unittest.TestCase):
    """Tests for the complete extract() pipeline."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_mixed_entities(self):
        text = (
            "Patient with hypertension takes lisinopril 20 mg PO daily. "
            "BP 140/90 mmHg. Order CBC."
        )
        entities = self.extractor.extract(text)
        types = {e.entity_type for e in entities}
        self.assertIn(MedicalEntityType.CONDITION, types)
        self.assertIn(MedicalEntityType.MEDICATION, types)
        self.assertIn(MedicalEntityType.DOSAGE, types)
        self.assertIn(MedicalEntityType.VITAL_SIGN, types)
        self.assertIn(MedicalEntityType.LAB_TEST, types)

    def test_empty_text(self):
        entities = self.extractor.extract("")
        self.assertEqual(len(entities), 0)

    def test_no_medical_content(self):
        entities = self.extractor.extract("The weather is nice today.")
        self.assertEqual(len(entities), 0)

    def test_positions_correct(self):
        text = "Patient takes metformin daily"
        entities = self.extractor._extract_medications(text)
        self.assertEqual(len(entities), 1)
        entity = entities[0]
        self.assertEqual(text[entity.start_pos:entity.end_pos].lower(), "metformin")

    def test_extract_to_dict(self):
        text = "Take aspirin 81 mg PO daily. Order CBC."
        result = self.extractor.extract_to_dict(text)
        self.assertIsInstance(result, dict)
        # Should have at least medication and dosage
        self.assertTrue(len(result) > 0)
        for key, entities in result.items():
            self.assertIsInstance(entities, list)
            for e in entities:
                self.assertIn("text", e)
                self.assertIn("entity_type", e)


class TestDeduplication(unittest.TestCase):
    """Tests for entity deduplication."""

    def setUp(self):
        self.extractor = MedicalNERExtractor()

    def test_no_duplicates(self):
        entities = [
            MedicalEntity("aspirin", MedicalEntityType.MEDICATION, start_pos=0, end_pos=7),
            MedicalEntity("metformin", MedicalEntityType.MEDICATION, start_pos=12, end_pos=21),
        ]
        result = self.extractor._deduplicate(entities)
        self.assertEqual(len(result), 2)

    def test_overlapping_removed(self):
        entities = [
            MedicalEntity("aspirin 81", MedicalEntityType.MEDICATION, start_pos=0, end_pos=10, confidence=0.9),
            MedicalEntity("81 mg", MedicalEntityType.DOSAGE, start_pos=8, end_pos=13, confidence=0.95),
        ]
        result = self.extractor._deduplicate(entities)
        # The longer entity at start_pos=0 should win (sorted first by position)
        self.assertEqual(len(result), 1)

    def test_empty_list(self):
        result = self.extractor._deduplicate([])
        self.assertEqual(len(result), 0)

    def test_single_entity(self):
        entities = [
            MedicalEntity("aspirin", MedicalEntityType.MEDICATION, start_pos=0, end_pos=7),
        ]
        result = self.extractor._deduplicate(entities)
        self.assertEqual(len(result), 1)


class TestSingleton(unittest.TestCase):
    """Tests for singleton accessor and convenience functions."""

    def test_get_medical_ner_extractor_returns_instance(self):
        extractor = get_medical_ner_extractor()
        self.assertIsInstance(extractor, MedicalNERExtractor)

    def test_singleton(self):
        e1 = get_medical_ner_extractor()
        e2 = get_medical_ner_extractor()
        self.assertIs(e1, e2)

    def test_extract_medical_entities_convenience(self):
        entities = extract_medical_entities("Patient takes aspirin daily")
        self.assertIsInstance(entities, list)
        self.assertTrue(any(
            e.entity_type == MedicalEntityType.MEDICATION for e in entities
        ))


if __name__ == '__main__':
    unittest.main()
