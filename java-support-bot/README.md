# Support Bot (Java)

Three-step support ticket workflow: classify, search KB, draft reply. Java equivalent of [`support-bot/`](../support-bot/).

## Run it

No API keys needed — runs entirely in-process:

```bash
mvn compile exec:java
```

## What it does

1. **classify** — categorizes the ticket (account/billing/technical) and detects sentiment
2. **search_kb** — retrieves relevant knowledge base articles based on category
3. **draft_reply** — drafts an empathetic reply using KB context

## Key concepts

- `Workflow.builder()` — fluent workflow construction with typed state
- Java records as workflow state (immutable, type-safe)
- `workflow.run()` — in-process execution, no runtime server needed
- `workflow.compile()` — generates canonical IR for submission to runtime

## Output

```
Category:  account
Priority:  high
Sentiment: frustrated

=== Reply ===
Hi there,

I completely understand how frustrating this must be. ...
```

## Next steps

- Add LLM calls in classify/draft steps using `Agent.run()`
- Add conditional routing: escalate urgent tickets to a human
- Submit the IR to the runtime for durable execution
