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
| [multi-tenant](./multi-tenant/) | Tenant-isolated invoice processing | Tenant scoping, row-level isolation, shared definitions |
| [data-governance](./data-governance/) | PII-aware customer onboarding | PII detection, redaction modes, retention policies |
| [oauth-delegation](./oauth-delegation/) | OAuth 2.0 delegated expense agent | RFC 8693 token exchange, scope narrowing, per-step scoping |
| | | |
| **Java SDK** | | |
| [java-hello-agent](./java-hello-agent/) | Minimal agent (Java) | Agent builder, IR validation |
| [java-research-agent](./java-research-agent/) | Web search + plan-and-execute (Java) | `@Tool`, `ToolCall<T>`, multi-step |
| [java-support-bot](./java-support-bot/) | Support ticket workflow (Java) | `Workflow.builder()`, record state, local exec |
| [java-approval-workflow](./java-approval-workflow/) | Expense approval with HITL (Java) | IR submission, `JamjetClient`, human approval |
| [java-multi-tenant](./java-multi-tenant/) | Tenant-isolated invoices (Java) | Multi-tenant, `JamjetClient`, tenant scoping |
| [java-data-governance](./java-data-governance/) | PII redaction workflow (Java) | PII detection, masking, retention policies |
| [java-oauth-agent](./java-oauth-agent/) | OAuth delegated agent (Java) | Scope narrowing, per-step scopes, audit trail |

## Running an example

### YAML / Python examples

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

### Java examples

Requires JDK 21+:

```bash
cd java-support-bot
mvn compile exec:java
```

For agent examples that call LLMs:

```bash
export OPENAI_API_KEY=sk-...
cd java-research-agent
mvn compile exec:java
```

## Structure

Each example is self-contained:

```
hello-agent/                          java-hello-agent/
├── workflow.yaml                     ├── pom.xml
├── workflow.py                       ├── src/main/java/.../HelloAgent.java
├── jamjet.toml                       └── README.md
├── evals/
│   └── dataset.jsonl
└── README.md
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
