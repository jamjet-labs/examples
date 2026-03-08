"""
benchmark.py — Due Diligence A2A Benchmark

Runs the full due diligence agent network and captures detailed metrics:
  - Per-agent latency (ms)
  - RAG retrieval latency (financial + market agents)
  - LLM call latency per agent
  - Token usage per agent (prompt + completion + total)
  - Total A2A round-trips
  - Parallel speedup (sequential time vs. actual wall-clock time)
  - Estimated cost (based on OpenAI gpt-4o-mini pricing)

Prints a clean metrics table in the style of the vertex-ai benchmark example.

Usage:
  python benchmark.py [COMPANY]
"""

import asyncio
import os
import sys
import time
from datetime import date
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

if not os.environ.get("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    sys.exit(1)

from agents import FinancialAgent, MarketAgent, RiskAgent
from orchestrator import run_due_diligence, OrchestratorMetrics

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# ── Cost estimation ────────────────────────────────────────────────────────────
# gpt-4o-mini pricing (as of early 2025): $0.150/1M input, $0.600/1M output
# Override these if using a different model.
COST_PER_1M_INPUT  = float(os.environ.get("COST_PER_1M_INPUT",  "0.150"))
COST_PER_1M_OUTPUT = float(os.environ.get("COST_PER_1M_OUTPUT", "0.600"))


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * COST_PER_1M_INPUT + completion_tokens * COST_PER_1M_OUTPUT) / 1_000_000


def _print_divider(char: str = "─", width: int = 72) -> None:
    print(char * width)


async def main() -> None:
    company = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("COMPANY", "Anthropic")

    print()
    print("=" * 72)
    print("  Due Diligence A2A Agent Network — Benchmark")
    print(f"  Company : {company}")
    print(f"  Model   : {MODEL}")
    print(f"  Date    : {date.today()}")
    print("=" * 72)
    print()

    # ── Start agents ───────────────────────────────────────────────────────────
    print("[benchmark] Starting agents...")
    financial_agent = FinancialAgent()
    market_agent    = MarketAgent()
    risk_agent      = RiskAgent()

    await asyncio.gather(
        financial_agent.start(),
        market_agent.start(),
        risk_agent.start(),
    )
    await asyncio.sleep(0.3)  # give servers a tick to finish binding
    print()

    # ── Run orchestration ──────────────────────────────────────────────────────
    print(f"[benchmark] Running due diligence for '{company}'...")
    print()

    t_wall_start = time.perf_counter()
    report, metrics = await run_due_diligence(company)
    t_wall_ms = (time.perf_counter() - t_wall_start) * 1000

    # ── Extract per-agent telemetry ────────────────────────────────────────────
    fin_meta  = metrics.agent_metadata.get("financial", {})
    mkt_meta  = metrics.agent_metadata.get("market", {})
    risk_meta = metrics.agent_metadata.get("risk", {})

    # Latency breakdown
    fin_rag_ms  = fin_meta.get("rag_latency_ms", 0)
    fin_llm_ms  = fin_meta.get("llm_latency_ms", 0)
    mkt_rag_ms  = mkt_meta.get("rag_latency_ms", 0)
    mkt_llm_ms  = mkt_meta.get("llm_latency_ms", 0)
    risk_llm_ms = risk_meta.get("llm_latency_ms", 0)

    # Token counts
    fin_pt  = fin_meta.get("prompt_tokens", 0)
    fin_ct  = fin_meta.get("completion_tokens", 0)
    fin_tt  = fin_meta.get("total_tokens", 0)
    mkt_pt  = mkt_meta.get("prompt_tokens", 0)
    mkt_ct  = mkt_meta.get("completion_tokens", 0)
    mkt_tt  = mkt_meta.get("total_tokens", 0)
    risk_pt = risk_meta.get("prompt_tokens", 0)
    risk_ct = risk_meta.get("completion_tokens", 0)
    risk_tt = risk_meta.get("total_tokens", 0)

    total_pt = fin_pt + mkt_pt + risk_pt
    total_ct = fin_ct + mkt_ct + risk_ct
    total_tt = fin_tt + mkt_tt + risk_tt

    total_cost = _estimate_cost(total_pt, total_ct)

    # Parallel speedup calculation
    sequential_estimate_ms = (
        metrics.financial_task_latency_ms
        + metrics.market_task_latency_ms
        + metrics.risk_task_latency_ms
    )
    actual_parallel_ms = metrics.parallel_phase_ms + metrics.risk_task_latency_ms
    speedup = sequential_estimate_ms / actual_parallel_ms if actual_parallel_ms > 0 else 1.0

    # ── Print metrics table ────────────────────────────────────────────────────
    print()
    _print_divider()
    print("  AGENT METRICS")
    _print_divider()
    print(f"  {'Agent':<28} {'Total':>9} {'RAG':>7} {'LLM':>7} {'Prompt':>8} {'Compl':>7} {'Total':>7}")
    print(f"  {'':28} {'ms':>9} {'ms':>7} {'ms':>7} {'tok':>8} {'tok':>7} {'tok':>7}")
    _print_divider("·")
    print(
        f"  {'Financial Agent (RAG)':<28}"
        f" {metrics.financial_task_latency_ms:>8.0f}ms"
        f" {fin_rag_ms:>6.0f}ms"
        f" {fin_llm_ms:>6.0f}ms"
        f" {fin_pt:>8,}"
        f" {fin_ct:>7,}"
        f" {fin_tt:>7,}"
    )
    print(
        f"  {'Market Agent (RAG)':<28}"
        f" {metrics.market_task_latency_ms:>8.0f}ms"
        f" {mkt_rag_ms:>6.0f}ms"
        f" {mkt_llm_ms:>6.0f}ms"
        f" {mkt_pt:>8,}"
        f" {mkt_ct:>7,}"
        f" {mkt_tt:>7,}"
    )
    print(
        f"  {'Risk Agent (synthesis)':<28}"
        f" {metrics.risk_task_latency_ms:>8.0f}ms"
        f" {'—':>7}"
        f" {risk_llm_ms:>6.0f}ms"
        f" {risk_pt:>8,}"
        f" {risk_ct:>7,}"
        f" {risk_tt:>7,}"
    )
    _print_divider("·")
    print(
        f"  {'TOTAL':<28}"
        f" {t_wall_ms:>8.0f}ms"
        f" {'':>7}"
        f" {'':>7}"
        f" {total_pt:>8,}"
        f" {total_ct:>7,}"
        f" {total_tt:>7,}"
    )
    _print_divider()
    print()

    # ── Orchestration metrics ──────────────────────────────────────────────────
    _print_divider()
    print("  ORCHESTRATION METRICS")
    _print_divider()
    print(f"  Agent discovery (parallel)      : {metrics.discovery_ms:>7.0f}ms  (3 Agent Cards fetched)")
    print(f"  Financial + Market phase        : {metrics.parallel_phase_ms:>7.0f}ms  (ran in parallel)")
    print(f"    └─ Financial agent only       : {metrics.financial_task_latency_ms:>7.0f}ms")
    print(f"    └─ Market agent only          : {metrics.market_task_latency_ms:>7.0f}ms")
    print(f"  Risk assessment phase           : {metrics.risk_task_latency_ms:>7.0f}ms")
    print(f"  Total wall-clock time           : {t_wall_ms:>7.0f}ms")
    print()
    print(f"  Sequential estimate (no parallel): {sequential_estimate_ms:>6.0f}ms")
    print(f"  Parallel speedup                 : {speedup:>6.2f}×")
    print(f"  Time saved by parallelism        : {sequential_estimate_ms - actual_parallel_ms:>6.0f}ms")
    print()
    print(f"  A2A round-trips                 : {metrics.a2a_round_trips}")
    _print_divider()
    print()

    # ── Cost table ─────────────────────────────────────────────────────────────
    _print_divider()
    print("  COST BREAKDOWN")
    _print_divider()
    fin_cost  = _estimate_cost(fin_pt,  fin_ct)
    mkt_cost  = _estimate_cost(mkt_pt,  mkt_ct)
    risk_cost = _estimate_cost(risk_pt, risk_ct)
    print(f"  Pricing model: ${COST_PER_1M_INPUT}/1M input, ${COST_PER_1M_OUTPUT}/1M output ({MODEL})")
    print()
    print(f"  {'Agent':<28} {'Input':>10} {'Output':>10} {'Cost':>12}")
    _print_divider("·")
    print(f"  {'Financial Agent':<28} {fin_pt:>10,} {fin_ct:>10,} ${fin_cost:>10.5f}")
    print(f"  {'Market Agent':<28} {mkt_pt:>10,} {mkt_ct:>10,} ${mkt_cost:>10.5f}")
    print(f"  {'Risk Agent':<28} {risk_pt:>10,} {risk_ct:>10,} ${risk_cost:>10.5f}")
    _print_divider("·")
    print(f"  {'TOTAL':<28} {total_pt:>10,} {total_ct:>10,} ${total_cost:>10.5f}")
    _print_divider()
    print()

    # ── RAG details ────────────────────────────────────────────────────────────
    _print_divider()
    print("  RAG RETRIEVAL DETAILS")
    _print_divider()
    print(f"  Financial Agent — chunks retrieved : {fin_meta.get('chunks_retrieved', '?')}")
    for h in fin_meta.get("chunks_used", []):
        print(f"    · {h}")
    print(f"  Financial Agent — RAG latency      : {fin_rag_ms:.1f}ms")
    print()
    print(f"  Market Agent — chunks retrieved    : {mkt_meta.get('chunks_retrieved', '?')}")
    for h in mkt_meta.get("chunks_used", []):
        print(f"    · {h}")
    print(f"  Market Agent — RAG latency         : {mkt_rag_ms:.1f}ms")
    _print_divider()
    print()

    # ── Report preview ─────────────────────────────────────────────────────────
    _print_divider()
    print("  REPORT PREVIEW (first 1,200 chars)")
    _print_divider()
    print()
    print(report[:1200] + ("..." if len(report) > 1200 else ""))
    print()
    _print_divider("=")
    print("  Benchmark complete.")
    _print_divider("=")
    print()


if __name__ == "__main__":
    asyncio.run(main())
