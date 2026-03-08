# Due Diligence — Multi-Agent A2A Example

A network of specialized AI agents that collaborate via the **A2A protocol** to produce
a full investment due diligence report from a single company name.

```
VC Analyst types "Anthropic"
         │
         ▼
   Orchestrator (run.py)
         │
    ┌────┴────┐
    │         │   (parallel)
    ▼         ▼
Financial   Market        ← RAG over knowledge base
 Agent      Agent
  7701       7702
    │         │
    └────┬────┘
         │
         ▼
      Risk Agent          ← Synthesizes everything
        7703
         │
         ▼
  Full Due Diligence Report
  (Financial + Market + Risk Score + Recommendation)
```

## Quick Start

```bash
# 1. Install dependencies
pip install aiohttp openai

# 2. Configure environment
cp .env.example .env
# Edit .env: set OPENAI_API_KEY and (optionally) COMPANY

# 3. Run the full due diligence pipeline
python run.py Anthropic

# Or: run benchmark with full metrics table
python benchmark.py Anthropic

# Supported companies (in the knowledge base): Anthropic, OpenAI, Mistral AI
```

## What Each Agent Does

| Agent | Port | Skill | Method |
|-------|------|-------|--------|
| **Financial Research Agent** | 7701 | `analyze_financials` | RAG over `knowledge/financials.md` |
| **Market Intelligence Agent** | 7702 | `analyze_market` | RAG over `knowledge/markets.md` |
| **Risk Assessment Agent** | 7703 | `assess_risk` | LLM synthesis of financial + market outputs |

### Financial Research Agent (`agents/financial.py`)
Implements RAG over `knowledge/financials.md`. For each query it:
1. Chunks the knowledge base by `##` section heading
2. Scores chunks by keyword overlap with the query
3. Retrieves the top-3 most relevant chunks
4. Passes retrieved context to the LLM with a financial analyst system prompt
5. Returns a structured analysis: revenue, margins, funding, unit economics, risks

### Market Intelligence Agent (`agents/market.py`)
Identical RAG pipeline, but over `knowledge/markets.md`. Produces:
competitive landscape, market sizing, moats, strategic risks.

### Risk Assessment Agent (`agents/risk.py`)
No RAG — receives the combined financial + market analysis from the orchestrator
and applies a 6-dimension risk scoring rubric:
- Financial Health (25%) · Market Position (20%) · Execution Risk (20%)
- Regulatory Risk (15%) · Technology Risk (10%) · Capital Risk (10%)

Outputs: risk scorecard table, composite score (1–5), rating (LOW/MEDIUM/HIGH/VERY HIGH),
investment recommendation, conditions for investment, confidence level.

### Orchestrator (`orchestrator.py`)
Discovers all agents via Agent Cards, coordinates the workflow:
- Phase 1: Fetch all 3 Agent Cards in parallel (discovery)
- Phase 2: Submit to Financial + Market agents simultaneously
- Phase 3: Poll both agents concurrently (max parallel speedup)
- Phase 4: Send combined outputs to Risk agent
- Phase 5: Compose final report

## A2A Protocol

Each agent exposes three endpoints:

```
GET  /.well-known/agent.json  →  Agent Card (discovery)
POST /a2a/tasks               →  Submit task { skill_id, input }
GET  /a2a/tasks/{id}          →  Poll for result
```

The orchestrator uses **only these three endpoints** — it has no Python imports
from the agent modules. You could replace any agent with a third-party service
that speaks A2A and the orchestrator wouldn't change.

### Swapping an Agent

To replace the Market Agent with a third-party A2A-compatible market intelligence service:

1. Update `AGENT_URLS["market"]` in `orchestrator.py` to the third-party URL
2. Verify it serves a valid Agent Card with the `analyze_market` skill
3. Run again — the orchestrator discovers and uses it automatically

No code changes needed in other agents or the report composition logic.

### Running Agents as Separate Services

For production deployment, start each agent independently:

```bash
# Terminal 1
python -c "from agents import FinancialAgent; FinancialAgent().run()"

# Terminal 2
python -c "from agents import MarketAgent; MarketAgent().run()"

# Terminal 3
python -c "from agents import RiskAgent; RiskAgent().run()"

# Terminal 4 — orchestrate
python orchestrator.py Anthropic
```

## Using a Different LLM Provider

This example uses the OpenAI SDK, which is compatible with many providers:

**Vertex AI (Gemini):**
```
OPENAI_BASE_URL=https://us-central1-aiplatform.googleapis.com/v1beta1/projects/YOUR_PROJECT/locations/us-central1/endpoints/openapi
OPENAI_API_KEY=<gcloud auth print-access-token>
OPENAI_MODEL=google/gemini-2.0-flash-001
```

**Ollama (local, free):**
```
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=llama3.1
```

**Anthropic (via proxy):**
```
OPENAI_BASE_URL=https://api.anthropic.com/v1
OPENAI_API_KEY=sk-ant-...
OPENAI_MODEL=claude-3-5-haiku-20241022
```

## Benchmark Output

`benchmark.py` prints a complete metrics table:

```
────────────────────────────────────────────────────────────────────────
  AGENT METRICS
────────────────────────────────────────────────────────────────────────
  Agent                        Total     RAG     LLM   Prompt   Compl   Total
                                  ms      ms      ms      tok     tok     tok
·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·
  Financial Agent (RAG)         1842ms     0ms  1839ms   2,341     512   2,853
  Market Agent (RAG)            2104ms     0ms  2101ms   2,188     498   2,686
  Risk Agent (synthesis)        3211ms      —   3208ms   4,402     891   5,293
·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·
  TOTAL                         6204ms                   8,931   1,901  10,832
────────────────────────────────────────────────────────────────────────

  ORCHESTRATION METRICS
  Financial + Market phase  :    2104ms  (ran in parallel)
  Sequential estimate       :    7157ms
  Parallel speedup          :    1.74×
  Time saved by parallelism :    2953ms
  A2A round-trips           :      12
```

## Evals

`evals/dataset.jsonl` contains 12 evaluation cases covering:
- Isolated financial analysis queries (4 cases)
- Isolated market intelligence queries (4 cases)
- Full end-to-end due diligence (3 cases)
- Comparative / cross-company queries (1 case)

Each eval case specifies `expected_contains` strings to check in the output.

## File Structure

```
due-diligence/
├── agents/
│   ├── __init__.py      # Exports FinancialAgent, MarketAgent, RiskAgent
│   ├── base.py          # BaseA2AAgent: HTTP server + A2A protocol
│   ├── financial.py     # Financial Research Agent with RAG
│   ├── market.py        # Market Intelligence Agent with RAG
│   └── risk.py          # Risk Assessment Agent (synthesis + scoring)
├── knowledge/
│   ├── financials.md    # RAG corpus: financial profiles for Anthropic, OpenAI, Mistral
│   └── markets.md       # RAG corpus: market intelligence, competitive landscape
├── evals/
│   └── dataset.jsonl    # 12 evaluation test cases
├── orchestrator.py      # A2A orchestration flow (pure HTTP, no agent imports)
├── run.py               # Start all agents + run orchestration
├── benchmark.py         # Full metrics table with per-agent telemetry
├── .env.example         # Environment variable template
└── DESIGN.md            # Architecture deep-dive
```

## Deep Dive

See [DESIGN.md](DESIGN.md) for:
- Why A2A here vs. a monolithic agent
- Architecture diagram with data flow
- Why RAG for financial data (not live web search)
- How Agent Cards enable discovery and replaceability
- How parallel delegation reduces wall-clock time
- Production considerations (auth, error handling, scaling)
- What the benchmark metrics reveal
