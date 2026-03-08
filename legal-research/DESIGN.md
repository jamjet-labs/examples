# Legal Research — Design Deep Dive

## Why Per-Case Budgets?

Law firms bill by the hour. AI costs are overhead — they don't generate revenue directly.
The managing partner needs to know: "What is the maximum AI cost per case?"

Without budgets:
- Individual cases look cheap ($2-5 each)
- But outliers spike to $120+ (the patent case incident)
- Monthly aggregate is unpredictable ($1.2k one month, $9.6k the next)
- No way to quote clients on AI research costs

With JamJet budgets:
- Every case costs at most $15 in AI
- Monthly budget = $15 x case count (predictable)
- Outliers are caught at $15, not $120
- The firm can include AI costs in client quotes

## Budget Accumulation Model

```
┌───────────────────────────────────────────────────────────────┐
│                    Budget Accumulation                        │
│                                                               │
│  Call 1: Summarize          2k in +  1k out + $0.003          │
│  Call 2: Search precedents  5k in +  3k out + $0.008          │
│  Call 3: Analyze case 1     8k in +  4k out + $0.012          │
│  Call 4: Analyze case 2    12k in +  6k out + $0.018          │
│  Call 5: Draft memo        15k in +  8k out + $0.023          │
│  ──────────────────────────────────────────────────────        │
│  TOTAL:                    42k in + 22k out + $0.064          │
│                                                               │
│  total_tokens() = 42k + 22k = 64k                            │
│                                                               │
│  Budget check: 64k / 500k tokens → OK (12.8% used)           │
│  Budget check: $0.064 / $15.00 → OK (0.4% used)              │
│                                                               │
│  Conclusion: Simple 5-call workflow is well within budget.    │
│  The budget exists for cases where the agent loops.           │
└───────────────────────────────────────────────────────────────┘
```

## When Budgets Actually Fire

Budgets rarely fire on well-behaved workflows. They exist for the edge cases:

### Scenario 1: Patent Portfolio (50 patents)
```
Each patent: ~16k tokens (10k in + 6k out)
After 30 patents: 480k tokens → approaching 500k limit
Patent 31: 505k tokens → BUDGET EXCEEDED
    → Execution pauses
    → Paralegal reviews 30 completed analyses
    → Decides: finish remaining 20 manually, or increase budget
```

### Scenario 2: Expensive Model + Long Context
```
Using claude-opus for deep analysis: ~$0.50 per call
After 30 calls: $15.00 → exactly at limit
Call 31: $15.50 → COST EXCEEDED
    → Even though tokens are only at 200k (below 500k limit)
    → Cost hit first because the model is expensive
    → This is why multi-dimension checks matter
```

### Scenario 3: Output-Heavy Memo Drafting
```
Agent drafts very long memos: 3k input, 8k output per call
After 50 calls: 150k input (OK) but 400k output (exceeds 300k limit!)
    → Output tokens exceeded before total or cost
    → Each dimension is checked independently
```

## Snapshot Persistence: The `__budget` Key

BudgetState is serialized as a JSON object under the `__budget` key in the execution
snapshot state. This is a deliberate design choice:

### Why Not a Separate Database Table?

| Approach | Pros | Cons |
|----------|------|------|
| Separate table | Clean schema, easy querying | Requires migration, sync issues with snapshot |
| Embedded in snapshot | Zero migration, crash-resilient by design, atomic with snapshot | Slightly more complex parsing |

We chose embedded because:
1. **Atomicity**: BudgetState is always consistent with the execution state
2. **No migration**: New field in existing JSON — backward compatible via `serde(default)`
3. **Crash resilience**: Snapshot is already the crash recovery mechanism
4. **Simplicity**: One fewer table to manage, index, and query

### Snapshot Layout

```json
{
  "case_id": "PATENT-2024-0847",
  "complaint_summary": "...",
  "precedents": ["..."],
  "analyses": ["..."],
  "__budget": {
    "total_input_tokens": 120000,
    "total_output_tokens": 60000,
    "total_cost_usd": 0.18,
    "iteration_count": 15,
    "tool_call_count": 8,
    "consecutive_error_count": 0,
    "circuit_breaker_tripped": false
  }
}
```

The `__budget` prefix (double underscore) signals that this is runtime metadata, not
business data. Application code should never read or write this key directly.

## Cost Model: Understanding What You're Paying For

### Token Cost Breakdown (Claude Sonnet)

| Operation | Input tokens | Output tokens | Estimated cost |
|-----------|-------------|---------------|----------------|
| Summarize complaint | 2,000 | 1,000 | $0.003 |
| Search precedents | 5,000 | 3,000 | $0.008 |
| Analyze 1 case | 8,000 | 4,000 | $0.012 |
| Analyze 10 cases | 80,000 | 40,000 | $0.120 |
| Draft memo | 15,000 | 8,000 | $0.023 |
| **Typical case total** | **110,000** | **56,000** | **$0.166** |
| **Worst case (50 patents)** | **420,000** | **180,000** | **$0.600** |

At these prices, the $15 budget allows roughly **90 typical cases** or **25 complex
portfolio reviews**. The budget is generous by design — it catches runaway loops, not
normal usage.

### When Does a $15 Budget Actually Get Hit?

Only in pathological cases:
- Agent loops: "Let me search for one more precedent" x 1000
- Recursive analysis: "Let me re-analyze this case with more context" x 100
- Context inflation: Each iteration includes all previous results, growing the prompt

These are exactly the scenarios the budget prevents.

## Production Considerations

### 1. Budget Alerts Before Limits
In production, emit a warning event at 80% budget consumption. This gives the team
time to investigate before execution pauses:

```yaml
budget_alerts:
  - at: 0.8    # 80% of any budget dimension
    action: warn
  - at: 1.0    # 100%
    action: pause
```

### 2. Per-Client Budget Overrides
Different clients may have different budgets. The workflow's `cost_budget_usd` can be
overridden at execution time via input parameters or client configuration.

### 3. Budget Reporting
The audit log captures every `TokenBudgetExceeded` and `CostBudgetExceeded` event.
The finance team can generate monthly reports: "Show me all executions that exceeded
80% of their budget."

### 4. Model Selection and Cost
The workflow uses Haiku for simple steps (summarize, budget summary) and Sonnet for
complex steps (analysis, memo drafting). This is intentional cost optimization —
Haiku is ~10x cheaper than Sonnet for equivalent token counts.
