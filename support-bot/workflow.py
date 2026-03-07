"""
support-bot: Customer support ticket classification, KB search, and reply drafting.

Usage:
    python -c "
    import asyncio
    from workflow import SupportBot
    from jamjet import JamJetClient

    async def main():
        client = JamJetClient()
        result = await client.run(SupportBot, input={
            'ticket': 'I cannot log in to my account — it says my password is wrong',
            'ticket_id': 'TKT-4821',
        })
        print(result.state['reply'])

    asyncio.run(main())
    "
"""

from jamjet import workflow, node, State


@workflow(id="support-bot", version="0.1.0")
class SupportBot:
    """Three-step support workflow: classify → search KB → draft reply."""

    @node(start=True)
    async def classify(self, state: State) -> State:
        """Classify the ticket by category and priority."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system="You are a support ticket classifier. Output JSON only.",
            prompt=f"""Classify this support ticket:

{state['ticket']}

Output JSON with keys:
- category: one of [account, billing, technical, feature_request, other]
- priority: one of [urgent, high, normal, low]
- sentiment: one of [frustrated, neutral, positive]
- summary: one-sentence summary of the issue
""",
        )
        return {"classification": response.json()}

    @node
    async def search_kb(self, state: State) -> State:
        """Search the knowledge base for relevant articles."""
        results = await self.tool(
            server="knowledge-base",
            tool="search",
            arguments={
                "query": state["ticket"],
                "category": state["classification"]["category"],
                "limit": 5,
            },
        )
        return {"kb_results": results.content}

    @node
    async def draft_reply(self, state: State) -> State:
        """Draft a helpful, empathetic support reply."""
        classification = state["classification"]

        response = await self.model(
            model="claude-sonnet-4-6",
            system="""You are a helpful, empathetic customer support agent.
Write clear, friendly replies that directly address the customer's issue.
Use the knowledge base articles provided to give accurate information.
Sign off as 'The Support Team'.""",
            prompt=f"""Customer ticket (ID: {state['ticket_id']}):
{state['ticket']}

Classification: {classification['category']} / {classification['priority']} priority
Customer sentiment: {classification['sentiment']}

Relevant knowledge base articles:
{chr(10).join(str(r) for r in state['kb_results'])}

Draft a helpful reply that:
1. Acknowledges the customer's issue with empathy
2. Provides clear steps to resolve it based on the KB articles
3. Offers follow-up if the issue persists
""",
        )
        return {"reply": response.text}
