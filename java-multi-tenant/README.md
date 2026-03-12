# java-multi-tenant

Multi-tenant invoice processing — same workflow, fully isolated tenant data.

## Run it

```bash
mvn compile exec:java
```

To submit to a running runtime with tenant isolation:

```bash
jamjet dev &
mvn compile exec:java
```

## What it does

1. Builds an invoice processing workflow (validate, route, process)
2. Runs the same workflow for two tenants: Acme Corp and Globex Inc
3. Submits tenant-scoped executions to the runtime via `X-Tenant-Id`
4. The runtime enforces row-level data partitioning per tenant

## Key concepts

- **Tenant isolation** — each tenant's workflows, executions, state, and audit logs are partitioned at the storage layer
- **Shared workflow definitions** — the same IR can be deployed across tenants
- **Runtime enforcement** — `TenantScopedSqliteBackend` filters all queries by `tenant_id`
- **Workflow builder** — `Workflow.builder()` with typed record state

## Next steps

- [java-data-governance](../java-data-governance/) — PII detection and redaction
- [java-oauth-agent](../java-oauth-agent/) — OAuth 2.0 delegated agent auth
- [fintech-audit](../fintech-audit/) — SOC2-compliant audit trail
