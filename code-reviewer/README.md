# Code Reviewer

Fetches a GitHub PR via MCP, generates a thorough code review with Claude, scores quality with an eval node, retries with feedback if quality is low, then posts the review as a PR comment.

## Prerequisites

```bash
export GITHUB_TOKEN=ghp_...
```

## Run it

```bash
jamjet dev &

jamjet run workflow.yaml \
  --input '{"repo": "owner/repo", "pr_number": 42}'
```

## Self-improvement loop

The `check-quality` eval node scores the review on a 1–5 rubric. If it scores below 4, the feedback is automatically injected into the next model call:

```
First review → score 3.1 (too generic)
  ↓ feedback: "Be more specific, reference line numbers"
Second review → score 4.7 (thorough and specific)
  ↓ posts to GitHub
```

Max 2 retries, then posts the best available review.
