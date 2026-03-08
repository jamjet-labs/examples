"""
trading-agent: Pre-trade research with autonomy enforcement.

Demonstrates JamJet's autonomy levels:
  - bounded_autonomous: research agent with iteration/cost/token limits
  - guided: execution agent requiring trader approval for every action
  - circuit breaker: stops agents after N consecutive errors

Usage:
    jamjet dev &
    jamjet run workflow.py --input '{
        "ticker": "NVDA",
        "analysis_type": "10-K filing deep analysis",
        "position_size_usd": 500000
    }'
"""

from jamjet import workflow, node, State, Agent, tool


# ── Tools available to the research agent ────────────────────────────

@tool
async def search_sec_filings(ticker: str, filing_type: str = "10-K") -> str:
    """Search SEC EDGAR for company filings."""
    return f"SEC filing results for {ticker} ({filing_type})"


@tool
async def search_news(ticker: str, days: int = 30) -> str:
    """Search financial news for a ticker."""
    return f"News results for {ticker} (last {days} days)"


@tool
async def analyze_sentiment(text: str) -> str:
    """Analyze market sentiment of financial text."""
    return f"Sentiment analysis: {text[:50]}..."


# ── Tools available to the risk agent ────────────────────────────────

@tool
async def check_portfolio_exposure(ticker: str, position_usd: float) -> str:
    """Check if position exceeds portfolio exposure limits."""
    return f"Exposure check: {ticker} @ ${position_usd:,.0f}"


@tool
async def check_sector_concentration(ticker: str) -> str:
    """Check sector concentration risk."""
    return f"Sector concentration for {ticker}: within limits"


# ── Tools available to the execution agent ───────────────────────────

@tool
async def submit_market_order(ticker: str, side: str, quantity: int) -> str:
    """Submit a market order to the broker. Requires trader approval."""
    return f"Order submitted: {side} {quantity} {ticker} @ market"


@tool
async def cancel_order(order_id: str) -> str:
    """Cancel a pending order. Requires trader approval."""
    return f"Order {order_id} cancelled"


# ── Workflow definition ──────────────────────────────────────────────

@workflow(
    id="trading-agent",
    version="0.1.0",
    token_budget={"total_tokens": 200_000},
    cost_budget_usd=10.00,
    on_budget_exceeded="pause",
)
class TradingAgent:
    """Pre-trade research pipeline with autonomy enforcement."""

    @node(start=True)
    async def research(self, state: State) -> State:
        """Research agent: bounded_autonomous with strict limits."""
        agent = Agent(
            "quant-research-v2",
            model="claude-sonnet-4-6",
            tools=[search_sec_filings, search_news, analyze_sentiment],
            instructions=(
                "You are a quantitative research analyst. Analyze the security by "
                "searching SEC filings, news, and sentiment. Be thorough but efficient."
            ),
            # ── Autonomy: bounded_autonomous ─────────────────────────
            strategy="react",
            max_iterations=10,
            max_cost_usd=2.0,
            timeout_seconds=300,
        )
        result = await agent.run(
            f"Analyze {state['ticker']}: {state['analysis_type']}. "
            f"Search filings, analyze news sentiment, identify risks and catalysts."
        )
        return {"research_output": result.output}

    @node
    async def risk_assessment(self, state: State) -> State:
        """Risk agent: bounded_autonomous with tighter limits."""
        agent = Agent(
            "risk-validator-v1",
            model="claude-sonnet-4-6",
            tools=[check_portfolio_exposure, check_sector_concentration],
            instructions=(
                "You are a risk management AI. Validate the proposed position "
                "against portfolio risk limits."
            ),
            strategy="react",
            max_iterations=5,
            max_cost_usd=1.0,
            timeout_seconds=120,
        )
        result = await agent.run(
            f"Validate ${state['position_size_usd']:,.0f} position in {state['ticker']}. "
            f"Research findings: {state['research_output'][:500]}"
        )
        return {"risk_assessment": result.output}

    @node
    async def propose_order(self, state: State) -> State:
        """Propose specific order parameters based on research and risk."""
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                "You are a trade operations AI. Propose a specific order "
                "with exact parameters based on research and risk assessment."
            ),
            prompt=(
                f"Research: {state['research_output'][:500]}\n"
                f"Risk: {state['risk_assessment'][:500]}\n"
                f"Requested position: ${state['position_size_usd']:,.0f}\n\n"
                f"Propose: action, ticker, quantity, order type, stop-loss."
            ),
        )
        return {"order_proposal": response.text}

    @node(
        # ── Autonomy: guided ─────────────────────────────────────────
        # Every tool call requires trader approval. No exceptions.
        # The @node decorator doesn't directly set autonomy — this is
        # declared in the workflow YAML or the agent card. In Python,
        # the guided constraint is enforced by the runtime when the
        # agent_ref's card specifies autonomy_level: guided.
        human_approval=True,
    )
    async def execute_trade(self, state: State) -> State:
        """Execution agent: guided mode — every action needs trader approval."""
        # In guided mode, each tool call below will pause execution
        # and wait for the trader to approve via /approve endpoint.
        agent = Agent(
            "trade-executor-v1",
            model="claude-haiku-4-5-20251001",
            tools=[submit_market_order, cancel_order],
            instructions=(
                "You are a trade execution AI. Submit the proposed order. "
                "Every action requires trader approval before execution."
            ),
            strategy="react",
            max_iterations=3,
        )
        result = await agent.run(f"Execute: {state['order_proposal']}")
        return {"execution_result": result.output}
