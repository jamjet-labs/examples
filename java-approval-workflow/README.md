# Approval Workflow (Java)

Expense approval workflow with human-in-the-loop gate. Java equivalent of [`approval-workflow/`](../approval-workflow/).

## Run it

Local execution (no runtime needed):

```bash
mvn compile exec:java
```

With the runtime (for real HITL):

```bash
jamjet dev &
mvn compile exec:java
```

## What it does

1. **prepare** — categorizes the expense and determines if approval is needed
2. **review** — auto-approves small expenses; pauses for human approval on large ones
3. **process** — sends notification based on the decision

## Key concepts

- `Workflow.builder()` with typed record state
- `workflow.compile()` + `IrValidator.validateOrThrow()` for safe IR
- `workflow.run()` for local execution (no runtime)
- `JamjetClient` for submitting IR and starting executions on the runtime
- Human-in-the-loop: the runtime pauses at approval steps until `client.approve()` is called

## Output

```
--- Local Execution (small expense, auto-approved) ---
  Employee:  Alice
  Amount:    $250.00 (small)
  Decision:  auto-approved

--- Local Execution (large expense, requires approval) ---
  Employee:  Bob
  Amount:    $5000.00 (large)
  Decision:  approved
```

## Next steps

- Add an LLM step to generate expense summaries for reviewers
- Add a policy engine rule to enforce spending limits per department
- Use the runtime's approval UI for real human-in-the-loop
