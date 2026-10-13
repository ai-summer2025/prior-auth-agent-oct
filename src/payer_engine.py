"""
Payer policy evaluation engine.
Assesses a clinical case against coverage rules and calculates approval probability.
"""
import json
from typing import List, Tuple
from pathlib import Path
from .models import ClinicalCase, PolicyAssessment


DATA_DIR = Path(__file__).parent.parent / "data"


def load_policies() -> dict:
    """Load payer coverage policies."""
    with open(DATA_DIR / "payer_policies.json", "r") as f:
        return json.load(f)


def assess_case(case: ClinicalCase) -> PolicyAssessment:
    """
    Evaluate a clinical case against payer policies.

    This is the core policy engine — it applies coverage rules, checks medical
    necessity criteria, and calculates an adjusted approval probability.
    """
    policies = load_policies()
    policy_data = policies["policies"].get(case.policy_key)

    if not policy_data:
        # Unknown policy — return neutral assessment
        return PolicyAssessment(
            policy_key=case.policy_key or "unknown",
            indication_tier="approved_with_auth",
            base_probability=0.5,
            adjusted_probability=0.5,
            recommendation="Unable to find specific payer policy. Submit with full clinical documentation.",
        )

    base_probability = policy_data.get("base_approval_probability", 0.5)
    adjustment = 0.0

    # Determine indication tier
    indication_tier = _determine_indication_tier(case, policy_data)

    # Apply tier-based adjustment
    tier_adjustments = {
        "approved_no_auth": 0.35,
        "approved_with_auth": 0.10,
        "requires_step_therapy": -0.10,
        "typically_denied": -0.35,
    }
    adjustment += tier_adjustments.get(indication_tier, 0.0)

    # Check medical necessity criteria
    criteria_met, criteria_missing = _evaluate_necessity_criteria(case, policy_data)
    criteria_met_ratio = len(criteria_met) / max(len(criteria_met) + len(criteria_missing), 1)
    adjustment += (criteria_met_ratio - 0.5) * 0.25

    # Apply global modifiers from case characteristics
    global_factors = policies.get("global_approval_factors", {})
    global_denials = policies.get("global_denial_factors", {})

    if case.specialist_involved:
        adjustment += global_factors.get("specialist_letter_of_support", 0.0)
    if len(case.prior_treatments) >= 2:
        adjustment += global_factors.get("multiple_failed_treatments", 0.0)
    if case.urgency in ["urgent", "emergent"]:
        adjustment += global_factors.get("acute_safety_concern", 0.0)
    if case.symptom_duration_weeks < 4:
        adjustment += global_denials.get("symptom_duration_too_short", 0.0)
    if not case.specialist_involved and indication_tier == "requires_step_therapy":
        adjustment += global_denials.get("no_specialist_referral", 0.0)
    if len(case.prior_treatments) == 0 and indication_tier == "requires_step_therapy":
        adjustment += global_denials.get("incomplete_step_therapy", 0.0)

    # Clamp probability to [0.05, 0.98]
    adjusted_probability = max(0.05, min(0.98, base_probability + adjustment))

    # Identify likely denial reasons
    likely_denials = _identify_denial_risks(case, policy_data, criteria_missing)

    # Generate recommendation
    recommendation = _generate_recommendation(indication_tier, adjusted_probability, criteria_missing)

    return PolicyAssessment(
        policy_key=case.policy_key,
        indication_tier=indication_tier,
        criteria_met=criteria_met,
        criteria_missing=criteria_missing,
        likely_denial_reasons=likely_denials,
        base_probability=base_probability,
        adjusted_probability=adjusted_probability,
        recommendation=recommendation,
    )


def _determine_indication_tier(case: ClinicalCase, policy_data: dict) -> str:
    """Determine which indication tier this case falls into."""
    indication_lower = case.clinical_indication.lower()
    diagnosis_lower = case.patient.primary_diagnosis.lower()
    combined = indication_lower + " " + diagnosis_lower

    tiers = policy_data.get("indication_tiers", {})

    # Check in priority order
    for tier in ["approved_no_auth", "approved_with_auth", "requires_step_therapy", "typically_denied"]:
        conditions = tiers.get(tier, [])
        for condition in conditions:
            words = condition.replace("_", " ").lower().split()
            if any(w in combined for w in words if len(w) > 3):
                return tier

    return "approved_with_auth"


def _evaluate_necessity_criteria(
    case: ClinicalCase, policy_data: dict
) -> Tuple[List[str], List[str]]:
    """
    Check which medical necessity criteria are met vs. missing.
    Returns (criteria_met, criteria_missing).
    """
    criteria_met = []
    criteria_missing = []
    all_criteria = policy_data.get("medical_necessity_criteria", [])

    for criterion in all_criteria:
        crit_lower = criterion.lower()

        met = False

        # Duration check
        if "week" in crit_lower or "month" in crit_lower:
            if "6 week" in crit_lower and case.symptom_duration_weeks >= 6:
                met = True
            elif "4 week" in crit_lower and case.symptom_duration_weeks >= 4:
                met = True
            elif "3 month" in crit_lower and case.symptom_duration_weeks >= 12:
                met = True
            elif "6 month" in crit_lower and case.symptom_duration_weeks >= 24:
                met = True

        # Treatment/step therapy check
        if "fail" in crit_lower and "treatment" in crit_lower or "therapy" in crit_lower:
            if len(case.prior_treatments) >= 1:
                met = True

        # Specialist check
        if "specialist" in crit_lower or "rheumatologist" in crit_lower or "cardiologist" in crit_lower:
            if case.specialist_involved:
                met = True

        # BMI check
        if "bmi" in crit_lower and case.patient.bmi:
            if "40" in crit_lower and case.patient.bmi >= 40:
                met = True
            elif "35" in crit_lower and case.patient.bmi >= 35:
                met = True

        # Neurological / physical exam findings (inferred from supporting notes)
        if "neurological" in crit_lower or "deficit" in crit_lower or "exam" in crit_lower:
            if case.supporting_notes and len(case.supporting_notes) > 50:
                met = True

        # Prior treatments documented
        if "prior" in crit_lower and "treatment" in crit_lower:
            if len(case.prior_treatments) >= 2:
                met = True
            elif len(case.prior_treatments) == 1 and ">=1" in crit_lower:
                met = True

        if met:
            criteria_met.append(criterion)
        else:
            criteria_missing.append(criterion)

    return criteria_met, criteria_missing


def _identify_denial_risks(
    case: ClinicalCase, policy_data: dict, criteria_missing: List[str]
) -> List[str]:
    """Identify the most likely denial reasons for this case."""
    denial_reasons = []
    typical_denials = policy_data.get("typical_denial_reasons", [])

    for reason in typical_denials:
        reason_lower = reason.lower()

        # Flag if step therapy not documented
        if "step therapy" in reason_lower or "conservative treatment" in reason_lower:
            if len(case.prior_treatments) < 2:
                denial_reasons.append(reason)

        # Flag if symptom duration is short
        elif "duration" in reason_lower or "acute" in reason_lower:
            if case.symptom_duration_weeks < 6:
                denial_reasons.append(reason)

        # Flag if no specialist
        elif "specialist" in reason_lower or "consultation" in reason_lower:
            if not case.specialist_involved:
                denial_reasons.append(reason)

        # Flag if clinical notes are sparse
        elif "documentation" in reason_lower or "notes" in reason_lower:
            if not case.supporting_notes or len(case.supporting_notes) < 50:
                denial_reasons.append(reason)

    return denial_reasons[:4]  # Return top 4 risk factors


def _generate_recommendation(
    tier: str, probability: float, criteria_missing: List[str]
) -> str:
    """Generate a clinical recommendation based on assessment."""
    if tier == "approved_no_auth":
        return "This procedure likely does not require prior authorization for this indication. Verify with payer before submitting."

    if probability >= 0.80:
        return "Strong approval likely. Submit with standard documentation package."
    elif probability >= 0.65:
        return "Moderate-to-high approval probability. Strengthen documentation of medical necessity criteria before submitting."
    elif probability >= 0.45:
        return "Borderline case. Address missing criteria before submission and prepare preemptive appeal documentation."
    else:
        if criteria_missing:
            return f"Low approval probability. Must address: {criteria_missing[0][:80]}... Consider peer-to-peer review."
        return "Low approval probability. Recommend peer-to-peer review with medical director before submission."
