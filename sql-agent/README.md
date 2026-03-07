# SQL Agent

Ask your database questions in plain English. JamJet fetches the schema, generates SQL with Claude, validates it for safety, executes it via the PostgreSQL MCP server, and explains the results.

## Prerequisites

```bash
export DATABASE_URL=postgresql://user:password@host:5432/mydb
```

## Run it

```bash
jamjet dev &

jamjet run workflow.yaml \
  --input '{"question": "How many users signed up last week?"}'

jamjet run workflow.yaml \
  --input '{"question": "What are the top 5 products by revenue this month?"}'
```

## Safety

The `validate-sql` branch node checks that the generated query is a `SELECT` statement and rejects DDL/DML. The PostgreSQL MCP server also enforces read-only mode.

## Adapting it

- Add a `confirm` wait node before executing queries that return large result sets
- Add an `eval` node to score answer quality against expected results
- Connect to multiple databases by adding more MCP server entries in `jamjet.toml`
