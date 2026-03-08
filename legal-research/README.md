# Legal Research — Token & Cost Budget Enforcement

A law firm's AI research assistant that demonstrates **JamJet's token and cost budget
enforcement** — preventing runaway LLM costs, enforcing per-case spending caps, and
surviving worker crashes without losing budget state.

```
Managing partner assigns case
         |
         v
  Complaint Summary             budget: 500k tokens / $15 per case
  (2k in, 1k out, $0.003)       ────────────────────────────────────
         |                       Running total tracked in BudgetState
         v                       embedded in execution snapshot
  Precedent Search
  (5k in, 3k out, $0.008)       At any point:
         |                       - token limit hit → PAUSE
    +----+----+                  - cost limit hit  → PAUSE
    |         |                  - crash occurs     → budget state
    v         v                    survives in snapshot
 Case 1    Case 2
 Analysis  Analysis              Human paralegal takes over
 (8k in)   (12k in)             when budget is exceeded
    |         |
    +----+----+
         |
         v
  Draft Comparative Memo
  (15k in, 8k out, $0.023)
         |
         v
  Budget check: 64k / 500k tokens
                $0.064 / $15.00
  Status: WITHIN BUDGET
```

## The Problem This Solves

### 1. The $120 Patent Case
A single complex patent case consumed **4.7 million tokens ($120)** when the research agent
kept "finding one more relevant precedent" in an infinite loop. The case was worth $2,000.
The AI cost 6% of the case value in a single research session.

**JamJet's fix**: Hard token budget of 500k per case. At 500,001 tokens → execution pauses,
paralegal takes over.

### 2. The 8x Monthly Spend Spike
Without per-case cost caps, monthly AI spend spiked from $1,200 to $9,600 before the
managing partner noticed on the credit card statement. Individual cases looked reasonable —
it was the aggregate that was alarming.

**JamJet's fix**: Per-case cost budget of $15. The firm now knows the maximum AI cost per
case upfront. Monthly budget = $15 x expected case count.

### 3. The Budget Reset After Crash
A worker crashed (OOM on a 200-page contract) after consuming 180k tokens. When the worker
restarted, the budget counter reset to zero. The agent consumed another 400k tokens before
being stopped — effectively bypassing the 500k limit.

**JamJet's fix**: BudgetState is embedded in the execution snapshot. After crash recovery,
the budget picks up at 180k — not zero.

## How Token & Cost Budgets Work

### BudgetState Accumulator

Every time the agent makes an LLM call, the runtime accumulates usage:

```
┌──────────────────────────────────────────────────────┐
│                   BudgetState                        │
│                                                      │
│  total_input_tokens:   42,000     ◄── accumulated    │
│  total_output_tokens:  22,000         across all     │
│  total_cost_usd:       $0.064         LLM calls      │
│  iteration_count:      5                             │
│  tool_call_count:      12                            │
│  consecutive_errors:   0                             │
│  circuit_breaker:      false                         │
│                                                      │
│  total_tokens() → 64,000                             │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │ Embedded in snapshot as "__budget" key   │        │
│  │ Survives crash, restart, reschedule     │        │
│  └──────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────┘
```

### Multi-Dimension Budget Checks

The runtime checks **all** budget dimensions after every node execution:

```
After node completes:
         │
    ┌────┴────────────────────────────┐
    │ Check input token budget        │ 42k / 500k → OK
    ├─────────────────────────────────┤
    │ Check output token budget       │ 22k / 300k → OK
    ├─────────────────────────────────┤
    │ Check total token budget        │ 64k / 500k → OK
    ├─────────────────────────────────┤
    │ Check cost budget               │ $0.064 / $15 → OK
    └────┬────────────────────────────┘
         │
         v
    All OK → continue execution
    Any exceeded → PAUSE + emit event + alert
```

The **first** limit hit determines the action. Output tokens might exceed before input tokens
(e.g., the agent writes long memos). Cost might exceed before tokens (e.g., using an expensive
model). Each dimension is independent.

### Crash Recovery

```
     Normal execution
         │
    ┌────┴────┐
    │ Call 1  │ +12k tokens, $0.018
    │ Call 2  │ +16k tokens, $0.024
    │  ...    │
    │ Call 14 │ +8k tokens, $0.012
    └────┬────┘
         │
    Snapshot saved: { "__budget": { total_tokens: 175000, cost: $1.75, ... } }
         │
    ╳ CRASH (OOM)
         │
    ┌────┴────┐
    │ Restart │ Load snapshot → BudgetState recovered
    │         │ total_tokens: 175,000 (not zero!)
    │ Call 15 │ +8k tokens → 183,000
    │ Call 16 │ +10k tokens → 193,000
    │  ...    │
    └────┬────┘
         │
    Budget correctly tracks ALL usage, even across crashes
```

## Run It

```bash
jamjet dev &

# Run a legal research workflow
jamjet run workflow.yaml --input '{
  "case_id": "PATENT-2024-0847",
  "case_description": "Patent infringement claim: AI-generated code violating software patent",
  "jurisdiction": "US Federal, Northern District of California",
  "max_precedents": 10
}'

# Monitor budget consumption
jamjet inspect <exec-id>
```

### Try Exceeding the Budget

```bash
# This will hit the token budget — analyzing 50 patents at ~16k tokens each
jamjet run workflow.yaml --input '{
  "case_id": "PORTFOLIO-2024-001",
  "case_description": "Full patent portfolio review: 50 patents in semiconductor IP",
  "jurisdiction": "US Federal, multiple districts",
  "max_precedents": 50
}'
```

## What It Does

1. **Summarize Complaint** — Quick summary of the case filing (2k tokens)
2. **Search Precedents** — Find relevant case law (5k tokens)
3. **Analyze Each Precedent** — Deep analysis of each case (8-15k tokens each)
4. **Draft Comparative Memo** — Synthesize all findings (15k tokens)
5. **Budget Check** — After each step, verify tokens and cost are within limits

## Key Concepts

| Concept | How it works |
|---------|-------------|
| **Token budget** | `token_budget: { total_tokens: 500000 }` — hard cap on total tokens |
| **Cost budget** | `cost_budget_usd: 15.0` — hard cap on USD cost |
| **Multi-dimension** | Input, output, total tokens, AND cost — each checked independently |
| **Crash resilience** | BudgetState embedded in snapshot under `__budget` key |
| **on_budget_exceeded** | `pause` (default), `cancel`, or `escalate` |

## Python Equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Adapting It

- **Increase token budget**: `token_budget: { total_tokens: 1000000 }` for complex cases
- **Adjust cost cap**: `cost_budget_usd: 25.0` for cases that need more analysis
- **Per-dimension limits**: `token_budget: { input_tokens: 300000, output_tokens: 200000 }`
- **Change exceeded behavior**: `on_budget_exceeded: cancel` to terminate instead of pause

## Further Reading

- [DESIGN.md](./DESIGN.md) — Budget accumulation internals, snapshot persistence, cost model analysis
- [Budget Tests](https://github.com/jamjet-labs/jamjet/tree/main/runtime/state/tests/research_budget.rs) — 6 Rust integration tests modeling this exact scenario
