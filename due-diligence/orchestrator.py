"""
orchestrator.py — Due Diligence Orchestrator

Implements the A2A orchestration flow for investment due diligence:

  1. Discover all 3 specialized agents via Agent Cards (parallel HTTP GET)
  2. Submit tasks to Financial + Market agents in parallel
  3. Poll for completion (both agents run simultaneously → parallel speedup)
  4. Submit combined analysis to Risk agent
  5. Synthesize and return the final due diligence report

This file only uses the A2A HTTP protocol — it has no Python imports from
the agent modules. It would work identically if the agents were deployed as
separate services on different machines or implemented in different languages.

The orchestrator treats agents as black boxes discovered via Agent Cards.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import aiohttp


# ── A2A client helpers ─────────────────────────────────────────────────────────

async def discover_agent(session: aiohttp.ClientSession, url: str) -> dict:
    """
    Fetch an Agent Card from /.well-known/agent.json.
    Returns the card as a dict on success, raises on failure.
    """
    card_url = f"{url}/.well-known/agent.json"
    async with session.get(card_url) as resp:
        resp.raise_for_status()
        card = await resp.json()
    return card


async def submit_task(
    session: aiohttp.ClientSession,
    agent_url: str,
    skill_id: str,
    input_text: str,
) -> str:
    """
    Submit a task to an A2A agent.
    Returns task_id.
    """
    async with session.post(
        f"{agent_url}/a2a/tasks",
        json={"skill_id": skill_id, "input": input_text},
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    return data["task_id"]


async def poll_task(
    session: aiohttp.ClientSession,
    agent_url: str,
    task_id: str,
    poll_interval: float = 0.5,
    timeout: float = 120.0,
) -> dict:
    """
    Poll GET /a2a/tasks/{id} until the task completes or fails.
    Returns the full task dict on completion.
    Raises TimeoutError if the task doesn't complete within timeout seconds.
    """
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

        async with session.get(f"{agent_url}/a2a/tasks/{task_id}") as resp:
            resp.raise_for_status()
            task = await resp.json()

        status = task["status"]
        if status == "completed":
            return task
        elif status == "failed":
            raise RuntimeError(f"Agent task failed: {task.get('error', 'unknown error')}")
        # else: pending or running — keep polling
        await asyncio.sleep(poll_interval)


# ── Telemetry accumulation ─────────────────────────────────────────────────────

@dataclass
class OrchestratorMetrics:
    """Accumulates per-agent metrics during orchestration."""
    discovery_ms: float = 0.0
    financial_task_latency_ms: float = 0.0
    market_task_latency_ms: float = 0.0
    risk_task_latency_ms: float = 0.0
    parallel_phase_ms: float = 0.0   # time for financial+market running concurrently
    total_wall_clock_ms: float = 0.0
    a2a_round_trips: int = 0         # total HTTP calls to A2A endpoints
    agent_metadata: dict = field(default_factory=dict)


# ── Main orchestration flow ────────────────────────────────────────────────────

AGENT_URLS = {
    "financial": "http://localhost:7701",
    "market":    "http://localhost:7702",
    "risk":      "http://localhost:7703",
}


async def run_due_diligence(company: str) -> tuple[str, OrchestratorMetrics]:
    """
    Full due diligence orchestration for a given company name.

    Returns (final_report: str, metrics: OrchestratorMetrics).
    """
    metrics = OrchestratorMetrics()
    t_total_start = time.perf_counter()

    async with aiohttp.ClientSession() as session:

        # ── Phase 1: Discover all agents in parallel ───────────────────────
        print("\n[orchestrator] Phase 1: Discovering agents via Agent Cards...")
        t0 = time.perf_counter()

        cards = await asyncio.gather(
            discover_agent(session, AGENT_URLS["financial"]),
            discover_agent(session, AGENT_URLS["market"]),
            discover_agent(session, AGENT_URLS["risk"]),
        )
        metrics.a2a_round_trips += 3
        metrics.discovery_ms = (time.perf_counter() - t0) * 1000

        financial_card, market_card, risk_card = cards
        print(f"  ✓ Discovered: {financial_card['name']} (port 7701)")
        print(f"  ✓ Discovered: {market_card['name']} (port 7702)")
        print(f"  ✓ Discovered: {risk_card['name']} (port 7703)")
        print(f"  Discovery took {metrics.discovery_ms:.0f}ms")

        # ── Phase 2: Submit Financial + Market tasks in parallel ───────────
        print(f"\n[orchestrator] Phase 2: Submitting parallel tasks for '{company}'...")

        financial_question = (
            f"Analyze the financial profile of {company}. "
            f"Cover revenue, ARR, business model, unit economics, funding history, "
            f"valuation, and key financial risks."
        )
        market_question = (
            f"Analyze the market position and competitive landscape for {company}. "
            f"Cover market size, competitive moats, key competitors, strategic risks, "
            f"and overall market positioning."
        )

        t0 = time.perf_counter()
        financial_task_id, market_task_id = await asyncio.gather(
            submit_task(session, AGENT_URLS["financial"], "analyze_financials", financial_question),
            submit_task(session, AGENT_URLS["market"], "analyze_market", market_question),
        )
        metrics.a2a_round_trips += 2
        print(f"  ✓ Financial task submitted: {financial_task_id[:8]}")
        print(f"  ✓ Market task submitted:    {market_task_id[:8]}")

        # ── Phase 3: Poll both agents concurrently ─────────────────────────
        print("\n[orchestrator] Phase 3: Awaiting Financial + Market results (parallel)...")

        t_parallel_start = time.perf_counter()

        async def _poll_financial() -> dict:
            t = time.perf_counter()
            result = await poll_task(session, AGENT_URLS["financial"], financial_task_id)
            metrics.financial_task_latency_ms = (time.perf_counter() - t) * 1000
            metrics.a2a_round_trips += int(metrics.financial_task_latency_ms / 500) + 1
            return result

        async def _poll_market() -> dict:
            t = time.perf_counter()
            result = await poll_task(session, AGENT_URLS["market"], market_task_id)
            metrics.market_task_latency_ms = (time.perf_counter() - t) * 1000
            metrics.a2a_round_trips += int(metrics.market_task_latency_ms / 500) + 1
            return result

        financial_result, market_result = await asyncio.gather(
            _poll_financial(), _poll_market()
        )
        metrics.parallel_phase_ms = (time.perf_counter() - t_parallel_start) * 1000

        print(f"  ✓ Financial analysis complete ({metrics.financial_task_latency_ms:.0f}ms)")
        print(f"  ✓ Market analysis complete    ({metrics.market_task_latency_ms:.0f}ms)")
        print(f"  Parallel phase took {metrics.parallel_phase_ms:.0f}ms "
              f"(would have taken {metrics.financial_task_latency_ms + metrics.market_task_latency_ms:.0f}ms sequentially)")

        # Store agent-level metadata
        metrics.agent_metadata["financial"] = financial_result.get("metadata", {})
        metrics.agent_metadata["market"] = market_result.get("metadata", {})

        # ── Phase 4: Submit combined analysis to Risk agent ────────────────
        print("\n[orchestrator] Phase 4: Submitting to Risk Assessment Agent...")

        combined_input = (
            f"Company: {company}\n\n"
            f"=== FINANCIAL ANALYSIS (from Financial Research Agent) ===\n"
            f"{financial_result['output']}\n\n"
            f"=== MARKET INTELLIGENCE (from Market Intelligence Agent) ===\n"
            f"{market_result['output']}\n\n"
            f"=== END OF RESEARCH INPUTS ===\n"
        )

        risk_task_id = await submit_task(
            session, AGENT_URLS["risk"], "assess_risk", combined_input
        )
        metrics.a2a_round_trips += 1
        print(f"  ✓ Risk task submitted: {risk_task_id[:8]}")

        t_risk_start = time.perf_counter()
        risk_result = await poll_task(session, AGENT_URLS["risk"], risk_task_id)
        metrics.risk_task_latency_ms = (time.perf_counter() - t_risk_start) * 1000
        metrics.a2a_round_trips += int(metrics.risk_task_latency_ms / 500) + 1
        metrics.agent_metadata["risk"] = risk_result.get("metadata", {})

        print(f"  ✓ Risk assessment complete ({metrics.risk_task_latency_ms:.0f}ms)")

    # ── Phase 5: Compose final report ─────────────────────────────────────
    print("\n[orchestrator] Phase 5: Composing final due diligence report...")
    metrics.total_wall_clock_ms = (time.perf_counter() - t_total_start) * 1000

    report = _compose_report(company, financial_result, market_result, risk_result)
    print(f"  ✓ Report ready ({metrics.total_wall_clock_ms:.0f}ms total wall clock)")

    return report, metrics


def _compose_report(
    company: str,
    financial_result: dict,
    market_result: dict,
    risk_result: dict,
) -> str:
    """Assemble the three agent outputs into a formatted due diligence report."""
    divider = "=" * 72
    section = "-" * 72

    return f"""
{divider}
  INVESTMENT DUE DILIGENCE REPORT
  Company: {company.upper()}
  Generated by: A2A Agent Network (Financial + Market + Risk Agents)
{divider}

{section}
  SECTION 1: FINANCIAL ANALYSIS
  Source: Financial Research Agent (RAG over financial knowledge base)
{section}

{financial_result['output']}


{section}
  SECTION 2: MARKET INTELLIGENCE & COMPETITIVE ANALYSIS
  Source: Market Intelligence Agent (RAG over market knowledge base)
{section}

{market_result['output']}


{section}
  SECTION 3: RISK ASSESSMENT & INVESTMENT RECOMMENDATION
  Source: Risk Assessment Agent (synthesis of Sections 1 + 2)
{section}

{risk_result['output']}


{divider}
  END OF REPORT
{divider}
""".strip()
