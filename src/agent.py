"""
Prior Authorization Agent — Main Orchestration Loop.

This is the core agentic system that autonomously:
  Step 1: INTAKE    — Parse and validate the clinical case
  Step 2: CODIFY    — Map to ICD-10/CPT codes
  Step 3: ASSESS    — Evaluate against payer coverage policies
  Step 4: EVIDENCE  — Search PubMed for supporting clinical literature
  Step 5: DRAFT     — Generate complete authorization packet
  Step 6: SCORE     — Calculate multi-factor approval probability
  Step 7: STRATEGIZE— Generate preemptive appeal if probability is low
"""
import time
import sys
from typing import Optional, Callable
from .models import (
    ClinicalCase, PatientProfile, AgentStep, AgentResult, AppealStrategy,
    ApprovalLikelihood,
)
from .code_mapper import map_diagnosis_to_code, load_mappings
from .payer_engine import assess_case
from .evidence_finder import get_evidence_for_case
from .auth_writer import generate_auth_request, generate_appeal_strategy


# Threshold below which we proactively generate appeal strategy
APPEAL_THRESHOLD = 0.70
VERBOSE = True


def log(msg: str, step: Optional[AgentStep] = None, color: str = ""):
    """Print a formatted agent log message."""
    if not VERBOSE:
        return
    prefix = f"[{step.value}]" if step else "[AGENT]"
    colors = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "cyan": "\033[96m", "bold": "\033[1m", "": ""}
    reset = "\033[0m"
    print(f"{colors.get(color, '')}{prefix} {msg}{reset}", flush=True)


def run_agent(
    patient_age: int,
    patient_sex: str,
    primary_diagnosis: str,
    requested_procedure: str,
    clinical_indication: str,
    symptom_duration_weeks: int,
    prior_treatments: list,
    secondary_diagnoses: list = None,
    current_medications: list = None,
    specialist_involved: bool = False,
    urgency: str = "routine",
    supporting_notes: str = "",
    bmi: Optional[float] = None,
    use_pubmed: bool = True,
    verbose: bool = True,
) -> AgentResult:
    """
    Run the full prior authorization agent pipeline.

    This is the main entry point for the agentic system.
    Returns an AgentResult with the complete authorization packet.
    """
    global VERBOSE
    VERBOSE = verbose
    start_time = time.time()
    steps_completed = []

    # STEP 1: INTAKE
    log("Parsing and validating clinical case...", AgentStep.INTAKE, "cyan")
    patient = PatientProfile(
        age=patient_age,
        sex=patient_sex,
        primary_diagnosis=primary_diagnosis,
        secondary_diagnoses=secondary_diagnoses or [],
        current_medications=current_medications or [],
        bmi=bmi,
    )
    case = ClinicalCase(
        patient=patient,
        requested_procedure=requested_procedure,
        clinical_indication=clinical_indication,
        symptom_duration_weeks=symptom_duration_weeks,
        prior_treatments=prior_treatments,
        specialist_involved=specialist_involved,
        urgency=urgency,
        supporting_notes=supporting_notes,
    )
    log(f"Patient: {patient_age}yo {patient_sex} | Diagnosis: {primary_diagnosis}", AgentStep.INTAKE)
    log(f"Procedure: {requested_procedure} | Duration: {symptom_duration_weeks} weeks", AgentStep.INTAKE)
    steps_completed.append(AgentStep.INTAKE.value)

    # STEP 2: CODIFY
    log("Mapping to ICD-10/CPT codes...", AgentStep.CODIFY, "cyan")
    icd10, cpt, policy_key = map_diagnosis_to_code(primary_diagnosis, requested_procedure)
    case.icd10_code = icd10 or "Z00.00"
    case.cpt_code = cpt or "00000"
    case.policy_key = policy_key or "unknown"
    log(f"ICD-10: {case.icd10_code} | CPT: {case.cpt_code} | Policy: {case.policy_key}", AgentStep.CODIFY)
    steps_completed.append(AgentStep.CODIFY.value)

    # STEP 3: ASSESS
    log("Evaluating against payer coverage policies...", AgentStep.ASSESS, "cyan")
    assessment = assess_case(case)
    log(f"Indication tier: {assessment.indication_tier}", AgentStep.ASSESS)
    log(f"Criteria met: {len(assessment.criteria_met)} | Missing: {len(assessment.criteria_missing)}", AgentStep.ASSESS)
    log(f"Base approval probability: {assessment.base_probability:.0%}", AgentStep.ASSESS)
    if assessment.likely_denial_reasons:
        log(f"Risk factors identified: {len(assessment.likely_denial_reasons)}", AgentStep.ASSESS, "yellow")
    steps_completed.append(AgentStep.ASSESS.value)

    # STEP 4: EVIDENCE
    log("Searching PubMed for supporting clinical evidence...", AgentStep.EVIDENCE, "cyan")
    evidence = get_evidence_for_case(case, use_pubmed=use_pubmed)
    log(f"Found {len(evidence)} relevant evidence sources", AgentStep.EVIDENCE)
    for ev in evidence[:3]:
        log(f"  * [{ev.evidence_type.upper()}] {ev.title[:70]}... (relevance: {ev.relevance_score:.2f})", AgentStep.EVIDENCE)
    steps_completed.append(AgentStep.EVIDENCE.value)

    # STEP 5: DRAFT
    log("Generating prior authorization packet...", AgentStep.DRAFT, "cyan")
    auth_request = generate_auth_request(case, assessment, evidence)
    log(f"Auth Request ID: {auth_request.request_id}", AgentStep.DRAFT)
    log(f"Documentation checklist: {len(auth_request.supporting_documentation_checklist)} items", AgentStep.DRAFT)
    steps_completed.append(AgentStep.DRAFT.value)

    # STEP 6: SCORE
    log("Calculating approval probability...", AgentStep.SCORE, "cyan")
    probability = assessment.adjusted_probability
    likelihood = auth_request.likelihood_label
    color = "green" if probability >= 0.70 else "yellow" if probability >= 0.45 else "red"
    log(f"Adjusted approval probability: {probability:.1%} -- {likelihood.value}", AgentStep.SCORE, color)
    steps_completed.append(AgentStep.SCORE.value)

    # STEP 7: STRATEGIZE (if needed)
    appeal_strategy = None
    if probability < APPEAL_THRESHOLD:
        log(f"Probability below {APPEAL_THRESHOLD:.0%} threshold -- generating preemptive appeal strategy...", AgentStep.STRATEGIZE, "yellow")
        appeal_strategy = generate_appeal_strategy(case, assessment, evidence)
        log(f"Appeal arguments generated: {len(appeal_strategy.appeal_arguments)}", AgentStep.STRATEGIZE)
        log(f"Estimated appeal success: {appeal_strategy.estimated_appeal_success:.1%}", AgentStep.STRATEGIZE)
        steps_completed.append(AgentStep.STRATEGIZE.value)
    else:
        log("Approval probability sufficient -- appeal strategy not needed at this stage.", AgentStep.STRATEGIZE)

    steps_completed.append(AgentStep.COMPLETE.value)

    # Build final recommendation
    recommendation = _build_final_recommendation(assessment, appeal_strategy, evidence)

    run_time = time.time() - start_time
    log(f"Agent completed in {run_time:.2f}s | Steps: {len(steps_completed)}", color="bold")

    return AgentResult(
        case=case,
        assessment=assessment,
        auth_request=auth_request,
        appeal_strategy=appeal_strategy,
        steps_completed=steps_completed,
        total_evidence_found=len(evidence),
        run_time_seconds=run_time,
        recommendation=recommendation,
    )


def _build_final_recommendation(assessment, appeal_strategy, evidence) -> str:
    """Build the final actionable recommendation."""
    prob = assessment.adjusted_probability

    if prob >= 0.85:
        return (
            "SUBMIT: High confidence in approval. "
            "Gather documentation checklist items and submit within 48 hours."
        )
    elif prob >= 0.70:
        return (
            "SUBMIT WITH STRENGTHENING: Good approval probability. "
            "Address missing criteria before submission to improve chances. "
            "Peer-to-peer review not yet needed."
        )
    elif prob >= 0.50:
        return (
            "PREPARE CAREFULLY: Moderate probability. "
            "Address ALL missing criteria before submission. "
            "Have the peer-to-peer talking points ready. "
            "Preemptive appeal strategy has been generated."
        )
    elif prob >= 0.30:
        return (
            "HIGH DENIAL RISK: Consider requesting peer-to-peer before formal submission. "
            "Use the appeal letter template if denied. "
            "Explore expedited review options if patient condition is worsening."
        )
    else:
        return (
            "VERY HIGH DENIAL RISK: Address fundamental gaps in documentation. "
            "Consider requesting peer-to-peer review directly. "
            "Review alternative covered procedures or care pathways. "
            "Detailed appeal strategy has been generated."
        )


def print_results(result: AgentResult) -> None:
    """Print a formatted summary of the agent results."""
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    SEP = "=" * 70

    print(f"\n{BOLD}{CYAN}{SEP}{RESET}")
    print(f"{BOLD}  PRIOR AUTHORIZATION AGENT -- RESULTS{RESET}")
    print(f"{BOLD}{CYAN}{SEP}{RESET}\n")

    print(f"{BOLD}CASE SUMMARY{RESET}")
    print(f"  Patient:     {result.case.patient.age}yo {result.case.patient.sex}")
    print(f"  Diagnosis:   {result.case.patient.primary_diagnosis} (ICD-10: {result.case.icd10_code})")
    print(f"  Procedure:   {result.case.requested_procedure} (CPT: {result.case.cpt_code})")
    print(f"  Duration:    {result.case.symptom_duration_weeks} weeks")
    print(f"  Auth ID:     {result.auth_request.request_id}")
    print(f"  Generated:   {result.auth_request.generated_at[:19]}")

    print(f"\n{BOLD}POLICY ASSESSMENT{RESET}")
    tier_colors = {
        "approved_no_auth": GREEN,
        "approved_with_auth": GREEN,
        "requires_step_therapy": YELLOW,
        "typically_denied": RED,
    }
    tier_color = tier_colors.get(result.assessment.indication_tier, "")
    print(f"  Coverage tier:   {tier_color}{result.assessment.indication_tier.replace('_', ' ').title()}{RESET}")

    prob = result.assessment.adjusted_probability
    prob_color = GREEN if prob >= 0.70 else YELLOW if prob >= 0.45 else RED
    print(f"  Approval prob:   {prob_color}{prob:.1%} -- {result.auth_request.likelihood_label.value}{RESET}")
    print(f"  Policy matched:  {result.case.policy_key.replace('_', ' ').title()}")

    if result.assessment.criteria_met:
        print(f"\n  {GREEN}Criteria Met ({len(result.assessment.criteria_met)}):{RESET}")
        for c in result.assessment.criteria_met[:3]:
            print(f"    * {c[:80]}")

    if result.assessment.criteria_missing:
        print(f"\n  {YELLOW}Missing Criteria ({len(result.assessment.criteria_missing)}):{RESET}")
        for c in result.assessment.criteria_missing[:3]:
            print(f"    * {c[:80]}")

    if result.assessment.likely_denial_reasons:
        print(f"\n  {RED}Denial Risk Factors:{RESET}")
        for d in result.assessment.likely_denial_reasons[:3]:
            print(f"    * {d[:80]}")

    print(f"\n{BOLD}SUPPORTING EVIDENCE ({result.total_evidence_found} sources){RESET}")
    for ev in result.auth_request.evidence[:3]:
        print(f"  [{ev.evidence_type.upper()}] {ev.title[:65]}...")
        print(f"    {ev.authors} ({ev.year}) -- PMID: {ev.pmid}")

    print(f"\n{BOLD}DOCUMENTATION CHECKLIST{RESET}")
    for item in result.auth_request.supporting_documentation_checklist:
        print(f"  {item}")

    if result.appeal_strategy:
        print(f"\n{BOLD}{YELLOW}PREEMPTIVE APPEAL STRATEGY{RESET}")
        print(f"  Estimated appeal success: {result.appeal_strategy.estimated_appeal_success:.1%}")
        print(f"  Escalation path: {result.appeal_strategy.escalation_path}")
        print(f"\n  Top Appeal Arguments:")
        for i, arg in enumerate(result.appeal_strategy.appeal_arguments[:3], 1):
            print(f"  {i}. {arg[:120]}...")
        print(f"\n  Full appeal letter available -- run with --output-appeal to save")

    print(f"\n{BOLD}{CYAN}AGENT RECOMMENDATION{RESET}")
    print(f"  {result.recommendation}")
    print(f"\n{BOLD}{CYAN}{SEP}{RESET}")
    print(f"  Steps completed: {' -> '.join(result.steps_completed)}")
    print(f"  Evidence found:  {result.total_evidence_found} sources")
    print(f"  Run time:        {result.run_time_seconds:.2f}s")
    print(f"{BOLD}{CYAN}{SEP}{RESET}\n")
