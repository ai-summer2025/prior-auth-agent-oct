"""
Generates complete prior authorization request packets and appeal letters.
Produces professional clinical documentation with evidence citations.
"""
import uuid
from datetime import datetime
from typing import List
from .models import (
    ClinicalCase, PolicyAssessment, Evidence, AuthRequest, AppealStrategy,
    ApprovalLikelihood,
)


def generate_auth_request(
    case: ClinicalCase,
    assessment: PolicyAssessment,
    evidence: List[Evidence],
) -> AuthRequest:
    """Generate a complete prior authorization submission packet."""
    request_id = f"PA-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    clinical_summary = _build_clinical_summary(case)
    necessity_statement = _build_medical_necessity_statement(case, assessment, evidence)
    doc_checklist = _build_documentation_checklist(case, assessment)
    likelihood = _get_likelihood_label(assessment.adjusted_probability)

    return AuthRequest(
        request_id=request_id,
        generated_at=datetime.now().isoformat(),
        case=case,
        assessment=assessment,
        evidence=evidence,
        clinical_summary=clinical_summary,
        medical_necessity_statement=necessity_statement,
        supporting_documentation_checklist=doc_checklist,
        expected_approval_probability=assessment.adjusted_probability,
        likelihood_label=likelihood,
    )


def generate_appeal_strategy(
    case: ClinicalCase,
    assessment: PolicyAssessment,
    evidence: List[Evidence],
) -> AppealStrategy:
    """Generate a pre-emptive appeal strategy for cases at risk of denial."""
    appeal_arguments = _build_appeal_arguments(case, assessment, evidence)
    appeal_letter = _draft_appeal_letter(case, assessment, evidence, appeal_arguments)
    escalation = _get_escalation_path(assessment.adjusted_probability)
    estimated_success = min(0.80, assessment.adjusted_probability + 0.20)

    return AppealStrategy(
        denial_reasons_anticipated=assessment.likely_denial_reasons,
        appeal_arguments=appeal_arguments,
        evidence_to_cite=evidence[:3],
        appeal_letter_draft=appeal_letter,
        escalation_path=escalation,
        estimated_appeal_success=estimated_success,
    )


def _build_clinical_summary(case: ClinicalCase) -> str:
    """Build a concise clinical summary paragraph."""
    patient = case.patient
    tx_list = ", ".join(case.prior_treatments) if case.prior_treatments else "none documented"
    comorbidities = ", ".join(patient.secondary_diagnoses) if patient.secondary_diagnoses else "none"
    specialist = "Yes — specialist letter of support available" if case.specialist_involved else "Not yet obtained"

    return (
        f"Patient is a {patient.age}-year-old {patient.sex} presenting with {patient.primary_diagnosis}. "
        f"Symptoms have persisted for {case.symptom_duration_weeks} weeks. "
        f"The requested procedure is {case.requested_procedure} (CPT {case.cpt_code}) for the indication of {case.clinical_indication}. "
        f"Relevant comorbidities: {comorbidities}. "
        f"Prior treatments attempted: {tx_list}. "
        f"Current medications: {', '.join(patient.current_medications) if patient.current_medications else 'none listed'}. "
        f"Specialist involvement: {specialist}. "
        f"Urgency classification: {case.urgency.upper()}."
    )


def _build_medical_necessity_statement(
    case: ClinicalCase,
    assessment: PolicyAssessment,
    evidence: List[Evidence],
) -> str:
    """Generate a professional medical necessity statement."""
    lines = []
    lines.append("STATEMENT OF MEDICAL NECESSITY")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"Patient: {case.patient.age}yo {case.patient.sex} | Primary Dx: {case.patient.primary_diagnosis}")
    lines.append(f"Requested Service: {case.requested_procedure} (CPT: {case.cpt_code})")
    lines.append(f"Diagnosis Code: ICD-10 {case.icd10_code}")
    lines.append("")
    lines.append("CLINICAL RATIONALE:")
    lines.append(f"This patient requires {case.requested_procedure} for the management of {case.patient.primary_diagnosis}. ")

    if case.symptom_duration_weeks > 0:
        lines.append(
            f"The patient has experienced {case.clinical_indication} for {case.symptom_duration_weeks} weeks, "
            f"which has resulted in functional impairment and quality of life compromise."
        )

    if case.prior_treatments:
        lines.append(
            f"\nCONSERVATIVE TREATMENT FAILURE:\n"
            f"The following treatments have been attempted without adequate response: "
            f"{', '.join(case.prior_treatments)}."
        )

    if assessment.criteria_met:
        lines.append("\nMEDICAL NECESSITY CRITERIA MET:")
        for criterion in assessment.criteria_met:
            lines.append(f"  [MET] {criterion}")

    if evidence:
        lines.append("\nSUPPORTING EVIDENCE:")
        for ev in evidence[:3]:
            lines.append(f"  * {ev.citation()}")
            lines.append(f"    [{ev.evidence_type.upper()}] {ev.abstract_snippet[:200]}...")

    if case.supporting_notes:
        lines.append(f"\nCLINICIAN NOTES:\n{case.supporting_notes}")

    lines.append("\n" + "=" * 50)
    lines.append("This request is medically necessary and consistent with evidence-based clinical guidelines.")

    return "\n".join(lines)


def _build_documentation_checklist(
    case: ClinicalCase, assessment: PolicyAssessment
) -> List[str]:
    """Generate a checklist of documentation to include with the submission."""
    checklist = [
        "[ ] Completed prior authorization request form (payer-specific)",
        f"[ ] Clinical notes supporting {case.clinical_indication} (past 90 days)",
        "[ ] Treating physician attestation of medical necessity",
        f"[ ] Documentation of diagnosis: {case.patient.primary_diagnosis} (ICD-10: {case.icd10_code})",
    ]

    if case.prior_treatments:
        checklist.append(f"[ ] Records documenting failure of: {', '.join(case.prior_treatments)}")

    if case.specialist_involved:
        checklist.append("[ ] Specialist consultation letter with treatment recommendation")

    if case.patient.bmi:
        checklist.append(f"[ ] BMI documentation (current BMI: {case.patient.bmi})")

    for missing in assessment.criteria_missing[:3]:
        checklist.append(f"[ ] [CRITICAL] Address missing criterion: {missing[:80]}")

    checklist.extend([
        "[ ] Relevant imaging or diagnostic test results",
        "[ ] Peer-reviewed literature supporting medical necessity (attached)",
        "[ ] Patient's current medication list",
        "[ ] Insurance authorization request number (if resubmission)",
    ])

    return checklist


def _build_appeal_arguments(
    case: ClinicalCase,
    assessment: PolicyAssessment,
    evidence: List[Evidence],
) -> List[str]:
    """Build a set of appeal arguments organized by strength."""
    arguments = []

    rct_evidence = [e for e in evidence if e.evidence_type in ["RCT", "systematic_review"]]
    guideline_evidence = [e for e in evidence if e.evidence_type == "guideline"]

    if guideline_evidence:
        ev = guideline_evidence[0]
        arguments.append(
            f"CLINICAL GUIDELINE SUPPORT: The requested service is consistent with published clinical guidelines. "
            f"{ev.title} ({ev.journal}, {ev.year}) supports this indication. "
            f"Denial would be inconsistent with evidence-based medicine."
        )

    if rct_evidence:
        ev = rct_evidence[0]
        arguments.append(
            f"RANDOMIZED CONTROLLED EVIDENCE: High-quality RCT evidence supports the clinical benefit of this intervention. "
            f"{ev.citation()} demonstrates efficacy in similar patient populations."
        )

    if case.prior_treatments:
        arguments.append(
            f"STEP THERAPY COMPLETED: This patient has already attempted and failed conservative treatments "
            f"({', '.join(case.prior_treatments)}), satisfying step therapy requirements. "
            f"Further delay in definitive treatment risks clinical deterioration."
        )

    if case.patient.secondary_diagnoses:
        arguments.append(
            f"PATIENT COMPLEXITY: This patient's comorbidities ({', '.join(case.patient.secondary_diagnoses)}) "
            f"increase clinical complexity and justify the requested diagnostic/therapeutic intervention "
            f"to prevent complications and hospitalizations."
        )

    if case.urgency in ["urgent", "emergent"]:
        arguments.append(
            f"URGENCY OF CARE: This case is classified as {case.urgency.upper()}. "
            f"Delayed authorization poses immediate risk to patient safety. "
            f"The treating physician requests expedited peer-to-peer review."
        )

    arguments.append(
        "COST-EFFECTIVENESS: Approving this request is likely more cost-effective than the alternative of "
        "emergency department utilization, hospitalization, or complications arising from delayed treatment."
    )

    return arguments


def _draft_appeal_letter(
    case: ClinicalCase,
    assessment: PolicyAssessment,
    evidence: List[Evidence],
    arguments: List[str],
) -> str:
    """Draft a formal appeal letter."""
    date_str = datetime.now().strftime("%B %d, %Y")
    lines = [
        f"Date: {date_str}",
        "",
        "To: Medical Director, Utilization Management",
        f"Re: Prior Authorization Appeal -- {case.requested_procedure}",
        f"    Patient: [PATIENT_NAME] | DOB: [DATE_OF_BIRTH] | Member ID: [MEMBER_ID]",
        f"    Claim/Auth Reference: [DENIAL_REFERENCE_NUMBER]",
        "",
        "Dear Medical Director,",
        "",
        f"We are writing to formally appeal the denial of prior authorization for {case.requested_procedure} "
        f"(CPT {case.cpt_code}) for the above-referenced patient who carries a diagnosis of "
        f"{case.patient.primary_diagnosis} (ICD-10: {case.icd10_code}).",
        "",
        "CLINICAL SUMMARY:",
        f"{_build_clinical_summary(case)}",
        "",
        "GROUNDS FOR APPEAL:",
    ]

    for i, argument in enumerate(arguments, 1):
        lines.append(f"\n{i}. {argument}")

    if evidence:
        lines.extend(["", "SUPPORTING LITERATURE:"])
        for ev in evidence[:3]:
            lines.append(f"  * {ev.citation()}")

    lines.extend([
        "",
        "REQUEST:",
        f"We respectfully request that this authorization be approved and that a peer-to-peer review "
        f"be arranged with the treating physician if additional clinical information is needed. "
        f"We are available at [PHONE NUMBER] at the payer's earliest convenience.",
        "",
        "Sincerely,",
        "",
        "[TREATING PHYSICIAN NAME, MD]",
        "[PRACTICE NAME]",
        "[NPI: XXXXXXXXXX]",
        "[PHONE] | [FAX]",
        "",
        "Attachments: Clinical notes, prior treatment records, supporting literature",
    ])

    return "\n".join(lines)


def _get_likelihood_label(probability: float) -> ApprovalLikelihood:
    """Convert probability to a human-readable likelihood label."""
    if probability >= 0.85:
        return ApprovalLikelihood.VERY_HIGH
    elif probability >= 0.70:
        return ApprovalLikelihood.HIGH
    elif probability >= 0.50:
        return ApprovalLikelihood.MODERATE
    elif probability >= 0.30:
        return ApprovalLikelihood.LOW
    else:
        return ApprovalLikelihood.VERY_LOW


def _get_escalation_path(probability: float) -> str:
    """Recommend an escalation path based on denial probability."""
    if probability < 0.40:
        return (
            "Level 1 Appeal -> Peer-to-Peer Review with Medical Director -> "
            "Level 2 External Independent Review (IRO) -> State Insurance Commissioner Complaint if needed"
        )
    elif probability < 0.65:
        return "Level 1 Appeal -> Peer-to-Peer Review with Medical Director -> Level 2 Appeal if needed"
    else:
        return "Level 1 Appeal -> Peer-to-Peer Review with Medical Director"
