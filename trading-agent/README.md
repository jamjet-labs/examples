# Trading Agent — Autonomy Enforcement

A quantitative hedge fund's pre-trade research pipeline that demonstrates **JamJet's autonomy
enforcement** — three AI agents with different autonomy levels, budget-aware iteration limits,
and a circuit breaker that prevents error-loop catastrophes.

```
Market opens at 9:30am
         |
         v
  Research Agent              autonomy: bounded_autonomous
  (SEC filings, news)         max_iterations: 10, cost: $2, tokens: 100k
         |                    -> escalate if ANY limit hit
    +----+----+
    |         |
    v         v
 Filing     News              (parallel research)
 Analysis   Sentiment
    |         |
    +----+----+
         |
         v
  Risk Agent                  autonomy: bounded_autonomous
  (position sizing)           max_iterations: 5
         |
         v
  Execution Agent             autonomy: guided
  (order submission)          EVERY action requires trader approval
         |
         v
  Trader clicks /approve      (human gate — no exceptions)
         |
         v
  Order submitted to broker
         |
         |  503 error?
         v
  Circuit Breaker             3 consecutive errors → STOP
  (prevents order storms)     alert operations team
```

## The Problem This Solves

Without autonomy enforcement, real disasters happen:

### 1. Runaway Research ($47 overnight)
The research agent was analyzing SEC filings for a patent case. It kept "finding one more
relevant document" in an infinite loop. By morning: **4.7M tokens consumed, $47 in LLM costs**
on a single analysis that should have cost $2.

**JamJet's fix**: `bounded_autonomous` mode with `cost_budget_usd: 2.0`. At $2.01, the agent
escalates to the analyst instead of continuing.

### 2. Unauthorized Trades ($3M loss)
A competitor's execution agent placed live market orders without human approval. A configuration
error caused it to short-sell 10x the intended position. The error was discovered 4 hours later.

**JamJet's fix**: `guided` mode for the execution agent. Every single tool call — buy, sell,
cancel — requires explicit human approval via `/approve`.

### 3. Order Storm (200+ duplicate orders)
The broker API returned 503 errors. The execution agent retried 200+ times, each with slightly
different parameters. The broker interpreted each retry as a new order. Result: 200+ duplicate
positions opened when the API recovered.

**JamJet's fix**: Circuit breaker trips after 3 consecutive errors. Agent STOPS. Operations
team is alerted. No further API calls until a human resets.

## How Autonomy Enforcement Works

### Three Autonomy Levels

| Level | What it means | When to use |
|-------|--------------|-------------|
| `fully_autonomous` | Only the circuit breaker can stop the agent | 24/7 data ingestion, monitoring |
| `bounded_autonomous` | Enforces iteration, cost, token, and time limits | Research, analysis, planning |
| `guided` | Every tool call requires human approval | Trade execution, fund transfers, deletions |

### Decision Flow

```
Agent wants to execute a tool call
         │
         v
┌──────────────────────┐     ┌──────────────────────────┐
│ Circuit Breaker      │────>│ STOP: 3 consecutive      │
│ (ALL autonomy levels)│ Yes │ errors. Alert ops team.   │
│ consecutive_errors   │     │ No further calls.         │
│ >= threshold?        │     └──────────────────────────┘
└────────┬─────────────┘
         │ No
         v
┌──────────────────────┐     ┌──────────────────────────┐
│ Autonomy Level?      │     │                          │
│                      │     │                          │
│ guided ─────────────────>  │ PAUSE: require human     │
│                      │     │ approval for this call   │
│                      │     └──────────────────────────┘
│                      │
│ bounded_autonomous ──┐     ┌──────────────────────────┐
│                      ├───> │ CHECK: iterations, cost, │
│                      │     │ tokens, time limits      │
│                      │     │ Any exceeded? ESCALATE   │
│                      │     └──────────────────────────┘
│                      │
│ fully_autonomous ───────>  │ PROCEED: no limits       │
│                      │     │ (only circuit breaker)   │
└──────────────────────┘     └──────────────────────────┘
```

### Priority Order

The circuit breaker fires **before** checking autonomy levels. This is intentional — even a
`fully_autonomous` agent that encounters 3 consecutive errors should stop. Safety first.

## Run It

```bash
jamjet dev &

# Run the pre-trade research pipeline
jamjet run workflow.yaml --input '{
  "ticker": "NVDA",
  "analysis_type": "10-K filing deep analysis",
  "position_size_usd": 500000
}'

# When the execution agent wants to place an order:
jamjet resume <exec-id> --event trader_approved --data '{"approved": true}'
```

### Try Triggering an Escalation

```bash
# This will hit the iteration limit — 10 iterations for a complex portfolio
jamjet run workflow.yaml --input '{
  "ticker": "NVDA,AAPL,MSFT,GOOG,AMZN,META,TSLA,BRK.B,JPM,V",
  "analysis_type": "full portfolio analysis (50 patents each)",
  "position_size_usd": 10000000
}'
```

## What It Does

1. **Research Agent** (`bounded_autonomous`) — Scans SEC filings, news, social sentiment.
   Limited to 10 iterations, $2 cost, 100k tokens, 5-minute timeout. Escalates if any
   limit is hit.

2. **Risk Agent** (`bounded_autonomous`) — Validates position sizes against portfolio risk
   limits. Checks leverage, concentration, correlation. Limited to 5 iterations.

3. **Execution Agent** (`guided`) — Submits orders to the broker API. **Every call** requires
   a trader's explicit approval. Even cancellations need approval (a rogue cancel removed
   a hedging position once).

4. **Circuit Breaker** — If the broker API goes down and the agent hits 3 consecutive errors,
   execution stops immediately. Operations team is alerted.

## Key Concepts

| Concept | How it works |
|---------|-------------|
| **Bounded autonomous** | Agent iterates freely within limits (iterations, cost, tokens, time) |
| **Guided mode** | Every tool call pauses for human approval — no autonomous actions |
| **Circuit breaker** | N consecutive errors → agent stops. Prevents retry storms |
| **Escalation** | When a limit is hit, the system notifies the right person (analyst, trader, ops) |
| **Budget state persistence** | Budget survives crashes — embedded in execution snapshots |

## Python Equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Adapting It

- **Adjust iteration limits**: `max_iterations: 10` in the agent's `autonomy_constraints`
- **Change cost budgets**: `cost_budget_usd: 2.0` to allow more/less spend per analysis
- **Add tool restrictions**: Use `allowed_tools` to whitelist specific tools per agent
- **Change circuit breaker threshold**: `circuit_breaker_threshold: 5` for more tolerance

## Further Reading

- [DESIGN.md](./DESIGN.md) — Why three autonomy levels, circuit breaker math, real incident analysis
- [Autonomy Tests](https://github.com/jamjet-labs/jamjet/tree/main/runtime/policy/tests/trading_agent_autonomy.rs) — 9 Rust integration tests modeling this exact scenario
