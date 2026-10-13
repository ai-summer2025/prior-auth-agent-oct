#!/usr/bin/env python3
"""
Prior Auth Agent -- Command Line Interface

Usage:
    python main.py --demo                    Run built-in demo cases
    python main.py --case lumbar-mri         Run the lumbar MRI demo case
    python main.py --case biologics          Run the biologics demo case
    python main.py --case cardiac            Run the cardiac cath demo case
    python main.py --no-pubmed               Disable live PubMed search
    python main.py --output-appeal FILE      Save appeal letter to file
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.agent import run_agent, print_results


DEMO_CASES = {
    "lumbar-mri": {
        "name": "Lumbar MRI for Low Back Pain with Radiculopathy",
        "patient_age": 52,
        "patient_sex": "male",
        "primary_diagnosis": "lumbar radiculopathy with herniated disc",
        "requested_procedure": "MRI lumbar spine without contrast",
        "clinical_indication": "low back pain with left leg radiculopathy not responding to treatment",
        "symptom_duration_weeks": 8,
        "prior_treatments": ["NSAIDs (ibuprofen 800mg TID x 6 weeks)", "Physical therapy (12 sessions)"],
        "secondary_diagnoses": ["Type 2 diabetes", "Hypertension"],
        "current_medications": ["Metformin 1000mg BID", "Lisinopril 10mg daily", "Ibuprofen 800mg PRN"],
        "specialist_involved": False,
        "urgency": "routine",
        "supporting_notes": (
            "Patient presents with 8 weeks of worsening low back pain radiating to left leg in L4-L5 distribution. "
            "Physical exam demonstrates reduced DTR at left knee, 4/5 hip flexor strength on the left. "
            "Straight leg raise positive at 45 degrees on the left. "
            "Patient unable to work as a delivery driver due to pain severity. "
            "Failed 6 weeks of PT and 6-week NSAID trial. "
            "Requesting MRI to evaluate for surgical candidacy."
        ),
    },
    "biologics": {
        "name": "Biologic Therapy (Adalimumab) for Rheumatoid Arthritis",
        "patient_age": 45,
        "patient_sex": "female",
        "primary_diagnosis": "rheumatoid arthritis with rheumatoid factor positive",
        "requested_procedure": "adalimumab (Humira) 40mg every 2 weeks",
        "clinical_indication": "moderate-to-severe rheumatoid arthritis with inadequate DMARD response",
        "symptom_duration_weeks": 156,
        "prior_treatments": [
            "Methotrexate 20mg weekly x 6 months (inadequate response)",
            "Hydroxychloroquine 400mg daily x 4 months (intolerance -- GI side effects)",
            "Leflunomide 20mg daily x 3 months (elevated LFTs, discontinued)",
        ],
        "secondary_diagnoses": ["Interstitial lung disease (mild)", "Sjogren's syndrome"],
        "current_medications": ["Prednisone 7.5mg daily", "Folic acid 1mg daily", "Calcium with Vitamin D"],
        "specialist_involved": True,
        "urgency": "routine",
        "bmi": 24.5,
        "supporting_notes": (
            "This patient has been followed by rheumatology for 3 years with progressive RA. "
            "Current DAS28-CRP score: 5.6 (high disease activity). "
            "Joint count: 8 swollen, 12 tender joints. "
            "CRP 42 mg/L (elevated). ESR 88 mm/hr. RF positive 1:320. Anti-CCP 180 U/mL. "
            "Chest CT without significant change from baseline (stable mild ILD). "
            "TB screening: negative QuantiFERON-TB Gold. Hepatitis B/C: negative. "
            "Rheumatologist strongly recommends biologic initiation given persistent high disease activity "
            "and functional limitation (HAQ-DI 2.1, moderate-severe disability)."
        ),
    },
    "cardiac": {
        "name": "Cardiac Catheterization for Stable Chest Pain",
        "patient_age": 67,
        "patient_sex": "male",
        "primary_diagnosis": "stable angina with positive stress test",
        "requested_procedure": "cardiac catheterization coronary angiogram",
        "clinical_indication": "chest pain with positive nuclear stress test showing anterior wall ischemia",
        "symptom_duration_weeks": 12,
        "prior_treatments": [
            "Aspirin 81mg daily",
            "Metoprolol succinate 50mg daily",
            "Isosorbide mononitrate 30mg daily",
        ],
        "secondary_diagnoses": ["Hypertension", "Hyperlipidemia", "Type 2 diabetes", "Prior MI (2019)"],
        "current_medications": [
            "Aspirin 81mg", "Metoprolol 50mg", "Atorvastatin 80mg",
            "Isosorbide mononitrate 30mg", "Metformin 1000mg BID", "Lisinopril 20mg"
        ],
        "specialist_involved": True,
        "urgency": "urgent",
        "bmi": 29.2,
        "supporting_notes": (
            "Patient with prior MI presents with 3-month history of exertional chest pain (CCS Class II). "
            "Nuclear stress test (Bruce protocol) showed moderate anterior wall perfusion defect with "
            "reversibility, consistent with inducible ischemia in LAD territory. "
            "LVEF 45% by echo (reduced from 55% two years ago). "
            "Cardiology requesting coronary angiography to evaluate anatomy for potential revascularization. "
            "Patient on maximal medical therapy. Functional limitation limits ability to work."
        ),
    },
    "bariatric": {
        "name": "Bariatric Surgery for Morbid Obesity",
        "patient_age": 41,
        "patient_sex": "female",
        "primary_diagnosis": "morbid obesity with comorbidities",
        "requested_procedure": "laparoscopic sleeve gastrectomy bariatric surgery",
        "clinical_indication": "morbid obesity BMI 43 with type 2 diabetes and sleep apnea",
        "symptom_duration_weeks": 260,
        "prior_treatments": [
            "6-month supervised medical weight loss program (lost 8 lbs, regained)",
            "Phentermine-topiramate 7.5/46mg x 6 months (5% weight loss, insufficient)",
            "Semaglutide 2.4mg weekly x 4 months (GI intolerance, discontinued)",
        ],
        "secondary_diagnoses": ["Type 2 diabetes (A1c 9.2%)", "Obstructive sleep apnea on CPAP", "Hypertension", "NAFLD"],
        "current_medications": [
            "Metformin 2000mg daily", "Glipizide 10mg BID", "Lisinopril 20mg",
            "CPAP therapy nightly", "Omeprazole 20mg daily"
        ],
        "specialist_involved": True,
        "urgency": "routine",
        "bmi": 43.0,
        "supporting_notes": (
            "Patient with 5+ year history of morbid obesity and multiple failed weight loss attempts. "
            "Height 5'4\", Weight 251 lbs, BMI 43.1. "
            "Completed 6-month medically supervised weight loss program with Weight Watchers and primary care. "
            "Psychology clearance completed 2 months ago -- no psychiatric contraindications. "
            "Nutritional counseling completed x 6 sessions. "
            "Bariatric surgery center of excellence evaluation completed. "
            "Surgeon recommends sleeve gastrectomy. Patient understands risks and post-op dietary requirements."
        ),
    },
}


def main():
    parser = argparse.ArgumentParser(
        description="Prior Auth Agent -- Autonomous Prior Authorization System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --demo                  # Run all demo cases
  python main.py --case lumbar-mri       # Run the lumbar MRI case
  python main.py --case biologics        # Run the biologics (adalimumab) case
  python main.py --case cardiac          # Run the cardiac cath case
  python main.py --case bariatric        # Run the bariatric surgery case
  python main.py --no-pubmed --case lumbar-mri   # Skip PubMed (offline mode)
        """,
    )
    parser.add_argument("--demo", action="store_true", help="Run the first demo case (lumbar MRI)")
    parser.add_argument("--all-demos", action="store_true", help="Run all demo cases")
    parser.add_argument("--case", choices=list(DEMO_CASES.keys()), help="Run a specific demo case")
    parser.add_argument("--no-pubmed", action="store_true", help="Disable live PubMed search")
    parser.add_argument("--output-appeal", type=str, metavar="FILE", help="Save the appeal letter to a file")
    parser.add_argument("--output-auth", type=str, metavar="FILE", help="Save the full auth request to a file")
    parser.add_argument("--quiet", action="store_true", help="Suppress agent step-by-step logs")

    args = parser.parse_args()

    if not (args.demo or args.case or args.all_demos):
        parser.print_help()
        print("\nQuick start: python main.py --demo")
        sys.exit(0)

    use_pubmed = not args.no_pubmed
    verbose = not args.quiet

    cases_to_run = []
    if args.all_demos:
        cases_to_run = list(DEMO_CASES.keys())
    elif args.case:
        cases_to_run = [args.case]
    elif args.demo:
        cases_to_run = ["lumbar-mri"]

    results = []
    for case_key in cases_to_run:
        case_data = DEMO_CASES[case_key]
        print(f"\n{'='*70}")
        print(f"  Running: {case_data['name']}")
        print(f"{'='*70}")

        result = run_agent(
            patient_age=case_data["patient_age"],
            patient_sex=case_data["patient_sex"],
            primary_diagnosis=case_data["primary_diagnosis"],
            requested_procedure=case_data["requested_procedure"],
            clinical_indication=case_data["clinical_indication"],
            symptom_duration_weeks=case_data["symptom_duration_weeks"],
            prior_treatments=case_data.get("prior_treatments", []),
            secondary_diagnoses=case_data.get("secondary_diagnoses", []),
            current_medications=case_data.get("current_medications", []),
            specialist_involved=case_data.get("specialist_involved", False),
            urgency=case_data.get("urgency", "routine"),
            supporting_notes=case_data.get("supporting_notes", ""),
            bmi=case_data.get("bmi"),
            use_pubmed=use_pubmed,
            verbose=verbose,
        )
        print_results(result)
        results.append(result)

        if args.output_appeal and result.appeal_strategy:
            output_path = args.output_appeal if len(cases_to_run) == 1 else f"{case_key}_{args.output_appeal}"
            with open(output_path, "w") as f:
                f.write(result.appeal_strategy.appeal_letter_draft)
            print(f"Appeal letter saved to: {output_path}")

        if args.output_auth:
            output_path = args.output_auth if len(cases_to_run) == 1 else f"{case_key}_{args.output_auth}"
            with open(output_path, "w") as f:
                f.write(result.auth_request.medical_necessity_statement)
            print(f"Auth request saved to: {output_path}")

    if len(results) > 1:
        print("\n" + "=" * 70)
        print("  BATCH SUMMARY")
        print("=" * 70)
        for case_key, result in zip(cases_to_run, results):
            prob = result.assessment.adjusted_probability
            status = "OK" if prob >= 0.70 else "WARN" if prob >= 0.45 else "RISK"
            print(f"  [{status}] {case_key:<20} Prob: {prob:.1%}  |  {result.auth_request.likelihood_label.value}")
        print("=" * 70)


if __name__ == "__main__":
    main()
