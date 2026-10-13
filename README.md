# Prior Auth Agent

An autonomous AI agent that generates complete prior authorization request packets for healthcare procedures. It evaluates clinical cases against payer coverage policies, searches PubMed for supporting evidence, and drafts medical necessity statements and appeal letters — all with no paid API keys required.

## What It Does

Given a patient case (diagnosis, requested procedure, prior treatments, clinical notes), the agent runs a 7-step autonomous loop:

1. **INTAKE** — Parse and validate the clinical case
2. **CODIFY** — Map to ICD-10/CPT codes
3. **ASSESS** — Evaluate against payer coverage policies
4. **EVIDENCE** — Search PubMed for supporting clinical literature (free NCBI API)
5. **DRAFT** — Generate a complete authorization packet
6. **SCORE** — Calculate multi-factor approval probability
7. **STRATEGIZE** — Generate a preemptive appeal strategy if probability is below threshold

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the lumbar MRI demo case
python main.py --demo

# Run all 4 demo cases
python main.py --all-demos

# Run a specific case
python main.py --case cardiac

# Save appeal letter to file
python main.py --case biologics --output-appeal appeal.txt

# Offline mode (skip PubMed)
python main.py --demo --no-pubmed
```

## Demo Cases

- `lumbar-mri` — Lumbar MRI for radiculopathy with conservative treatment failure
- `biologics` — Adalimumab (Humira) for RA after multiple DMARD failures
- `cardiac` — Cardiac catheterization after positive nuclear stress test
- `bariatric` — Sleeve gastrectomy after supervised weight loss failure

## Output

The agent produces:
- **Clinical summary** — Concise paragraph for the prior auth form
- **Medical necessity statement** — Professional narrative with evidence citations
- **Documentation checklist** — Everything needed for submission
- **Approval probability** — Multi-factor score with VERY_HIGH/HIGH/MODERATE/LOW/VERY_LOW label
- **Appeal strategy** (if needed) — Pre-drafted appeal letter + escalation path

## Architecture

```
src/
  models.py         — Clinical data structures (dataclasses)
  code_mapper.py    — ICD-10/CPT code mapping
  payer_engine.py   — Coverage policy evaluation
  evidence_finder.py — PubMed search + relevance scoring
  auth_writer.py    — Auth packet + appeal letter generation
  agent.py          — 7-step orchestration loop
data/
  icd10_cpt_map.json    — Diagnosis/procedure code mappings
  payer_policies.json   — Coverage policies and criteria
```

## No API Keys Required

All dependencies are free and open source:
- NCBI E-utilities API for PubMed (no key needed for < 10 req/sec)
- Standard Python libraries only

## Running Tests

```bash
pytest test_main.py -v
pytest test_main.py -v --tb=short  # compact output
```

39 tests covering all modules. All pass with `--no-pubmed` flag (offline mode).

## License

MIT License — Copyright (c) 2026 ai-summer2025
