# Approval Workflow

A human-in-the-loop workflow: the agent proposes an action plan, pauses for human approval, then either executes or handles rejection.

The execution is **durable** — you can approve hours later and it resumes exactly where it left off.

## Run it

```bash
jamjet dev &

# Start the workflow
jamjet run workflow.yaml --input '{"task": "Migrate database to new schema"}'
# → exec_01JM...  Status: waiting (await-approval)
```

In another terminal or from a webhook:

```bash
# Approve
jamjet resume exec_01JM... --event human_approved --data '{"approved": true}'

# Reject with reason
jamjet resume exec_01JM... --event human_approved \
  --data '{"approved": false, "rejection_reason": "Not enough testing done yet"}'
```

## Timeout handling

If no approval arrives within 24 hours, the `escalate` node fires automatically.

## Integration patterns

- **Webhook**: POST from your approval UI → `jamjet resume`
- **Slack bot**: `/approve exec_01JM...` → calls `jamjet resume`
- **Email**: Parse reply → trigger `jamjet resume` via API
