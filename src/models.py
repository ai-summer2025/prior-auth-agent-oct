"""
Data models for the Prior Authorization Agent.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ApprovalLikelihood(Enum):
    VERY_HIGH = "Very High (>85%)"
    HIGH = "High (70-85%)"
    MODERATE = "Moderate (50-70%)"
    LOW = "Low (30-50%)"
    VERY_LOW = "Very Low (<30%)"


class AgentStep(Enum):
    INTAKE = "INTAKE"
    CODIFY = "CODIFY"
    ASSESS = "ASSESS"
    EVIDENCE = "EVIDENCE"
    DRAFT = "DRAFT"
    SCORE = "SCORE"
    STRATEGIZE = "STRATEGIZE"
    COMPLETE = "COMPLETE"


@dataclass
class PatientProfile:
    """Represents the patient for whom authorization is being requested."""
    age: int
    sex: str
    primary_diagnosis: str
    secondary_diagnoses: List[str] = field(default_factory=list)
    current_medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    bmi: Optional[float] = None
    insurance_plan: str = "Commercial Insurance"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "age": self.age,
            "sex": self.sex,
            "primary_diagnosis": self.primary_diagnosis,
            "secondary_diagnoses": self.secondary_diagnoses,
            "current_medications": self.current_medications,
            "bmi": self.bmi,
            "insurance_plan": self.insurance_plan,
        }


@dataclass
class ClinicalCase:
    """Structured representation of the clinical authorization request."""
    patient: PatientProfile
    requested_procedure: str
    clinical_indication: str
    symptom_duration_weeks: int
    prior_treatments: List[str] = field(default_factory=list)
    specialist_involved: bool = False
    urgency: str = "routine"
    supporting_notes: str = ""
    icd10_code: str = ""
    cpt_code: str = ""
    policy_key: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_procedure": self.requested_procedure,
            "clinical_indication": self.clinical_indication,
            "symptom_duration_weeks": self.symptom_duration_weeks,
            "prior_treatments": self.prior_treatments,
            "specialist_involved": self.specialist_involved,
            "urgency": self.urgency,
            "icd10_code": self.icd10_code,
            "cpt_code": self.cpt_code,
        }


@dataclass
class Evidence:
    """A piece of supporting clinical evidence from PubMed."""
    pmid: str
    title: str
    authors: str
    journal: str
    year: str
    abstract_snippet: str
    relevance_score: float
    evidence_type: str = "observational"

    def citation(self) -> str:
        return f"{self.authors} ({self.year}). {self.title}. {self.journal}. PMID: {self.pmid}"


@dataclass
class PolicyAssessment:
    """Result of evaluating the case against payer policies."""
    policy_key: str
    indication_tier: str
    criteria_met: List[str] = field(default_factory=list)
    criteria_missing: List[str] = field(default_factory=list)
    likely_denial_reasons: List[str] = field(default_factory=list)
    base_probability: float = 0.5
    adjusted_probability: float = 0.5
    recommendation: str = ""


@dataclass
class AuthRequest:
    """Generated prior authorization request packet."""
    request_id: str
    generated_at: str
    case: ClinicalCase
    assessment: PolicyAssessment
    evidence: List[Evidence]
    clinical_summary: str
    medical_necessity_statement: str
    supporting_documentation_checklist: List[str] = field(default_factory=list)
    expected_approval_probability: float = 0.5
    likelihood_label: ApprovalLikelihood = ApprovalLikelihood.MODERATE


@dataclass
class AppealStrategy:
    """Pre-emptive appeal strategy if authorization is denied."""
    denial_reasons_anticipated: List[str] = field(default_factory=list)
    appeal_arguments: List[str] = field(default_factory=list)
    evidence_to_cite: List[Evidence] = field(default_factory=list)
    appeal_letter_draft: str = ""
    escalation_path: str = ""
    estimated_appeal_success: float = 0.0


@dataclass
class AgentResult:
    """Final output from the prior authorization agent."""
    case: ClinicalCase
    assessment: PolicyAssessment
    auth_request: AuthRequest
    appeal_strategy: Optional[AppealStrategy]
    steps_completed: List[str] = field(default_factory=list)
    total_evidence_found: int = 0
    run_time_seconds: float = 0.0
    recommendation: str = ""
