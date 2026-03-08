# Trading Agent — Design Deep Dive

## Why Three Autonomy Levels?

Not all agents are created equal. A data ingestion agent that streams market prices 24/7
has very different trust requirements than an agent that places live orders. Autonomy levels
encode this trust gradient:

```
Trust Level      Low ◄────────────────────────────────► High

Autonomy Level   guided          bounded_autonomous      fully_autonomous

What's gated     EVERY tool      Only when limits        Nothing (except
                 call            are exceeded            circuit breaker)

Use cases        Trade execution Research, analysis,     Data feeds,
                 Fund transfers  planning, drafting      monitoring
                 Record deletion
```

### Why Not Just Use "guided" for Everything?

Because it kills throughput. A research agent making 50 tool calls per analysis would
require 50 human approvals. At 30 seconds per approval, that's 25 minutes of human time
for a task that should take 2 minutes. `bounded_autonomous` lets the agent work freely
within a safety box.

### Why Not Just Use "fully_autonomous" for Everything?

Because one bug costs millions. The March 2025 order storm at a competitor created 200+
duplicate orders because the agent retried indefinitely. `bounded_autonomous` and `guided`
prevent this class of errors entirely.

## Circuit Breaker: The Universal Safety Net

The circuit breaker is the **only** control that applies to ALL autonomy levels, including
`fully_autonomous`. It fires when consecutive errors reach a threshold.

### Why Consecutive (Not Total) Errors?

A research agent that makes 50 calls, 5 of which fail, is probably fine — the API was
briefly flaky. But 3 errors **in a row** means the service is down, and continuing will:

1. Waste money on calls that will fail
2. Hit rate limits that extend the outage
3. Potentially create duplicate requests when the service recovers

### The Math of Error Storms

Without a circuit breaker (real incident from March 2025):

```
t=0:00   Agent retries failed order → 503
t=0:01   Agent retries with modified params → 503
t=0:02   Agent retries with different params → 503
...
t=2:00   Agent has sent 200+ requests with unique params
t=2:01   Broker API recovers
t=2:02   All 200+ requests execute simultaneously
t=2:03   Account has 200x intended position
t=2:04   $3M loss before anyone notices
```

With JamJet's circuit breaker:

```
t=0:00   Agent retries failed order → 503 (error 1/3)
t=0:01   Agent retries → 503 (error 2/3)
t=0:02   Agent retries → 503 (error 3/3)
t=0:03   CIRCUIT BREAKER TRIPS → Agent STOPS
t=0:03   Operations team alerted via webhook
t=0:10   Human investigates, confirms broker is down
t=0:45   Broker recovers
t=0:46   Human resets circuit breaker via /approve
t=0:47   Agent resumes with a single clean order
```

**Cost of circuit breaker**: 0 (one microsecond check per iteration).
**Cost of not having one**: $3M+ in this real incident.

## Budget State Persistence

Budget state (tokens consumed, cost accumulated, iteration count) is embedded in the
execution snapshot under the `__budget` key. This means:

```
Worker starts analysis
  │
  ├── Iteration 1: 10k tokens, $0.15
  ├── Iteration 2: 8k tokens, $0.12
  ├── ...
  ├── Iteration 14: 6k tokens, $0.09
  ├── Snapshot saved: { __budget: { total_tokens: 95000, cost: $1.82, ... } }
  │
  ╳ Worker crashes (OOM on 200-page contract)
  │
  ├── Worker restarts
  ├── Loads snapshot → BudgetState recovered
  ├── total_tokens: 95000, cost: $1.82
  ├── Iteration 15: 8k tokens, $0.12 → total now $1.94
  ├── Iteration 16: 7k tokens, $0.11 → total now $2.05
  │
  └── ESCALATE: cost $2.05 > budget $2.00
```

Without crash-resilient budgets, the agent would reset to $0.00 after the crash and
potentially consume another $2.00 — **doubling the cost**.

## Escalation Targets

When a bounded_autonomous agent hits a limit, the system needs to know **who** to escalate to:

| Limit hit | Escalation target | Why |
|-----------|-------------------|-----|
| `max_iterations` | Analyst (human) | Agent needs guidance on next steps |
| `cost_budget_usd` | Operations team | Cost control — may need to increase budget |
| `token_budget` | Analyst + ops | Could indicate prompt engineering issue |
| `time_budget_secs` | Operations team | Could indicate infrastructure problem |
| Circuit breaker | Operations team | Service-level issue, not agent logic |

The escalation target is configurable per agent. In this example, the research agent
escalates to the analyst desk, while the execution agent escalates to the trading desk.

## Production Considerations

### 1. Autonomy Levels per Environment
Use stricter autonomy in production than in development:

```yaml
# dev
autonomy:
  level: bounded_autonomous
  constraints:
    max_iterations: 100  # generous for testing

# prod
autonomy:
  level: bounded_autonomous
  constraints:
    max_iterations: 10   # strict for safety
```

### 2. Circuit Breaker Reset
The circuit breaker stays tripped until a human resets it via the `/approve` endpoint.
This is intentional — automatic reset could re-trigger the error storm.

### 3. Cost Tracking Across Model Providers
The budget tracks cost in USD regardless of the model provider. If you switch from
Claude to GPT mid-workflow, the budget correctly accumulates costs from both.

### 4. Concurrent Agent Budgets
Each agent has its own budget within the workflow's overall budget. The workflow-level
budget is the hard cap; individual agent budgets are enforcement points within that cap.
