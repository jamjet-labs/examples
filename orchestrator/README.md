# Orchestrator

A multi-agent workflow that orchestrates specialist agents (research, writing, fact-check) via the A2A protocol. Demonstrates parallel fan-out and cross-agent delegation.

## Architecture

```
orchestrator
├── plan (model)
└── parallel-gather
    ├── research  → [A2A] → research-agent
    └── outline   (model)
        ↓
    draft     → [A2A] → writer-agent
        ↓
    fact-check → [A2A] → fact-check-agent
        ↓
    finalize  (model)
```

## Setup

You need three specialist agents running. Use the JamJet examples or your own:

```bash
# In separate terminals:
cd research-agent && jamjet serve --port 7801
cd writer-agent   && jamjet serve --port 7802
cd factcheck-agent && jamjet serve --port 7803
```

Set env variables pointing to each:

```bash
export RESEARCH_AGENT_URL=http://localhost:7801
export WRITER_AGENT_URL=http://localhost:7802
export FACT_CHECK_AGENT_URL=http://localhost:7803
```

## Run it

```bash
jamjet dev &

jamjet run workflow.yaml \
  --input '{"task": "Write a technical blog post about AI agent durability"}'
```

## Key concepts

- **Parallel branches** — `research` and `outline` run concurrently
- **A2A delegation** — specialist agents are called via the standard A2A protocol
- **Merging** — `draft` node receives merged state from both parallel branches
- **Fallback** — `finalize` applies fact-check corrections before publishing
