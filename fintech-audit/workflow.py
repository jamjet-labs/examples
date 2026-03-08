"""
fintech-audit: Loan application with SOC2-compliant audit trail.

Demonstrates JamJet's audit log system:
  - Immutable, append-only audit entries
  - Actor attribution (human vs agent vs system)
  - Policy violation logging with full context
  - HTTP request correlation for forensic analysis
  - Tool call hashing for replay detection

Usage:
    jamjet dev &
    jamjet run workflow.py --input '{
        "applicant_name": "Jane Smith",
        "loan_amount": 750000,
        "loan_purpose": "commercial real estate",
        "credit_score": 720
    }'

    # Approve the loan:
    jamjet resume <exec-id> --event loan_approved --data '{"approved": true}'

    # View audit trail:
    curl http://localhost:7700/audit?execution_id=<exec-id>
"""

from jamjet import workflow, node, State


@workflow(
    id="fintech-audit",
    version="0.1.0",
    # ── Policy: every decision is logged in the audit trail ──────────
    policy={
        "blocked_tools": [
            "delete_*",            # never delete applicant data
            "export_ssn_bulk",     # never bulk-export SSNs
            "modify_credit_score", # never tamper with credit scores
        ],
        "require_approval_for": [
            "approve_loan_over_500k",  # human sign-off for large loans
            "disburse_funds",          # fund disbursement needs approval
        ],
        "model_allowlist": [
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
    },
    # ── Budget ────────────────────────────────────────────────────────
    token_budget={"total_tokens": 200_000},
    cost_budget_usd=3.00,
    on_budget_exceeded="pause",
)
class FinTechAudit:
    """Loan application workflow with full audit trail for SOC2 compliance."""

    @node(start=True)
    async def credit_analysis(self, state: State) -> State:
        """Analyze applicant creditworthiness.

        Audit log captures:
        - node_started: actor=system, worker_id
        - node_completed: token usage, duration
        - policy_violation: if agent tries delete_* or export_ssn_bulk
        """
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a credit analysis AI. Analyze creditworthiness objectively. "
                "NEVER delete records, export SSNs, or modify credit scores."
            ),
            prompt=(
                f"Applicant: {state['applicant_name']}\n"
                f"Loan: ${state['loan_amount']:,.0f} for {state['loan_purpose']}\n"
                f"Credit score: {state['credit_score']}\n\n"
                f"Analyze: credit assessment, debt-to-income, loan-to-value, "
                f"payment history, risk factors."
            ),
        )
        return {"credit_analysis": response.text}

    @node
    async def risk_scoring(self, state: State) -> State:
        """Compute risk score. Actor type: System (automated, no human)."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system="You are a risk scoring engine. Score 1-10 (10 = highest risk).",
            prompt=(
                f"Credit analysis: {state['credit_analysis']}\n"
                f"Loan: ${state['loan_amount']:,.0f} for {state['loan_purpose']}\n\n"
                f"Compute: risk score, category, key risk factors, mitigating factors."
            ),
        )
        return {"risk_score": response.text}

    @node
    async def loan_decision(self, state: State) -> State:
        """Make lending decision. Loans > $500k trigger approval gate.

        If approve_loan_over_500k is called:
        - Audit: tool_approval_required with tool_call_hash (SHA-256)
        - Execution pauses until loan officer approves
        - The tool_call_hash enables replay detection
        """
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a loan decision AI. For loans over $500,000, call "
                "approve_loan_over_500k — it will pause for human review."
            ),
            prompt=(
                f"Applicant: {state['applicant_name']}\n"
                f"Loan: ${state['loan_amount']:,.0f}\n"
                f"Credit: {state['credit_analysis'][:300]}\n"
                f"Risk: {state['risk_score']}\n\n"
                f"Decision: APPROVE / DENY / CONDITIONAL. Include reasoning."
            ),
        )
        return {"loan_decision": response.text}

    @node(human_approval=True, timeout="48h")
    async def officer_review(self, state: State) -> State:
        """Human loan officer reviews the decision.

        Audit log captures:
        - approval_received with actor_type: Human
        - actor_id: the loan officer's user ID from the API token
        - This is the key SOC2 evidence: human oversight of AI decisions
        """
        # This node pauses automatically for human approval.
        # The audit log records who approved, when, and from what IP.
        return {"officer_review": "reviewed"}

    @node
    async def finalize(self, state: State) -> State:
        """Generate final status notice."""
        approved = state.get("approved", False)
        if approved:
            response = await self.model(
                model="claude-haiku-4-5-20251001",
                prompt=(
                    f"Loan APPROVED for {state['applicant_name']}. "
                    f"${state['loan_amount']:,.0f}. Generate confirmation notice."
                ),
            )
        else:
            response = await self.model(
                model="claude-haiku-4-5-20251001",
                prompt=(
                    f"Loan DENIED for {state['applicant_name']}. "
                    f"Generate adverse action notice with dispute rights."
                ),
            )
        return {"final_status": response.text}
