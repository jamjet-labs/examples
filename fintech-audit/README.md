# FinTech Audit — SOC2 Compliance Audit Trail

A FinTech loan application workflow that demonstrates **JamJet's audit log system** —
immutable event recording, actor attribution, forensic correlation, and compliance
reporting for SOC2 Type II certification.

```
Loan application submitted via API
  |  (HTTP context captured: request_id, IP, method, path)
  |
  v
Credit Analysis Agent              actor: credit-analysis-agent-v2
  |                                 audit: node_started, node_completed
  |
  |  Agent tries delete_credit_report
  |  → BLOCKED by policy engine
  |  → audit: policy_violation { decision: "blocked", rule: "delete_*" }
  |
  v
Risk Scoring                        actor: system
  |                                 audit: node_started, node_completed
  v
Loan Decision                       actor: loan-decision-agent-v1
  |
  |  Agent calls approve_loan_over_500k
  |  → PAUSED: require_approval
  |  → audit: tool_approval_required { tool: "approve_loan_over_500k" }
  |
  v
Loan Officer Reviews                actor: loan-officer-jsmith (human)
  |  /approve or /reject            audit: approval_received { user_id, decision }
  v
Application Finalized
  |
  v
┌─────────────────────────────────────────────────────────┐
│              IMMUTABLE AUDIT LOG                         │
│                                                          │
│  Every event above is recorded with:                     │
│  - Unique audit entry ID                                 │
│  - Event ID + execution ID                               │
│  - Actor ID + actor type (human/agent/system)            │
│  - Tool call hash (SHA-256 for replay detection)         │
│  - Policy decision (if applicable)                       │
│  - HTTP context (request_id, method, path, IP)           │
│  - Timestamp + raw event JSON                            │
│                                                          │
│  NEVER updated. NEVER deleted.                           │
│  INSERT OR IGNORE only (idempotent for crash replay).    │
└─────────────────────────────────────────────────────────┘
```

## The Problem This Solves

### 1. The $40,000 Audit Gap
During a SOC2 Type II audit, the auditor found a 3-hour gap in the event log on March 14th.
No one could explain what happened during that window. The remediation consulting cost
**$40,000** — more than the entire monthly AI spend.

**JamJet's fix**: Separate, append-only audit log that captures every security-relevant event.
The audit log is independent of the workflow event log — it can be retained indefinitely and
exported to SIEMs.

### 2. The "Who Did That?" Problem
An unauthorized API call tried to bulk-export applicant SSNs at 3:47pm. The security team
could see the action in logs, but couldn't determine **who** made the call. All actions were
logged as actor "system".

**JamJet's fix**: Every audit entry has `actor_id` and `actor_type` (Human / Agent / System).
The actor is derived from the API token, the event type, or the worker ID. The security team
can filter by actor to see everything a specific user or agent did.

### 3. The Replay Attack
An attacker captured a legitimate API request and replayed it 50 times, each creating a new
loan application with the same SSN. Without tool call hashing, these looked like 50 separate
legitimate requests.

**JamJet's fix**: `tool_call_hash` is a SHA-256 of `tool_name + ":" + input_json`. Duplicate
hashes in the audit log indicate potential replay attacks.

### 4. The Missing Correlation
The security team found a suspicious policy violation in the audit log but couldn't trace it
back to the originating API request. They had the audit entry and the API gateway logs, but
no way to connect them.

**JamJet's fix**: HTTP request context (request_id, method, path, IP address) is captured in
every audit entry. Cross-reference with the API gateway using `request_id`.

## How the Audit Log Works

### Audit Entry Anatomy

```
┌─────────────────────────────────────────────────────────────┐
│                      AuditLogEntry                          │
│                                                              │
│  id:               "550e8400-e29b-..."    ← unique per entry │
│  event_id:         "6ba7b810-9dad-..."    ← links to Event   │
│  execution_id:     "LOAN-2024-00847"      ← links to exec    │
│  sequence:         7                       ← monotonic        │
│  event_type:       "policy_violation"      ← serde tag        │
│                                                              │
│  actor_id:         "credit-analysis-agent-v2"                │
│  actor_type:       Agent                                     │
│                                                              │
│  tool_call_hash:   "a1b2c3d4..."          ← SHA-256          │
│  policy_decision:  "blocked"              ← allow/block/req  │
│                                                              │
│  http_request_id:  "req-abc123"           ← API correlation  │
│  http_method:      "POST"                                    │
│  http_path:        "/api/v1/executions/LOAN-2024-00847/run"  │
│  ip_address:       "10.0.3.47"            ← source IP        │
│                                                              │
│  created_at:       "2024-03-14T15:47:23Z" ← immutable        │
│  raw_event:        { ... full EventKind JSON ... }           │
└─────────────────────────────────────────────────────────────┘
```

### Actor Attribution Logic

```
Event type                    → actor_id               → actor_type
─────────────────────────────────────────────────────────────────────
ApprovalReceived              → event.user_id           → Human
NodeStarted                   → event.worker_id         → System
PolicyViolation               → request context         → System
ToolApprovalRequired          → request context         → System
Any event via API             → API token name           → Human
Any event from scheduler      → "scheduler-main"        → System
Any event from agent          → agent_ref               → Agent
```

### Append-Only Guarantee

The `SqliteAuditBackend` implementation:
- Uses `INSERT OR IGNORE` — idempotent on the entry ID
- Has **no UPDATE or DELETE methods** — not in the trait, not in the implementation
- The Rust compiler enforces this — `AuditBackend` trait only exposes `append()`, `query()`, `count()`

```rust
// The ONLY write method. No update(). No delete(). Ever.
async fn append(&self, entry: AuditLogEntry) -> Result<(), AuditError>;
```

## Run It

```bash
jamjet dev &

# Run a loan application
jamjet run workflow.yaml --input '{
  "applicant_name": "Jane Smith",
  "loan_amount": 750000,
  "loan_purpose": "commercial real estate",
  "credit_score": 720
}'

# When the loan officer reviews:
jamjet resume <exec-id> --event loan_approved --data '{"approved": true}'

# View the audit trail
curl http://localhost:7700/audit?execution_id=<exec-id>

# Filter by policy violations
curl http://localhost:7700/audit?event_type=policy_violation

# Filter by actor
curl http://localhost:7700/audit?actor_id=loan-officer-jsmith
```

## What It Does

1. **Credit Analysis** — Agent analyzes applicant's credit history
2. **Policy Check** — If the agent tries to delete/export data, it's blocked and logged
3. **Risk Scoring** — Compute risk score based on credit, loan amount, purpose
4. **Loan Decision** — Agent recommends approve/deny; large loans require human approval
5. **Human Review** — Loan officer approves/rejects via API
6. **Audit Trail** — Every step is recorded with full actor attribution and HTTP context

## Key Concepts

| Concept | How it works |
|---------|-------------|
| **Immutable entries** | `INSERT OR IGNORE` only. No UPDATE/DELETE in the backend trait. |
| **Actor attribution** | `actor_id` + `actor_type` (Human/Agent/System) derived from event context |
| **Tool call hash** | SHA-256 of `tool_name:input_json` — detects replay attacks |
| **HTTP correlation** | `request_id`, `method`, `path`, `ip_address` from API middleware |
| **Policy decision** | `"allow"`, `"blocked"`, `"require_approval"` — logged for compliance |
| **Pagination** | `limit` + `offset` + `count` for large audit trails |
| **Idempotent appends** | Crash replay safety — same entry ID won't create duplicates |

## Compliance Queries

### Weekly SOC2 Report
```bash
# All policy violations this week
curl "http://localhost:7700/audit?event_type=policy_violation&limit=100"

# All human approvals
curl "http://localhost:7700/audit?event_type=approval_received"

# Activity by a specific user
curl "http://localhost:7700/audit?actor_id=loan-officer-jsmith"
```

### Incident Investigation
```bash
# Everything that happened in a specific execution
curl "http://localhost:7700/audit?execution_id=LOAN-2024-00847"

# Cross-reference with API gateway using request_id
# (look up req-abc123 in your API gateway logs)
```

## Python Equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Adapting It

- **Export to SIEM**: Implement `AuditBackend` for your SIEM (Splunk, Datadog, etc.)
- **Custom actor attribution**: Override `derive_actor_id()` for your auth system
- **Retention policy**: The audit log is independent — keep it for 7 years while
  pruning workflow events monthly
- **Real-time alerts**: Subscribe to `policy_violation` events for immediate notification

## Further Reading

- [DESIGN.md](./DESIGN.md) — Audit log architecture, append-only guarantees, SIEM integration patterns
- [Audit Tests](https://github.com/jamjet-labs/jamjet/tree/main/runtime/audit/tests/compliance_audit.rs) — 9 Rust integration tests modeling this exact scenario
