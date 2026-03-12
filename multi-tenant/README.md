# multi-tenant

Tenant-isolated invoice processing — same workflow, fully isolated tenant data.

```
                    ┌──────────────┐
                    │   validate   │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │    route     │
                    └──┬───────┬──┘
                       │       │
           amount≤10k  │       │  amount>10k
                       │       │
              ┌────────┴──┐ ┌──┴──────────┐
              │auto-approve│ │approval-wait│
              └────────┬──┘ └──┬──────────┘
                       │       │
                    ┌──┴───────┴──┐
                    │     end     │
                    └─────────────┘

        ╔════════════════════════════════════════╗
        ║  Storage partitioned by tenant_id:     ║
        ║  acme  │ globex │ initech │ ...        ║
        ╚════════════════════════════════════════╝
```

## The Problem

SaaS platforms need to run the same workflow logic for multiple customers while ensuring complete data isolation. Without tenant partitioning, one customer's data could leak into another's workflow executions, audit logs, or state.

## How JamJet's Tenant Isolation Works

The runtime's `TenantScopedSqliteBackend` wraps the storage layer and automatically filters all queries by `tenant_id`:

- **Workflow definitions**: composite PK `(tenant_id, workflow_id, version)`
- **Execution state**: all events and snapshots scoped to tenant
- **Audit log**: every entry tagged with `tenant_id`
- **Resource limits**: per-tenant quotas (optional)

## Run it

```bash
jamjet dev &

# Tenant: Acme Corp
jamjet run workflow.yaml \
  --input '{"invoice_id": "INV-001", "vendor": "Supplies Co", "amount": 2500, "currency": "USD"}' \
  --tenant acme

# Tenant: Globex Inc (fully isolated)
jamjet run workflow.yaml \
  --input '{"invoice_id": "INV-042", "vendor": "Cloud Ltd", "amount": 75000, "currency": "USD"}' \
  --tenant globex
```

## What it does

1. **Validate** — checks invoice amount, vendor, currency
2. **Route** — auto-approves under $10k, flags larger for human review
3. **Manager review** — human approval gate (tenant-scoped)
4. **Finalize** — generates confirmation with audit trail

## Key concepts

| Concept | How it works |
|---------|-------------|
| **Tenant scoping** | `--tenant` flag sets `X-Tenant-Id`, runtime partitions all storage |
| **Row-level isolation** | `TenantScopedSqliteBackend` adds `WHERE tenant_id = ?` to every query |
| **Shared definitions** | Same workflow IR deployed once, runs for all tenants |
| **Isolated audit** | Each tenant's audit log is fully partitioned |

## Python equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Next steps

- [data-governance](../data-governance/) — PII detection and redaction
- [oauth-delegation](../oauth-delegation/) — OAuth 2.0 delegated agent auth
- [java-multi-tenant](../java-multi-tenant/) — same example in Java
