"""
legal-research: AI research assistant with token & cost budget enforcement.

Demonstrates JamJet's budget enforcement:
  - Per-case token budget: 500k total
  - Per-case cost budget: $15 USD
  - Multi-dimension checks: input, output, total, cost
  - Budget survives crashes via snapshot persistence
  - Graceful pause when budget exceeded

Usage:
    jamjet dev &
    jamjet run workflow.py --input '{
        "case_id": "PATENT-2024-0847",
        "case_description": "Patent infringement: AI-generated code",
        "jurisdiction": "US Federal, Northern District of California",
        "max_precedents": 10
    }'
"""

from jamjet import workflow, node, State


@workflow(
    id="legal-research",
    version="0.1.0",
    # ── Budget enforcement ────────────────────────────────────────────
    # The managing partner mandates:
    #   - 500k tokens max per case
    #   - $15 hard cost cap per case
    #   - Pause on exceeded (partial results are still useful)
    token_budget={
        "input_tokens": 350_000,
        "output_tokens": 150_000,
        "total_tokens": 500_000,
    },
    cost_budget_usd=15.00,
    on_budget_exceeded="pause",
)
class LegalResearch:
    """Legal research assistant with per-case token and cost budgets."""

    @node(start=True)
    async def summarize_complaint(self, state: State) -> State:
        """Quick summary of the case filing. ~3k tokens, ~$0.003."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system=(
                "You are a legal research AI. Provide concise, accurate legal "
                "summaries. Cite relevant statutes and legal standards."
            ),
            prompt=(
                f"Case ID: {state['case_id']}\n"
                f"Jurisdiction: {state['jurisdiction']}\n\n"
                f"Summarize this case:\n{state['case_description']}\n\n"
                f"Include: parties, claims, factual allegations, "
                f"relevant statutes, jurisdictional basis."
            ),
        )
        return {"complaint_summary": response.text}

    @node
    async def search_precedents(self, state: State) -> State:
        """Search for relevant case law. ~8k tokens, ~$0.008."""
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a legal research AI specializing in case law. "
                "Prioritize same jurisdiction, recent decisions, appellate courts."
            ),
            prompt=(
                f"Case: {state['case_id']}\n"
                f"Summary: {state['complaint_summary']}\n"
                f"Jurisdiction: {state['jurisdiction']}\n"
                f"Find up to {state['max_precedents']} relevant precedents.\n\n"
                f"For each: case name, citation, court, year, holding, relevance."
            ),
        )
        return {"precedents": response.text}

    @node
    async def analyze_precedents(self, state: State) -> State:
        """Deep analysis of each precedent. THIS IS WHERE BUDGET MATTERS.

        Analyzing 10 precedents at ~12k tokens each = 120k tokens in this
        step alone. The budget enforcement catches runaway analysis here.
        """
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a senior legal analyst. Be thorough but concise — "
                "costs are monitored. If budget is running low, prioritize "
                "the most relevant cases and flag the rest for human review."
            ),
            prompt=(
                f"Case: {state['case_id']}\n"
                f"Our case: {state['complaint_summary']}\n"
                f"Precedents: {state['precedents']}\n\n"
                f"For each precedent, analyze: key facts comparison, legal reasoning, "
                f"statute application, position impact, distinguishing factors, "
                f"appeal potential."
            ),
        )
        return {"analyses": response.text}

    @node
    async def draft_memo(self, state: State) -> State:
        """Draft the research memorandum. ~23k tokens, ~$0.023.

        This is the final heavy step. The budget should still have room
        after the precedent analyses — but if the agent analyzed too many
        precedents, the budget check after this node will catch it.
        """
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a senior legal associate drafting a research memo. "
                "The memo may be used in court filings. Be precise and cite sources."
            ),
            prompt=(
                f"Case: {state['case_id']} — {state['case_description']}\n"
                f"Jurisdiction: {state['jurisdiction']}\n"
                f"Summary: {state['complaint_summary']}\n"
                f"Analyses: {state['analyses']}\n\n"
                f"Draft a memo with:\n"
                f"I. QUESTION PRESENTED\n"
                f"II. SHORT ANSWER\n"
                f"III. STATEMENT OF FACTS\n"
                f"IV. DISCUSSION (legal standard, precedent analysis, application)\n"
                f"V. CONCLUSION AND RECOMMENDATION"
            ),
        )
        return {"comparative_memo": response.text}

    @node
    async def budget_summary(self, state: State) -> State:
        """Final step: mark workflow complete with budget status.

        The actual budget tracking is handled by the runtime automatically.
        This step exists for workflow completeness.
        """
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            prompt=(
                f"Case {state['case_id']} research complete. "
                f"Memo drafted. Summarize completion status in one sentence."
            ),
        )
        return {"budget_status": response.text}
