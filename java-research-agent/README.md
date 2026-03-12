# Research Agent (Java)

Multi-step research agent with web search tools and plan-and-execute strategy. Java equivalent of [`research-agent/`](../research-agent/).

## Prerequisites

```bash
export OPENAI_API_KEY=sk-...
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

1. Defines two tools: `WebSearch` and `FetchPage` using `@Tool` + `ToolCall<T>`
2. Builds an agent with `plan-and-execute` strategy (plan steps, execute each, synthesize)
3. Validates the compiled IR with `IrValidator`
4. Runs the agent, which generates a plan and executes it step-by-step

## Key concepts

- `@Tool` annotation and `ToolCall<T>` interface for tool definition
- `plan-and-execute` strategy — generates a plan, then executes each step
- `maxCostUsd()` — cost budget limit
- Multi-tool agent with automatic tool dispatch

## Next steps

- Swap stub tools for real APIs (Brave Search, SerpAPI)
- Try `critic` strategy for iterative refinement
- Add eval scoring — see the [eval guide](https://jamjet.dev/guides/eval)
