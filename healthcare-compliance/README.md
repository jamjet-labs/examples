# Healthcare Compliance — Policy Engine

A hospital patient intake workflow that demonstrates **JamJet's policy engine** enforcing
HIPAA compliance at runtime — blocking dangerous tools, gating sensitive operations behind
pharmacist approval, and restricting which AI models may touch patient data.

```
Patient arrives at hospital
         |
         v
  +-- Triage Agent --+        Policy: ft-triage-v3 allowed HERE ONLY
  |  (symptom check) |
  +--------+---------+
           |
     +-----+------+
     |             |
     v             v
 Medication    Lab Order         Policy: prescribe_medication -> require_approval
  Review        Agent            Policy: order_lab_* -> require_approval
     |             |
     v             v
  Pharmacist   Physician         (human approval gates)
  Approves     Approves
     |             |
     +------+------+
            |
            v                    Policy: delete_* -> BLOCKED (all layers)
     Discharge Summary           Policy: model must be claude-sonnet-4-6 or claude-haiku-4-5-20251001
            |
            v
    Patient record updated
    (delete_patient_record BLOCKED even if hallucinated)
```

## The Problem This Solves

Without a policy engine, a single misconfigured agent could:

1. **Delete protected health information (PHI)** — an LLM hallucinating a "clean up old records"
   tool call could wipe patient data. HIPAA violation: **$50,000+ fine per incident**.

2. **Submit unreviewed prescriptions** — the AI drafts a prescription and the pharmacy system
   accepts it without a licensed pharmacist clicking "approve". FDA violation.

3. **Route patient data through an unaudited model** — a developer swaps in `gpt-4o` because
   it's cheaper, but the hospital's security team hasn't audited it for PHI handling.
   HIPAA requires all data processors to be on an approved vendor list.

4. **Bypass workflow-level restrictions** — the intake workflow should never touch billing,
   but without policy layering, nothing prevents the agent from calling `modify_insurance_claim`.

## How JamJet's Policy Engine Prevents This

### Three-Layer Policy Hierarchy

```
                Most general
┌──────────────────────────────────┐
│  GLOBAL POLICY                   │
│  blocked: delete_*, export_phi   │
│  approval: prescribe_medication  │
│  models: claude-sonnet, haiku    │
│                                  │
│  ┌────────────────────────────┐  │
│  │  WORKFLOW POLICY           │  │
│  │  blocked: modify_insurance │  │
│  │  approval: schedule_surgery│  │
│  │                            │  │
│  │  ┌──────────────────────┐  │  │
│  │  │  NODE POLICY         │  │  │
│  │  │  models: ft-triage-v3│  │  │  <- override for triage node only
│  │  └──────────────────────┘  │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
                Most specific
```

**Evaluation order**: Most-specific layer wins. If the triage node's policy allows
`ft-triage-v3`, the global allowlist doesn't block it — but only at that node.

### Wildcard Pattern Matching

The policy engine supports glob patterns:

| Pattern | Matches | Use case |
|---------|---------|----------|
| `delete_*` | `delete_patient_record`, `delete_appointment`, `delete_test_results` | Block all deletion tools |
| `order_lab_*` | `order_lab_cbc`, `order_lab_metabolic_panel`, `order_lab_urinalysis` | Gate all lab orders |
| `claude-*` | `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` | Allow all Claude models |

This is critical because new microservices expose new tools constantly. Wildcard patterns
catch tools that didn't exist when the policy was written.

## Run It

```bash
jamjet dev &

# Run the intake workflow
jamjet run workflow.yaml --input '{
  "patient_id": "P-2024-8847",
  "symptoms": "chest pain, shortness of breath, dizziness",
  "allergies": ["penicillin"]
}'

# The workflow will pause at medication review — approve it:
jamjet resume <exec-id> --event pharmacist_approved --data '{"approved": true}'
```

### Try Triggering a Policy Violation

```bash
# This will be BLOCKED by the policy engine — delete_* is blocked globally
jamjet run workflow.yaml --input '{
  "patient_id": "P-2024-8847",
  "symptoms": "discharge - clean up records",
  "allergies": []
}'
```

## What It Does

1. **Triage** — Classifies symptoms using `ft-triage-v3` (allowed by node-level policy override)
2. **Symptom Analysis** — Uses `claude-sonnet-4-6` (global allowlist) to analyze symptoms
3. **Medication Review** — Agent drafts prescription; `prescribe_medication` triggers approval gate
4. **Lab Orders** — Agent suggests labs; `order_lab_*` triggers physician approval gate
5. **Discharge Summary** — Generates summary; any `delete_*` tool calls are blocked

## Key Concepts

| Concept | How it works |
|---------|-------------|
| **Tool blocking** | `blocked_tools: ["delete_*"]` — any tool matching the glob is rejected at runtime |
| **Approval gates** | `require_approval_for: ["prescribe_medication"]` — execution pauses until human approves |
| **Model allowlists** | `model_allowlist: ["claude-sonnet-4-6"]` — unapproved models are blocked before any data is sent |
| **Policy layering** | Global + workflow + node policies. Most-specific layer wins |
| **Wildcard patterns** | `*` matches any characters, `?` matches exactly one character |

## Python Equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Adapting It

- **Add your own blocked tools**: Update the `blocked_tools` list in `workflow.yaml`
- **Change the model allowlist**: Add/remove models from `model_allowlist`
- **Add workflow-specific restrictions**: The `policy` block at workflow level inherits global + adds its own rules
- **Add node-level overrides**: Each node can have its own `policy` block for exceptions

## Further Reading

- [DESIGN.md](./DESIGN.md) — Architecture deep-dive: why three policy layers, how glob matching works internally
- [Policy Engine Tests](https://github.com/jamjet-labs/jamjet/tree/main/runtime/policy/tests/healthcare_workflow.rs) — 9 Rust integration tests modeling this exact scenario
