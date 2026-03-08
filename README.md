<div align="center">

<!-- Pixel art lightning bolt logo -->
<svg width="60" height="72" viewBox="0 0 30 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="0"  width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="0"  width="5" height="4" fill="#f5c518"/>
  <rect x="5"  y="4"  width="5" height="4" fill="#f5c518"/>
  <rect x="10" y="4"  width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="4"  width="5" height="4" fill="#f5c518"/>
  <rect x="20" y="4"  width="5" height="4" fill="#f5c518"/>
  <rect x="10" y="8"  width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="8"  width="5" height="4" fill="#f5c518"/>
  <rect x="0"  y="12" width="5" height="4" fill="#f5c518"/>
  <rect x="5"  y="12" width="5" height="4" fill="#f5c518"/>
  <rect x="10" y="12" width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="12" width="5" height="4" fill="#f5c518"/>
  <rect x="5"  y="16" width="5" height="4" fill="#f5c518"/>
  <rect x="10" y="16" width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="16" width="5" height="4" fill="#f5c518"/>
  <rect x="20" y="16" width="5" height="4" fill="#f5c518"/>
  <rect x="25" y="16" width="5" height="4" fill="#f5c518"/>
  <rect x="10" y="20" width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="20" width="5" height="4" fill="#f5c518"/>
  <rect x="10" y="24" width="5" height="4" fill="#f5c518"/>
  <rect x="15" y="24" width="5" height="4" fill="#f5c518"/>
</svg>

# JamJet Examples

**Ready-to-run workflow examples for [JamJet](https://github.com/jamjet-labs/jamjet) — the agent-native runtime.**

[![License](https://img.shields.io/badge/license-Apache%202.0-f5c518?style=flat-square)](../jamjet/LICENSE)

[jamjet.dev](https://jamjet.dev) · [Docs](https://jamjet.dev/docs/quickstart) · [Examples Gallery](https://jamjet.dev/examples)

</div>

---

## Prerequisites

```bash
pip install jamjet
export ANTHROPIC_API_KEY=sk-ant-...    # or OPENAI_API_KEY
```

Start the local runtime (keep this running):

```bash
jamjet dev
```

## Examples

| Example | Description | Key concepts |
|---------|-------------|-------------|
| [hello-agent](./hello-agent/) | Minimal question-answering workflow | Model node, basic state |
| [research-agent](./research-agent/) | Web search + synthesis | MCP tool node, multi-step |
| [code-reviewer](./code-reviewer/) | GitHub PR review with quality scoring | MCP, eval node, retry |
| [support-bot](./support-bot/) | Customer support ticket handler | Python SDK, classification |
| [approval-workflow](./approval-workflow/) | Human-in-the-loop approval gate | Wait node, event resume |
| [orchestrator](./orchestrator/) | Multi-agent delegation with A2A | A2A task node, parallel |
| [data-pipeline](./data-pipeline/) | Extract, transform, load with checkpointing | Durability, parallel branches |
| [sql-agent](./sql-agent/) | Natural language to SQL via MCP | PostgreSQL MCP server |
| [vertex-ai](./vertex-ai/) | Gemini on Vertex AI as the model provider | OpenAI-compatible endpoint, token auth |
| | | |
| **Enterprise** | | |
| [healthcare-compliance](./healthcare-compliance/) | HIPAA-compliant patient intake | Policy engine, tool blocking, model allowlists |
| [trading-agent](./trading-agent/) | Hedge fund pre-trade research pipeline | Autonomy enforcement, circuit breaker, guided mode |
| [legal-research](./legal-research/) | Law firm AI research with cost caps | Token & cost budgets, crash-resilient state |
| [fintech-audit](./fintech-audit/) | SOC2-compliant loan application | Audit trail, actor attribution, forensic correlation |

## Running an example

```bash
cd hello-agent
jamjet validate workflow.yaml
jamjet run workflow.yaml --input '{"query": "What is JamJet?"}'
```

For examples that stream output:

```bash
jamjet run workflow.yaml --input '{"query": "..."}' --stream
```

Inspect the result:

```bash
jamjet inspect <exec-id>
```

## Structure

Each example is self-contained:

```
hello-agent/
├── workflow.yaml      # YAML workflow definition (always present)
├── workflow.py        # Python SDK equivalent (where applicable)
├── jamjet.toml        # MCP server config (where needed)
├── evals/
│   └── dataset.jsonl  # Eval dataset (where applicable)
└── README.md          # Example-specific docs
```

## Contributing

New examples welcome! Keep them:
- Self-contained (minimal external dependencies)
- Well-documented with a clear `README.md`
- Under 100 lines of YAML/Python where possible

Open a PR or GitHub Discussion with your idea.

---

<div align="center">
  <sub>© 2026 JamJet — Apache 2.0 · <a href="https://jamjet.dev">jamjet.dev</a></sub>
</div>
