# Healthcare Compliance — Design Deep Dive

## Why a Policy Engine?

Healthcare AI systems operate under strict regulatory requirements (HIPAA, FDA, state medical
board regulations). A policy engine provides **defense in depth** — even if the application code
has a bug, the runtime prevents dangerous actions.

### Defense Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Application Code                                  │
│  The developer writes safe prompts and logic.               │
│  BUT: LLMs hallucinate. Developers make mistakes.           │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: JamJet Policy Engine (THIS LAYER)                 │
│  Runtime enforces rules regardless of what the LLM outputs. │
│  Tool blocking, approval gates, model allowlists.           │
│  Cannot be bypassed by application code.                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Infrastructure Controls                           │
│  Network segmentation, IAM roles, database permissions.     │
│  Catches anything that slips through Layers 1-2.            │
└─────────────────────────────────────────────────────────────┘
```

The policy engine is Layer 2 — it's the **runtime safety net** that catches:
- LLM hallucinations (generating tool calls that shouldn't exist)
- Developer misconfigurations (using the wrong model)
- Scope creep (intake workflow touching billing systems)

## Architecture: Three-Layer Policy Hierarchy

```
         ┌─────────────────────────────────────────┐
         │           POLICY EVALUATION              │
         │                                          │
         │  Node policy      ← checked FIRST        │
         │      │                                   │
         │      v                                   │
         │  Workflow policy  ← checked SECOND       │
         │      │                                   │
         │      v                                   │
         │  Global policy    ← checked LAST         │
         │      │                                   │
         │      v                                   │
         │  No match → ALLOW                        │
         └─────────────────────────────────────────┘
```

The first matching rule wins. This means:
- A **node-level** rule overrides workflow and global rules
- A **workflow-level** rule overrides global rules
- If **no rule matches**, the action is allowed (open by default)

### Why This Order Matters

Consider the triage node. It needs `ft-triage-v3` — a fine-tuned model that isn't in the
global allowlist. Without node-level override:

```
Global allowlist: [claude-sonnet-4-6, claude-haiku-4-5-20251001]
ft-triage-v3 → NOT in allowlist → BLOCKED
```

With node-level override:

```
Node allowlist: [claude-sonnet-4-6, ft-triage-v3]
ft-triage-v3 → in node allowlist → ALLOWED (stops checking here)
```

The same model at a different node (e.g., discharge summary) is still blocked:

```
No node policy → check workflow → check global
Global allowlist: [claude-sonnet-4-6, claude-haiku-4-5-20251001]
ft-triage-v3 → NOT in global allowlist → BLOCKED
```

## Glob Pattern Matching

The policy engine uses a minimal glob matcher supporting `*` (any characters) and `?`
(single character). This is critical for forward-compatibility:

### Why Wildcards?

A hospital with 200+ microservices deploys new tools weekly. Without wildcards:

```yaml
blocked_tools:
  - delete_patient_record
  - delete_appointment
  - delete_lab_result
  - delete_insurance_record
  # ... maintainer forgets to add delete_imaging_scan
  # → HIPAA violation when the agent calls it
```

With wildcards:

```yaml
blocked_tools:
  - "delete_*"    # catches ALL current and future delete_ tools
```

### Pattern Examples

| Pattern | Input | Match? | Why |
|---------|-------|--------|-----|
| `delete_*` | `delete_patient_record` | Yes | `*` matches `patient_record` |
| `delete_*` | `remove_patient_record` | No | Doesn't start with `delete_` |
| `order_lab_*` | `order_lab_cbc` | Yes | `*` matches `cbc` |
| `order_lab_*` | `order_medication` | No | Doesn't start with `order_lab_` |
| `claude-*` | `claude-sonnet-4-6` | Yes | `*` matches `sonnet-4-6` |
| `model-v?` | `model-v3` | Yes | `?` matches single char `3` |
| `model-v?` | `model-v12` | No | `?` matches exactly one char |

## Runtime Enforcement Flow

```
Node scheduled for execution
         │
         v
┌──────────────────┐
│ Load policy sets │  (global + workflow + node)
│ from workflow IR │
└────────┬─────────┘
         │
         v
┌──────────────────┐     ┌─────────────────────┐
│ Model allowlist  │────>│ BLOCK: model 'gpt-4o'│
│ check            │ No  │ not in allowlist     │
└────────┬─────────┘     └─────────────────────┘
         │ Yes
         v
┌──────────────────┐     ┌─────────────────────┐
│ Blocked tools    │────>│ BLOCK: tool matches  │
│ check (glob)     │ Yes │ 'delete_*' pattern   │
└────────┬─────────┘     └─────────────────────┘
         │ No
         v
┌──────────────────┐     ┌─────────────────────────┐
│ Require approval │────>│ PAUSE: prescribe_med     │
│ check (glob)     │ Yes │ awaiting pharmacist      │
└────────┬─────────┘     └─────────────────────────┘
         │ No
         v
     ALLOW — execute normally
```

## Cost and Performance

Policy evaluation adds **< 1 microsecond** per node execution. The glob matcher operates
on ASCII byte sequences with no heap allocation for patterns under 64 characters. This is
negligible compared to the 100ms–30s that a typical LLM call takes.

## Production Considerations

### 1. Policy Versioning
Policy sets are embedded in the workflow IR. When you update a policy, you create a new
workflow version. Old executions continue with the policy they started with — no mid-flight
policy changes that could cause inconsistency.

### 2. Audit Trail
Every policy decision (allow, block, require_approval) is logged as an event in the audit
log. The compliance team can query: "show me all blocked tool calls in the last 30 days."

### 3. Testing Policies
The Rust integration tests (`runtime/policy/tests/healthcare_workflow.rs`) validate all 9
policy scenarios in this workflow. Run them with:

```bash
cargo test -p jamjet-policy --test healthcare_workflow
```

### 4. Incident Response
When a policy blocks a tool call, the event includes:
- Which tool was blocked
- Which pattern matched
- Which policy layer (global/workflow/node)
- The node and execution context

This gives the incident response team everything they need without debugging application code.
