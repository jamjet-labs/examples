# FinTech Audit — Design Deep Dive

## Why a Separate Audit Log?

JamJet already has an event log for workflow state management. Why add another log?

| Concern | Event log | Audit log |
|---------|-----------|-----------|
| **Purpose** | Reconstruct workflow state | Compliance evidence |
| **Retention** | Days to weeks | Years (SOC2: 1yr, HIPAA: 6yr, SOX: 7yr) |
| **Mutations** | Compacted, pruned | NEVER modified |
| **Consumers** | Scheduler, workers | Compliance team, auditors, SIEM |
| **Schema** | EventKind variants | Enriched with actor, HTTP context, hashes |
| **Queried by** | execution_id + sequence | actor_id, event_type, time range, tool hash |

The audit log is a **compliance-grade** record. It answers questions that the event log
can't:
- "Who approved this loan at 3:47pm on March 14th?"
- "How many policy violations did this agent trigger this quarter?"
- "Was this tool call a replay attack?"

## Append-Only Architecture

### The Trait Enforces Immutability

```rust
#[async_trait]
pub trait AuditBackend: Send + Sync {
    async fn append(&self, entry: AuditLogEntry) -> Result<(), AuditError>;
    async fn query(&self, q: &AuditQuery) -> Result<Vec<AuditLogEntry>, AuditError>;
    async fn count(&self, q: &AuditQuery) -> Result<u64, AuditError>;
}
```

There is no `update()`. There is no `delete()`. The Rust compiler won't let you add one
without modifying the trait definition — and the trait is in the `jamjet-audit` crate,
not application code.

This is a **compile-time guarantee** of immutability. No runtime check, no "please don't
delete" comment. The type system prevents it.

### Idempotent Appends

```sql
INSERT OR IGNORE INTO audit_log (id, ...) VALUES (?, ...)
```

The `OR IGNORE` clause means:
- First insert: entry is written
- Duplicate insert (same ID): silently ignored

This is critical for crash recovery. If a worker crashes after writing the audit entry
but before acknowledging the work item, the worker will replay the event on restart. The
duplicate insert is harmless — no duplicate audit records.

## Actor Attribution

### The Problem with "system"

Many systems log all automated actions as actor "system". This is useless for compliance:

```
Auditor: "Who approved this $750k loan?"
You: "The system."
Auditor: "Which system? A human? An AI? An automated script?"
You: "...the system."
Auditor: [writes up control deficiency]
```

### JamJet's Attribution Chain

```
Event received
      │
      v
┌─────────────────────────────────────────────────────────┐
│ 1. Check event type → derive actor                      │
│    ApprovalReceived → user_id from event (Human)        │
│    NodeStarted → worker_id from event (System)          │
│    PolicyViolation → from request context               │
│                                                          │
│ 2. Fall back to request context → API token name        │
│    POST /api/v1/executions → token "loan-officer-jsmith"│
│                                                          │
│ 3. Fall back to default → "system" (System)             │
│    Internal scheduler events                             │
└─────────────────────────────────────────────────────────┘
```

This means:
- Human actions are attributed to the specific person
- Agent actions are attributed to the specific agent
- System actions are attributed to the specific worker or scheduler

The auditor can now answer: "Loan officer J. Smith approved this loan at 3:47pm from
IP 10.0.3.47 via POST /api/v1/executions/LOAN-2024-00847/approve."

## Tool Call Hashing

### How It Works

For every tool-invocation event, the audit enricher computes:

```
hash = SHA-256(tool_name + ":" + input_json)
```

For example:
```
tool_name = "approve_loan_over_500k"
input_json = '{"applicant":"Jane Smith","amount":750000}'

hash = SHA-256("approve_loan_over_500k:{"applicant":"Jane Smith","amount":750000}")
     = "a1b2c3d4e5f6..."
```

### Replay Detection

If two audit entries have the same `tool_call_hash`:

| Scenario | Same hash? | Same execution? | Action |
|----------|-----------|-----------------|--------|
| Normal retry (same exec) | Yes | Yes | Expected, ignore |
| Replay attack | Yes | No | Alert! Different execution, same payload |
| Duplicate request | Yes | Yes | Idempotent, harmless |
| Different inputs | No | Either | Normal operation |

The security team queries:
```sql
SELECT tool_call_hash, COUNT(*) as cnt
FROM audit_log
WHERE tool_call_hash IS NOT NULL
GROUP BY tool_call_hash
HAVING cnt > 1
ORDER BY cnt DESC
```

Any hash appearing across different executions is suspicious.

## HTTP Context Correlation

### Why Capture HTTP Metadata?

The audit log entry connects to the broader request lifecycle:

```
Client (10.0.3.47)
    │
    │ POST /api/v1/executions/LOAN-2024-00847/approve
    │ X-Request-ID: req-abc123-def456
    │ Authorization: Bearer <loan-officer-jsmith token>
    │
    ▼
API Gateway (logs: req-abc123-def456, 200 OK, 142ms)
    │
    ▼
JamJet API Server
    │
    ├── Audit entry created:
    │   request_id: req-abc123-def456
    │   method: POST
    │   path: /api/v1/executions/LOAN-2024-00847/approve
    │   ip: 10.0.3.47
    │   actor: loan-officer-jsmith
    │
    ▼
Audit Log (SQLite / SIEM)
```

To investigate an incident:
1. Find the audit entry with the suspicious action
2. Get the `request_id` from the entry
3. Search the API gateway logs for that `request_id`
4. See the full HTTP request, response code, timing
5. Trace to the source IP and correlate with VPN/SSO logs

## SIEM Integration

The `SqliteAuditBackend` is the built-in implementation. For production, implement the
`AuditBackend` trait for your SIEM:

```rust
struct SplunkAuditBackend { /* ... */ }

#[async_trait]
impl AuditBackend for SplunkAuditBackend {
    async fn append(&self, entry: AuditLogEntry) -> Result<(), AuditError> {
        // POST to Splunk HEC endpoint
        // entry is serialized as JSON
    }

    async fn query(&self, q: &AuditQuery) -> Result<Vec<AuditLogEntry>, AuditError> {
        // SPL query against Splunk index
    }

    async fn count(&self, q: &AuditQuery) -> Result<u64, AuditError> {
        // SPL count query
    }
}
```

Options for production:
- **Splunk** — HEC endpoint, SPL queries
- **Datadog** — Log pipeline, Datadog query language
- **AWS CloudWatch** — Log groups, CloudWatch Insights
- **Elasticsearch** — Direct indexing, Lucene queries
- **BigQuery** — For long-term analytics and SOC2 evidence

## Retention and Compliance

| Standard | Minimum retention | Typical |
|----------|-------------------|---------|
| SOC2 Type II | 1 year | 3 years |
| HIPAA | 6 years | 7 years |
| SOX | 7 years | 10 years |
| PCI DSS | 1 year | 3 years |
| GDPR | "as long as necessary" | Case-by-case |

The audit log's independence from the event log means you can:
- Prune workflow events after 30 days (reduce storage costs)
- Keep audit entries for 7 years (compliance)
- Export audit entries to cold storage (S3 Glacier) for cost optimization
- Run compliance queries against the audit log without touching the event log

## Production Checklist

- [ ] Configure audit log retention per your compliance requirements
- [ ] Set up SIEM integration (Splunk, Datadog, etc.)
- [ ] Enable real-time alerting on `policy_violation` events
- [ ] Configure actor attribution for your auth system (OIDC, SAML)
- [ ] Verify `tool_call_hash` uniqueness monitoring
- [ ] Test crash replay idempotency
- [ ] Document the audit trail for your SOC2 auditor
- [ ] Set up quarterly audit log review process
