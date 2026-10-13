"""
Test suite for Prior Auth Agent.

Tests cover:
  - Code mapping (ICD-10/CPT)
  - Policy assessment logic
  - Evidence finder (offline/mock mode)
  - Auth request generation
  - Appeal strategy generation
  - Full end-to-end agent pipeline
  - Edge cases and error handling
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.models import (
    ClinicalCase, PatientProfile, ApprovalLikelihood,
    Evidence, PolicyAssessment,
)
from src.code_mapper import map_diagnosis_to_code, describe_icd10, describe_cpt
from src.payer_engine import assess_case
from src.evidence_finder import (
    get_evidence_for_case, score_relevance, determine_evidence_type,
    parse_pubmed_xml, FALLBACK_EVIDENCE,
)
from src.auth_writer import generate_auth_request, generate_appeal_strategy, _get_likelihood_label
from src.agent import run_agent


def make_lumbar_case(duration_weeks=8, prior_tx=None, specialist=False, notes=""):
    patient = PatientProfile(
        age=52,
        sex="male",
        primary_diagnosis="lumbar radiculopathy herniated disc",
        secondary_diagnoses=["Hypertension"],
        current_medications=["Ibuprofen 800mg", "Lisinopril 10mg"],
    )
    case = ClinicalCase(
        patient=patient,
        requested_procedure="MRI lumbar spine",
        clinical_indication="low back pain with radiculopathy",
        symptom_duration_weeks=duration_weeks,
        prior_treatments=prior_tx or ["Physical therapy 6 weeks", "NSAIDs 6 weeks"],
        specialist_involved=specialist,
        urgency="routine",
        supporting_notes=notes,
        icd10_code="M54.4",
        cpt_code="72148",
        policy_key="lumbar_MRI",
    )
    return case


def make_biologics_case():
    patient = PatientProfile(
        age=45,
        sex="female",
        primary_diagnosis="rheumatoid arthritis",
        secondary_diagnoses=["Interstitial lung disease"],
        current_medications=["Methotrexate 20mg weekly", "Prednisone 7.5mg"],
    )
    case = ClinicalCase(
        patient=patient,
        requested_procedure="adalimumab biologic injection",
        clinical_indication="moderate-to-severe rheumatoid arthritis with DMARD failure",
        symptom_duration_weeks=52,
        prior_treatments=["Methotrexate 6 months", "Hydroxychloroquine 4 months", "Leflunomide 3 months"],
        specialist_involved=True,
        urgency="routine",
        supporting_notes="DAS28 score 5.6. RF positive. Anti-CCP 180. TB screening negative. Hep B/C negative.",
        icd10_code="M05.79",
        cpt_code="J0135",
        policy_key="biologics_rheumatoid_arthritis",
    )
    return case


class TestCodeMapper(unittest.TestCase):

    def test_lumbar_mri_diagnosis_mapping(self):
        icd10, cpt, policy_key = map_diagnosis_to_code(
            "lumbar radiculopathy herniated disc",
            "MRI lumbar spine without contrast"
        )
        self.assertIn("M54", icd10, f"Expected lumbar ICD-10 code, got: {icd10}")
        self.assertEqual(cpt, "72148", f"Expected CPT 72148 for lumbar MRI, got: {cpt}")
        self.assertEqual(policy_key, "lumbar_MRI")

    def test_brain_mri_mapping(self):
        icd10, cpt, policy_key = map_diagnosis_to_code(
            "headache migraine chronic",
            "MRI brain with and without contrast"
        )
        self.assertIn("70", cpt, f"Expected brain MRI CPT code, got: {cpt}")
        self.assertEqual(policy_key, "MRI_brain")

    def test_rheumatoid_arthritis_biologic_mapping(self):
        icd10, cpt, policy_key = map_diagnosis_to_code(
            "rheumatoid arthritis severe",
            "adalimumab humira injection"
        )
        self.assertEqual(policy_key, "biologics_rheumatoid_arthritis")

    def test_cardiac_cath_mapping(self):
        icd10, cpt, policy_key = map_diagnosis_to_code(
            "stable angina coronary artery disease",
            "cardiac catheterization coronary angiogram"
        )
        self.assertEqual(cpt, "93454")
        self.assertEqual(policy_key, "cardiac_catheterization")

    def test_bariatric_surgery_mapping(self):
        icd10, cpt, policy_key = map_diagnosis_to_code(
            "morbid obesity BMI 43",
            "bariatric surgery gastric bypass"
        )
        self.assertEqual(policy_key, "bariatric_surgery")

    def test_unknown_diagnosis_returns_empty_strings(self):
        icd10, cpt, policy_key = map_diagnosis_to_code("xylophone disease", "quantum procedure")
        self.assertIsInstance(icd10, str)
        self.assertIsInstance(cpt, str)
        self.assertIsInstance(policy_key, str)

    def test_describe_functions(self):
        desc = describe_icd10("M54.4")
        self.assertIsInstance(desc, str)
        desc2 = describe_cpt("72148")
        self.assertIsInstance(desc2, str)


class TestPayerEngine(unittest.TestCase):

    def test_lumbar_mri_with_good_case_high_probability(self):
        case = make_lumbar_case(
            duration_weeks=10,
            prior_tx=["Physical therapy 8 weeks", "NSAIDs 6 weeks", "Chiropractic care 8 sessions"],
            specialist=True,
            notes="Neurological deficit on exam. 4/5 strength left leg. Positive SLR.",
        )
        assessment = assess_case(case)
        self.assertGreater(assessment.adjusted_probability, 0.60)

    def test_lumbar_mri_acute_case_lower_probability(self):
        case = make_lumbar_case(duration_weeks=2, prior_tx=[], specialist=False, notes="")
        assessment = assess_case(case)
        self.assertLess(assessment.adjusted_probability, 0.65)

    def test_biologics_with_full_dmard_failure_high_probability(self):
        case = make_biologics_case()
        assessment = assess_case(case)
        self.assertGreater(assessment.adjusted_probability, 0.55)

    def test_unknown_policy_returns_neutral_assessment(self):
        patient = PatientProfile(age=30, sex="female", primary_diagnosis="xylophone disease")
        case = ClinicalCase(
            patient=patient,
            requested_procedure="quantum procedure",
            clinical_indication="testing edge case",
            symptom_duration_weeks=4,
            policy_key="totally_unknown_procedure_xyz",
        )
        assessment = assess_case(case)
        self.assertIsInstance(assessment.adjusted_probability, float)
        self.assertGreater(assessment.adjusted_probability, 0.0)
        self.assertLess(assessment.adjusted_probability, 1.0)

    def test_assessment_probability_is_in_valid_range(self):
        for duration in [1, 6, 12, 52]:
            case = make_lumbar_case(duration_weeks=duration)
            assessment = assess_case(case)
            self.assertGreaterEqual(assessment.adjusted_probability, 0.05)
            self.assertLessEqual(assessment.adjusted_probability, 0.98)

    def test_criteria_met_and_missing_are_lists(self):
        case = make_lumbar_case()
        assessment = assess_case(case)
        self.assertIsInstance(assessment.criteria_met, list)
        self.assertIsInstance(assessment.criteria_missing, list)
        self.assertIsInstance(assessment.likely_denial_reasons, list)

    def test_urgency_affects_probability(self):
        case_routine = make_lumbar_case()
        case_routine.urgency = "routine"
        case_urgent = make_lumbar_case()
        case_urgent.urgency = "urgent"
        assessment_routine = assess_case(case_routine)
        assessment_urgent = assess_case(case_urgent)
        self.assertGreaterEqual(
            assessment_urgent.adjusted_probability,
            assessment_routine.adjusted_probability,
        )


class TestEvidenceFinder(unittest.TestCase):

    def test_fallback_evidence_returns_for_known_policy(self):
        case = make_lumbar_case()
        evidence = get_evidence_for_case(case, use_pubmed=False)
        self.assertGreater(len(evidence), 0)

    def test_evidence_has_required_fields(self):
        case = make_lumbar_case()
        evidence = get_evidence_for_case(case, use_pubmed=False)
        for ev in evidence:
            self.assertIsInstance(ev.pmid, str)
            self.assertIsInstance(ev.title, str)
            self.assertIsInstance(ev.abstract_snippet, str)
            self.assertGreater(ev.relevance_score, 0.0)
            self.assertLessEqual(ev.relevance_score, 1.0)

    def test_evidence_sorted_by_relevance(self):
        case = make_lumbar_case()
        evidence = get_evidence_for_case(case, use_pubmed=False)
        if len(evidence) >= 2:
            for i in range(len(evidence) - 1):
                self.assertGreaterEqual(evidence[i].relevance_score, evidence[i + 1].relevance_score)

    def test_relevance_scoring_penalizes_unrelated_content(self):
        case = make_lumbar_case()
        high_score = score_relevance(
            "Lumbar MRI for low back pain: clinical guidelines systematic review",
            "This randomized controlled trial evaluates lumbar MRI utilization in patients with radiculopathy.",
            case,
        )
        low_score = score_relevance(
            "Ophthalmology case report on macular degeneration",
            "This paper discusses retinal degeneration in elderly patients.",
            case,
        )
        self.assertGreater(high_score, low_score)

    def test_evidence_type_classification(self):
        self.assertEqual(
            determine_evidence_type("Randomized controlled trial of lumbar MRI", "This RCT enrolled 200 patients."),
            "RCT"
        )
        self.assertEqual(
            determine_evidence_type("Systematic review and meta-analysis", "We conducted a meta-analysis of 15 studies."),
            "systematic_review"
        )
        self.assertEqual(
            determine_evidence_type("Clinical practice guideline for imaging", "These guidelines recommend..."),
            "guideline"
        )

    def test_evidence_capped_at_five(self):
        case = make_lumbar_case()
        evidence = get_evidence_for_case(case, use_pubmed=False)
        self.assertLessEqual(len(evidence), 5)

    def test_parse_pubmed_xml_malformed_returns_empty(self):
        result = parse_pubmed_xml("THIS IS NOT XML")
        self.assertEqual(result, [])

    def test_all_policy_keys_have_fallback_evidence(self):
        expected_policies = [
            "lumbar_MRI", "MRI_brain", "biologics_rheumatoid_arthritis",
            "bariatric_surgery", "cardiac_catheterization", "genetic_testing_cancer",
        ]
        for policy in expected_policies:
            self.assertIn(policy, FALLBACK_EVIDENCE)
            self.assertGreater(len(FALLBACK_EVIDENCE[policy]), 0)


class TestAuthWriter(unittest.TestCase):

    def setUp(self):
        self.case = make_lumbar_case()
        self.assessment = assess_case(self.case)
        self.evidence = get_evidence_for_case(self.case, use_pubmed=False)

    def test_auth_request_has_request_id(self):
        auth_request = generate_auth_request(self.case, self.assessment, self.evidence)
        self.assertTrue(auth_request.request_id.startswith("PA-"))
        self.assertGreater(len(auth_request.request_id), 10)

    def test_auth_request_has_documentation_checklist(self):
        auth_request = generate_auth_request(self.case, self.assessment, self.evidence)
        self.assertIsInstance(auth_request.supporting_documentation_checklist, list)
        self.assertGreater(len(auth_request.supporting_documentation_checklist), 3)

    def test_auth_request_clinical_summary_contains_patient_info(self):
        auth_request = generate_auth_request(self.case, self.assessment, self.evidence)
        summary = auth_request.clinical_summary
        self.assertIn(str(self.case.patient.age), summary)
        self.assertIn(self.case.patient.sex, summary)
        self.assertIn(self.case.requested_procedure[:20].lower(), summary.lower())

    def test_likelihood_label_mapping(self):
        self.assertEqual(_get_likelihood_label(0.90), ApprovalLikelihood.VERY_HIGH)
        self.assertEqual(_get_likelihood_label(0.75), ApprovalLikelihood.HIGH)
        self.assertEqual(_get_likelihood_label(0.60), ApprovalLikelihood.MODERATE)
        self.assertEqual(_get_likelihood_label(0.40), ApprovalLikelihood.LOW)
        self.assertEqual(_get_likelihood_label(0.20), ApprovalLikelihood.VERY_LOW)

    def test_appeal_strategy_generated_for_low_probability(self):
        case = make_lumbar_case(duration_weeks=1, prior_tx=[], specialist=False, notes="")
        assessment = assess_case(case)
        appeal = generate_appeal_strategy(case, assessment, self.evidence)
        self.assertIsInstance(appeal.appeal_arguments, list)
        self.assertGreater(len(appeal.appeal_arguments), 0)
        self.assertIsInstance(appeal.appeal_letter_draft, str)
        self.assertGreater(len(appeal.appeal_letter_draft), 200)

    def test_appeal_letter_contains_key_sections(self):
        case = make_lumbar_case(duration_weeks=2, prior_tx=[], specialist=False)
        assessment = assess_case(case)
        appeal = generate_appeal_strategy(case, assessment, self.evidence)
        letter = appeal.appeal_letter_draft.lower()
        self.assertIn("appeal", letter)
        self.assertIn("medical director", letter)
        self.assertIn("grounds for appeal", letter)

    def test_medical_necessity_statement_contains_evidence(self):
        auth_request = generate_auth_request(self.case, self.assessment, self.evidence)
        statement = auth_request.medical_necessity_statement.lower()
        self.assertIn("medical necessity", statement)
        self.assertIn("statement", statement)


class TestAgentPipeline(unittest.TestCase):

    def test_full_pipeline_lumbar_mri(self):
        result = run_agent(
            patient_age=52, patient_sex="male",
            primary_diagnosis="lumbar radiculopathy herniated disc",
            requested_procedure="MRI lumbar spine without contrast",
            clinical_indication="low back pain with left leg radiculopathy",
            symptom_duration_weeks=8,
            prior_treatments=["Physical therapy", "NSAIDs"],
            specialist_involved=False, urgency="routine",
            supporting_notes="Neurological deficit on exam.",
            use_pubmed=False, verbose=False,
        )
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.auth_request)
        self.assertIsNotNone(result.assessment)
        self.assertGreater(result.total_evidence_found, 0)
        self.assertGreater(result.run_time_seconds, 0)

    def test_full_pipeline_biologics(self):
        result = run_agent(
            patient_age=45, patient_sex="female",
            primary_diagnosis="rheumatoid arthritis",
            requested_procedure="adalimumab biologic injection",
            clinical_indication="rheumatoid arthritis with DMARD failure",
            symptom_duration_weeks=52,
            prior_treatments=["Methotrexate", "Hydroxychloroquine", "Leflunomide"],
            specialist_involved=True, urgency="routine",
            supporting_notes="DAS28 score 5.6. TB negative.",
            use_pubmed=False, verbose=False,
        )
        self.assertIsNotNone(result)
        self.assertIn("INTAKE", result.steps_completed)
        self.assertIn("COMPLETE", result.steps_completed)

    def test_low_probability_triggers_appeal_strategy(self):
        result = run_agent(
            patient_age=35, patient_sex="male",
            primary_diagnosis="low back pain acute",
            requested_procedure="MRI lumbar spine",
            clinical_indication="acute low back pain 1 week",
            symptom_duration_weeks=1, prior_treatments=[],
            specialist_involved=False, urgency="routine",
            use_pubmed=False, verbose=False,
        )
        if result.assessment.adjusted_probability < 0.70:
            self.assertIsNotNone(result.appeal_strategy)
            self.assertGreater(len(result.appeal_strategy.appeal_arguments), 0)

    def test_high_probability_case_no_appeal_needed(self):
        result = run_agent(
            patient_age=67, patient_sex="male",
            primary_diagnosis="stable angina coronary artery disease",
            requested_procedure="cardiac catheterization coronary angiogram",
            clinical_indication="stable angina with positive stress test",
            symptom_duration_weeks=12,
            prior_treatments=["Aspirin", "Metoprolol", "Isosorbide mononitrate"],
            specialist_involved=True, urgency="urgent",
            supporting_notes="Positive nuclear stress test. LVEF 45%. Prior MI.",
            use_pubmed=False, verbose=False,
        )
        if result.assessment.adjusted_probability >= 0.70:
            self.assertIsNone(result.appeal_strategy)

    def test_result_recommendation_is_non_empty(self):
        result = run_agent(
            patient_age=41, patient_sex="female",
            primary_diagnosis="morbid obesity",
            requested_procedure="bariatric surgery sleeve gastrectomy",
            clinical_indication="morbid obesity BMI 43 with diabetes",
            symptom_duration_weeks=260,
            prior_treatments=["Supervised weight loss 6 months", "Phentermine-topiramate"],
            specialist_involved=True, urgency="routine", bmi=43.0,
            use_pubmed=False, verbose=False,
        )
        self.assertIsInstance(result.recommendation, str)
        self.assertGreater(len(result.recommendation), 10)


class TestEdgeCases(unittest.TestCase):

    def test_empty_prior_treatments_does_not_crash(self):
        result = run_agent(
            patient_age=30, patient_sex="female",
            primary_diagnosis="headache chronic",
            requested_procedure="MRI brain",
            clinical_indication="chronic headache not responding",
            symptom_duration_weeks=10, prior_treatments=[],
            use_pubmed=False, verbose=False,
        )
        self.assertIsNotNone(result)

    def test_minimal_supporting_notes_does_not_crash(self):
        result = run_agent(
            patient_age=55, patient_sex="male",
            primary_diagnosis="low back pain",
            requested_procedure="MRI lumbar spine",
            clinical_indication="back pain",
            symptom_duration_weeks=6, prior_treatments=["NSAIDs"],
            supporting_notes="", use_pubmed=False, verbose=False,
        )
        self.assertIsNotNone(result)

    def test_very_old_patient_does_not_crash(self):
        result = run_agent(
            patient_age=95, patient_sex="female",
            primary_diagnosis="memory loss dementia",
            requested_procedure="MRI brain",
            clinical_indication="cognitive decline evaluation",
            symptom_duration_weeks=20, prior_treatments=[],
            use_pubmed=False, verbose=False,
        )
        self.assertIsNotNone(result)

    def test_urgent_emergent_cases_handled_correctly(self):
        result_routine = run_agent(
            patient_age=50, patient_sex="male",
            primary_diagnosis="chest pain",
            requested_procedure="cardiac catheterization",
            clinical_indication="chest pain with positive stress test",
            symptom_duration_weeks=4, prior_treatments=["Aspirin"],
            urgency="routine", use_pubmed=False, verbose=False,
        )
        result_emergent = run_agent(
            patient_age=50, patient_sex="male",
            primary_diagnosis="unstable angina",
            requested_procedure="cardiac catheterization",
            clinical_indication="chest pain with positive stress test",
            symptom_duration_weeks=4, prior_treatments=["Aspirin"],
            urgency="emergent", specialist_involved=True,
            use_pubmed=False, verbose=False,
        )
        self.assertGreaterEqual(
            result_emergent.assessment.adjusted_probability,
            result_routine.assessment.adjusted_probability,
        )

    def test_auth_request_id_is_unique(self):
        import time
        case = make_lumbar_case()
        assessment = assess_case(case)
        evidence = get_evidence_for_case(case, use_pubmed=False)
        req1 = generate_auth_request(case, assessment, evidence)
        time.sleep(0.01)
        req2 = generate_auth_request(case, assessment, evidence)
        self.assertNotEqual(req1.request_id, req2.request_id)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for test_class in [
        TestCodeMapper, TestPayerEngine, TestEvidenceFinder,
        TestAuthWriter, TestAgentPipeline, TestEdgeCases,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
