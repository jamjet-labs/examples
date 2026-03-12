# Hello Agent (Java)

Minimal JamJet example — one agent, one question, one answer. Java equivalent of [`hello-agent/`](../hello-agent/).

## Prerequisites

```bash
export OPENAI_API_KEY=sk-...    # or any OpenAI-compatible endpoint
```

## Run it

```bash
mvn compile exec:java
```

With a custom query:

```bash
mvn compile exec:java -Dexec.args="How does event sourcing work?"
```

## What it does

1. Builds an `Agent` with Claude Haiku and the react strategy
2. Compiles to canonical IR and validates it
3. Runs the agent against your query via the OpenAI-compatible API
4. Prints the answer

## Key concepts

- `Agent.builder()` — fluent agent construction
- `agent.compile()` — IR generation
- `IrValidator.validate()` — client-side validation
- `agent.run()` — in-process execution (no runtime needed)

## Next steps

- Add tools with `@Tool` — see [`java-research-agent/`](../java-research-agent/)
- Use workflows instead of agents — see [`java-support-bot/`](../java-support-bot/)
- Submit IR to the runtime — see [`java-approval-workflow/`](../java-approval-workflow/)
