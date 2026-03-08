"""
healthcare-compliance: HIPAA-compliant patient intake with policy enforcement.

Demonstrates JamJet's policy engine:
  - Tool blocking: delete_*, export_phi_bulk
  - Approval gates: prescribe_medication, order_lab_*
  - Model allowlists: only audited models may process PHI
  - Node-level policy overrides: triage uses ft-triage-v3

Usage:
    jamjet dev &
    jamjet run workflow.py --input '{
        "patient_id": "P-2024-8847",
        "symptoms": "chest pain, shortness of breath",
        "allergies": ["penicillin"]
    }'

    # When prompted for pharmacist approval:
    jamjet resume <exec-id> --event pharmacist_approved --data '{"approved": true}'
"""

from jamjet import workflow, node, State


@workflow(
    id="healthcare-compliance",
    version="0.1.0",
    # ── Global policy: applies to every node ─────────────────────────
    policy={
        "blocked_tools": [
            "delete_*",           # block ALL deletion tools (wildcard)
            "export_phi_bulk",    # block bulk PHI export
        ],
        "require_approval_for": [
            "prescribe_medication",  # pharmacist must approve
            "order_lab_*",           # physician must approve all lab orders
            "discharge_patient",     # attending must sign off
        ],
        "model_allowlist": [
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
    },
    # ── Budget: cap costs per patient intake ──────────────────────────
    token_budget={"total_tokens": 500_000},
    cost_budget_usd=5.00,
    on_budget_exceeded="pause",
)
class HealthcareCompliance:
    """HIPAA-compliant patient intake workflow with policy enforcement."""

    @node(
        start=True,
        # Node-level policy override: allows ft-triage-v3 at THIS node only.
        # Other nodes still enforce the global allowlist (claude-sonnet, haiku).
        policy={
            "model_allowlist": [
                "claude-sonnet-4-6",
                "ft-triage-v3",
            ],
        },
    )
    async def triage(self, state: State) -> State:
        """Classify patient urgency using the fine-tuned triage model."""
        response = await self.model(
            model="ft-triage-v3",
            system=(
                "You are a hospital triage AI trained on emergency department protocols. "
                "Classify urgency: EMERGENT, URGENT, SEMI-URGENT, NON-URGENT. "
                "List top 3 differential diagnoses. "
                "Flag symptoms requiring immediate physician attention."
            ),
            prompt=(
                f"Patient ID: {state['patient_id']}\n"
                f"Presenting symptoms: {state['symptoms']}\n"
                f"Known allergies: {', '.join(state['allergies'])}\n\n"
                f"Classify urgency and provide differential diagnoses."
            ),
        )
        return {"triage_result": response.text}

    @node
    async def symptom_analysis(self, state: State) -> State:
        """Deep symptom analysis by a board-certified physician AI."""
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a board-certified internal medicine physician AI assistant. "
                "Analyze symptoms considering the triage classification and patient allergies."
            ),
            prompt=(
                f"Patient: {state['patient_id']}\n"
                f"Symptoms: {state['symptoms']}\n"
                f"Allergies: {', '.join(state['allergies'])}\n"
                f"Triage: {state['triage_result']}\n\n"
                f"Provide:\n"
                f"1. Detailed symptom analysis\n"
                f"2. Recommended diagnostic tests\n"
                f"3. Initial treatment considerations (respecting allergies)\n"
                f"4. Red flags requiring immediate escalation"
            ),
        )
        return {"analysis": response.text}

    @node
    async def medication_review(self, state: State) -> State:
        """Draft prescriptions. prescribe_medication triggers pharmacist approval."""
        # If this step calls prescribe_medication, the policy engine will
        # automatically PAUSE execution and notify the pharmacist.
        # No code change needed — the policy is declared at the workflow level.
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a clinical pharmacist AI. Recommend medications based on the analysis. "
                "Call prescribe_medication for each prescription. The system will automatically "
                "pause for pharmacist review."
            ),
            prompt=(
                f"Patient: {state['patient_id']}\n"
                f"Allergies: {', '.join(state['allergies'])}\n"
                f"Analysis: {state['analysis']}\n\n"
                f"Recommend medications with drug, dosage, route, frequency, duration."
            ),
        )
        return {"medication_plan": response.text}

    @node
    async def lab_orders(self, state: State) -> State:
        """Suggest lab tests. order_lab_* triggers physician approval via wildcard."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system=(
                "You are a lab order assistant. Recommend appropriate lab tests. "
                "Each order_lab_* call will require physician approval."
            ),
            prompt=(
                f"Patient: {state['patient_id']}\n"
                f"Analysis: {state['analysis']}\n"
                f"Triage: {state['triage_result']}\n\n"
                f"Recommend necessary lab tests."
            ),
        )
        return {"lab_orders": response.text}

    @node
    async def discharge_summary(self, state: State) -> State:
        """Generate discharge summary. Any delete_* calls are BLOCKED by policy."""
        # Even if the LLM hallucinates a delete_patient_record call,
        # the policy engine blocks it before it reaches any tool.
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a discharge summary AI. Create a comprehensive discharge summary. "
                "NEVER attempt to delete or modify existing patient records."
            ),
            prompt=(
                f"Patient: {state['patient_id']}\n"
                f"Symptoms: {state['symptoms']}\n"
                f"Triage: {state['triage_result']}\n"
                f"Analysis: {state['analysis']}\n"
                f"Medications: {state['medication_plan']}\n"
                f"Labs: {state['lab_orders']}\n\n"
                f"Generate discharge summary with chief complaint, assessment, "
                f"treatment, medications, follow-up instructions, and warning signs."
            ),
        )
        return {"discharge_summary": response.text}
