# Hello Agent

The minimal JamJet workflow — one model node, one answer.

## Run it

```bash
jamjet dev &   # start runtime (once per session)

jamjet run workflow.yaml --input '{"query": "What is JamJet?"}'
```

## What it does

1. Takes a `query` string as input
2. Sends it to Claude Haiku with a simple prompt
3. Writes the response to `answer` in state
4. Terminates

## Python equivalent

```python
from jamjet import workflow, node, State

@workflow(id="hello-agent", version="0.1.0")
class HelloAgent:
    @node(start=True)
    async def think(self, state: State) -> State:
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            prompt=f"Answer clearly: {state['query']}",
        )
        return {"answer": response.text}
```

## Next steps

- Add a system prompt to `think` for a specific persona
- Chain another node to post-process the answer
- Try the [research-agent](../research-agent/) example to add web search
