# Data Pipeline

A durable ETL pipeline that extracts from three APIs in parallel, transforms with Claude, and stores the result. Demonstrates JamJet's crash-recovery guarantee for long-running data workflows.

## Why JamJet for data pipelines?

If any HTTP fetch fails after retries, or the runtime crashes mid-pipeline, execution resumes from the last checkpoint. The completed `fetch-api1` step won't re-run — only the failed step retries.

## Setup

```bash
export API1_URL=https://api1.example.com
export API1_TOKEN=...
export API2_URL=https://api2.example.com
export API2_KEY=...
export API3_URL=https://api3.example.com
export API3_TOKEN=...
export REPORTS_URL=https://reports.example.com
export REPORTS_TOKEN=...
```

## Run it

```bash
jamjet dev &

jamjet run workflow.yaml --input '{"date": "2026-03-07"}'
```

## Parallel extraction

The `extract` parallel node fans out to all three API fetches simultaneously. Each has independent retry logic with exponential backoff. The `transform` node only runs after all three complete.

## Adapting it

- Add more `fetch-*` branches to the parallel node
- Replace HTTP nodes with MCP tool nodes for database sources
- Add an `eval` node before `store-report` to validate data quality
