# Support Bot

A Python SDK workflow that classifies support tickets, searches a knowledge base, and drafts empathetic replies.

## What it demonstrates

- **Python SDK** decorator-based workflow authoring
- **Classification** with structured JSON output from a fast model (Haiku)
- **MCP tool call** to a knowledge base server
- **Multi-model** — Haiku for classification, Sonnet for reply drafting

## Run it

```bash
jamjet dev &

python -c "
import asyncio
from workflow import SupportBot
from jamjet import JamJetClient

async def main():
    client = JamJetClient()
    result = await client.run(SupportBot, input={
        'ticket': 'I cannot log in — password reset email never arrived',
        'ticket_id': 'TKT-4821',
    })
    print(result.state['reply'])

asyncio.run(main())
"
```

## Adapting it

- Swap the `knowledge-base` MCP server for your actual KB (Notion, Confluence, custom)
- Add a `send_reply` node to push replies to your ticketing system (Zendesk, Linear, etc.)
- Add an eval node to score reply quality before sending
