"""
data-governance: PII-aware customer onboarding with automatic redaction.

Demonstrates JamJet's data governance features (Phase 4.6-4.7):
  - PII detection via built-in regex patterns (email, SSN, phone, credit card)
  - PII redaction modes: mask, hash (SHA-256), or remove
  - Data retention policies with automatic audit entry expiry
  - DataPolicyIr in workflow IR for runtime-level enforcement
  - Audit entries with redacted=true flag

Usage:
    jamjet dev &
    jamjet run workflow.py --input '{
        "customer_id": "CUST-7291",
        "full_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "phone": "555-123-4567",
        "ssn": "123-45-6789",
        "credit_card": "4111-1111-1111-1234"
    }'
"""

from jamjet import workflow, node, State


@workflow(
    id="data-governance-onboarding",
    version="0.1.0",
    # ── Data policy: controls PII handling at the runtime level ──────
    # The runtime's PiiRedactor applies these rules automatically:
    # - Detects PII via regex patterns (email, ssn, phone, credit_card)
    # - Redacts matching fields before audit log storage
    # - Strips prompts and outputs from audit entries
    # - Sets expires_at on audit entries for automatic purge
    data_policy={
        "pii_detectors": ["email", "ssn", "phone", "credit_card"],
        "pii_fields": ["$.email", "$.phone", "$.ssn", "$.credit_card"],
        "redaction_mode": "mask",       # mask | hash | remove
        "retain_prompts": False,
        "retain_outputs": False,
        "retention_days": 90,
    },
    policy={
        "blocked_tools": ["export_pii_bulk", "send_unredacted_*"],
        "model_allowlist": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    },
)
class DataGovernanceOnboarding:
    """Customer onboarding with PII detection, redaction, and retention controls."""

    @node(start=True)
    async def detect_pii(self, state: State) -> State:
        """Detect PII fields in customer data.

        The runtime's PiiRedactor runs these built-in patterns:
        - email:       [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}
        - ssn:         \\d{3}-\\d{2}-\\d{4}
        - phone:       \\d{3}[-.]?\\d{3}[-.]?\\d{4}
        - credit_card: \\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}

        Detected fields are tagged in the audit entry metadata.
        """
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system=(
                "You are a PII detection agent. Identify all personally identifiable "
                "information fields and classify each by type and risk level."
            ),
            prompt=(
                f"Customer: {state['full_name']} ({state['customer_id']})\n"
                f"Email: {state['email']}\n"
                f"Phone: {state['phone']}\n"
                f"SSN: {state['ssn']}\n"
                f"Card: {state['credit_card']}\n\n"
                f"List all PII fields detected with their type and risk level."
            ),
        )
        return {"risk_flags": response.text}

    @node
    async def kyc_verify(self, state: State) -> State:
        """KYC verification using real PII.

        The runtime has access to real PII for this step,
        but the audit log only stores the redacted version
        (because retain_prompts=False and retain_outputs=False).
        """
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a KYC verification agent. Verify identity against "
                "databases and sanctions lists. Report: verified / manual-review / rejected."
            ),
            prompt=(
                f"Customer: {state['full_name']} ({state['customer_id']})\n"
                f"SSN: {state['ssn']}\n"
                f"Risk assessment: {state['risk_flags']}\n\n"
                f"Perform KYC verification."
            ),
        )
        return {"kyc_status": response.text}

    @node
    async def redact_and_store(self, state: State) -> State:
        """Produce a redacted summary safe for the compliance audit log.

        After this step, the runtime's PiiRedactor has already masked
        all PII fields in the state. This step generates a human-readable
        summary for compliance review.

        The audit entry for this node will have:
        - redacted: true
        - expires_at: now + 90 days (from retention_days policy)
        """
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system=(
                "Produce a redacted customer summary safe for audit logs. "
                "Mask all PII: email (j***@***.com), SSN (***-**-XXXX), "
                "phone (***-***-XXXX), card (****-****-****-XXXX)."
            ),
            prompt=(
                f"Customer: {state['full_name']} ({state['customer_id']})\n"
                f"KYC: {state['kyc_status']}\n"
                f"PII detected: {state['risk_flags']}\n\n"
                f"Generate redacted summary. Retention: 90 days."
            ),
        )
        return {"redacted_summary": response.text}
