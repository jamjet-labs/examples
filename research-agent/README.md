# Research Agent

Searches the web using Brave Search (MCP) and synthesizes a structured report with Claude.

## Prerequisites

1. Get a [Brave Search API key](https://api.search.brave.com/)
2. Set it as an env variable:
   ```bash
   export BRAVE_API_KEY=BSA...
   ```
3. Install the MCP server (npm required):
   ```bash
   npx -y @modelcontextprotocol/server-brave-search --help
   ```

## Run it

```bash
jamjet dev &

jamjet run workflow.yaml --input '{"query": "How does event sourcing work?"}'
```

With streaming:

```bash
jamjet run workflow.yaml \
  --input '{"query": "Latest AI agent frameworks compared"}' \
  --stream
```

## What it does

1. **search** — calls `brave-search/web_search` via MCP with your query (10 results, 3 retries with exponential backoff)
2. **synthesize** — sends results to Claude Sonnet to produce a structured report with citations

## Eval

Run the eval suite to measure report quality:

```bash
jamjet eval run evals/dataset.jsonl \
  --workflow workflow.yaml \
  --rubric "Is the report well-structured, factually grounded, and properly cited?" \
  --min-score 4 \
  --latency-ms 10000
```
