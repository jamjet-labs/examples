"""
multi-tenant: Tenant-isolated invoice processing.

Demonstrates JamJet's multi-tenant isolation (Phase 4.4):
  - Tenant-scoped workflow submission
  - Row-level data partitioning (TenantScopedSqliteBackend)
  - Shared workflow definitions across tenants
  - Tenant-isolated audit logs and execution state

Usage:
    jamjet dev &
    jamjet run workflow.py \
        --input '{"invoice_id": "INV-001", "vendor": "Office Supplies Co", "amount": 2500, "currency": "USD"}' \
        --tenant acme

    # Different tenant, fully isolated:
    jamjet run workflow.py \
        --input '{"invoice_id": "INV-042", "vendor": "Cloud Services", "amount": 75000, "currency": "USD"}' \
        --tenant globex
"""

from jamjet import workflow, node, State


@workflow(
    id="multi-tenant-invoices",
    version="0.1.0",
    # Policy applies identically across all tenants
    policy={
        "blocked_tools": ["delete_invoice", "modify_amount"],
        "model_allowlist": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    },
)
class MultiTenantInvoices:
    """Invoice processing workflow — same logic, tenant-isolated data.

    When submitted with --tenant, the runtime partitions all storage access
    by tenant_id. Each tenant gets:
    - Isolated workflow_definitions (composite PK includes tenant_id)
    - Isolated execution state and event logs
    - Isolated audit entries
    - Tenant-specific resource limits (if configured)
    """

    @node(start=True)
    async def validate(self, state: State) -> State:
        """Validate the invoice. Flag large amounts for approval."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system=(
                "You are an invoice validation agent. Check for valid amount, "
                "known vendor, correct currency. Flag amounts > $10,000 for approval."
            ),
            prompt=(
                f"Invoice: {state['invoice_id']}\n"
                f"Vendor: {state['vendor']}\n"
                f"Amount: {state['currency']} {state['amount']:,.2f}\n\n"
                f"Validate this invoice."
            ),
        )
        status = "requires-approval" if state["amount"] > 10_000 else "auto-approved"
        return {"status": status, "audit_note": response.text}

    @node
    async def process(self, state: State) -> State:
        """Route: auto-approve small invoices, pause for large ones."""
        if state["status"] == "auto-approved":
            return {"approver": "system", "audit_note": "Auto-approved: under threshold"}

        # For large invoices, the workflow pauses here for human approval.
        # The audit log records the tenant_id, actor, and approval decision.
        return {"status": "pending-review", "audit_note": "Escalated: above threshold"}

    @node(human_approval=True, timeout="72h")
    async def manager_review(self, state: State) -> State:
        """Human manager reviews large invoices.

        The runtime's TenantScopedSqliteBackend ensures that:
        - Manager for tenant 'acme' only sees acme's pending invoices
        - Manager for tenant 'globex' only sees globex's pending invoices
        - Audit log records: actor_type=Human, actor_id=<manager>, tenant_id=<tenant>
        """
        return {"status": "approved", "approver": "manager"}

    @node
    async def finalize(self, state: State) -> State:
        """Generate final confirmation."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            prompt=(
                f"Invoice {state['invoice_id']} from {state['vendor']} "
                f"({state['currency']} {state['amount']:,.2f}) — {state['status']}. "
                f"Generate a brief confirmation."
            ),
        )
        return {"audit_note": response.text}
