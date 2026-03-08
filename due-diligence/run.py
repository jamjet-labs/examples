"""
run.py — Start all A2A agents and run a due diligence orchestration.

Usage:
  python run.py [COMPANY]

  COMPANY defaults to the COMPANY env var, or "Anthropic" if not set.

All three agents start in this process for demo convenience. In production,
each agent would be a separate service (Docker container, Kubernetes pod, etc.)
deployed and scaled independently. The orchestrator code in orchestrator.py
works identically in both cases — it only communicates via HTTP.

Startup sequence:
  1. Load .env
  2. Start Financial Agent (port 7701)
  3. Start Market Agent (port 7702)
  4. Start Risk Agent (port 7703)
  5. Wait briefly for servers to be ready
  6. Run orchestration for the target company
  7. Print the final due diligence report
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# ── Load .env ──────────────────────────────────────────────────────────────────
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if _v:
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Validate required env ──────────────────────────────────────────────────────
if not os.environ.get("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    sys.exit(1)

from agents import FinancialAgent, MarketAgent, RiskAgent
from orchestrator import run_due_diligence


async def main() -> None:
    company = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("COMPANY", "Anthropic")

    print()
    print("=" * 62)
    print("  Due Diligence A2A Agent Network")
    print(f"  Company: {company}")
    print(f"  Model:   {os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')}")
    print("=" * 62)
    print()

    # ── Start all agents ───────────────────────────────────────────────────────
    print("[run] Starting agents...")
    financial_agent = FinancialAgent()
    market_agent    = MarketAgent()
    risk_agent      = RiskAgent()

    await asyncio.gather(
        financial_agent.start(),
        market_agent.start(),
        risk_agent.start(),
    )

    # Give aiohttp a tick to finish binding before we hit the endpoints
    await asyncio.sleep(0.3)
    print()

    # ── Run orchestration ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    report, metrics = await run_due_diligence(company)
    elapsed = time.perf_counter() - t0

    # ── Print report ───────────────────────────────────────────────────────────
    print()
    print(report)
    print()

    # ── Quick summary ──────────────────────────────────────────────────────────
    print("=" * 62)
    print("  SUMMARY")
    print("=" * 62)
    print(f"  Company         : {company}")
    print(f"  Total wall clock: {elapsed * 1000:.0f}ms")
    print(f"  A2A round-trips : {metrics.a2a_round_trips}")
    print(f"  Discovery time  : {metrics.discovery_ms:.0f}ms")
    print(f"  Parallel phase  : {metrics.parallel_phase_ms:.0f}ms (financial + market)")
    print(f"  Risk phase      : {metrics.risk_task_latency_ms:.0f}ms")
    print()
    print("  Run benchmark.py for full metrics table with token counts.")
    print("=" * 62)
    print()


if __name__ == "__main__":
    asyncio.run(main())
