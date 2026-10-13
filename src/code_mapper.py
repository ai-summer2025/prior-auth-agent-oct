"""Maps clinical descriptions to ICD-10 and CPT codes."""
import json
import re
import os
from typing import Optional, Tuple
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def load_mappings() -> dict:
    mapping_file = DATA_DIR / "icd10_cpt_map.json"
    with open(mapping_file, "r") as f:
        return json.load(f)

def map_diagnosis_to_code(diagnosis_text: str, procedure_text: str) -> Tuple[str, str, str]:
    mappings = load_mappings()
    text_lower = (diagnosis_text + " " + procedure_text).lower()
    best_procedure_match = None
    for keyword, data in mappings["procedure_keywords"].items():
        if keyword in text_lower:
            best_procedure_match = data
            break
    best_diagnosis_match = None
    for keyword, data in mappings["diagnosis_keywords"].items():
        if keyword in text_lower:
            best_diagnosis_match = data
            break
    icd10 = ""
    cpt = ""
    policy_key = ""
    if best_diagnosis_match:
        icd10 = best_diagnosis_match.get("icd10", "")
        policy_key = best_diagnosis_match.get("policy_key", "")
    if best_procedure_match:
        cpt = best_procedure_match.get("cpt", "")
        if not policy_key:
            policy_key = best_procedure_match.get("policy_key", "")
    return icd10, cpt, policy_key

def get_indication_type(diagnosis: str, policy: dict) -> str:
    diag_lower = diagnosis.lower()
    indication_tiers = policy.get("indication_tiers", {})
    for tier, conditions in indication_tiers.items():
        for condition in conditions:
            condition_words = condition.replace("_", " ").lower()
            if any(word in diag_lower for word in condition_words.split()):
                return tier
    return "approved_with_auth"

def describe_icd10(code: str) -> str:
    mappings = load_mappings()
    for keyword, data in mappings["diagnosis_keywords"].items():
        if data.get("icd10") == code:
            return data.get("description", code)
    return code

def describe_cpt(code: str) -> str:
    mappings = load_mappings()
    for keyword, data in mappings["procedure_keywords"].items():
        if data.get("cpt") == code:
            return data.get("description", code)
    return code
