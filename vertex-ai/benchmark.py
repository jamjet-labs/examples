"""
Benchmark: JamJet @task + @tool on Vertex AI (Gemini 2.0 Flash)

Records per-step timing, token usage, and total wall-clock time.
Run: python benchmark.py
"""

import asyncio
import os
import time
from pathlib import Path
from datetime import date

# Load .env
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if v:
                os.environ.setdefault(k.strip(), v.strip())

project  = os.environ["VERTEX_PROJECT"]
location = os.environ.get("VERTEX_LOCATION", "us-central1")
os.environ.setdefault(
    "OPENAI_BASE_URL",
    f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/endpoints/openapi",
)

if "OPENAI_API_KEY" not in os.environ:
    import subprocess
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    os.environ["OPENAI_API_KEY"] = token

from openai import AsyncOpenAI
from jamjet import task, tool

MODEL = "google/gemini-2.0-flash-001"
QUERY = "What are the key trends in AI agents in 2025?"

# ── Instrumented client wrapper ────────────────────────────────────────────

call_log: list[dict] = []

_orig_client = AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)

async def instrumented_create(**kwargs):
    t0 = time.perf_counter()
    response = await _orig_client.chat.completions.create(**kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    usage = response.usage
    call_log.append({
        "model": kwargs.get("model"),
        "prompt_tokens":     usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens":      usage.total_tokens if usage else 0,
        "latency_ms":        round(elapsed_ms, 1),
        "has_tools":         bool(kwargs.get("tools")),
    })
    return response

# Monkey-patch so @task calls go through our wrapper
import jamjet.agents.agent as _agent_mod
import openai as _openai_mod

class _PatchedCompletions:
    async def create(self, **kwargs):
        return await instrumented_create(**kwargs)

class _PatchedChat:
    completions = _PatchedCompletions()

class _PatchedClient:
    chat = _PatchedChat()

# Override the client constructor used inside Agent.run()
_real_AsyncOpenAI = _openai_mod.AsyncOpenAI
def _patched_AsyncOpenAI(**kwargs):
    return _PatchedClient()
_openai_mod.AsyncOpenAI = _patched_AsyncOpenAI

# ── Tools ──────────────────────────────────────────────────────────────────

@tool
async def current_date() -> str:
    """Return today's date so the agent can reason about recency."""
    return date.today().isoformat()

# ── Tasks ──────────────────────────────────────────────────────────────────

@task(model=MODEL, tools=[current_date])
async def plan(query: str) -> str:
    """
    You are a research planner. Break the user's query into 3-5 focused
    sub-questions that together will produce a complete answer.
    Return only a numbered list of sub-questions, nothing else.
    """

@task(model=MODEL, tools=[current_date])
async def synthesize(query_and_outline: str) -> str:
    """
    You are a research analyst. Write a thorough, well-structured report
    that addresses the query using the provided outline as your guide.
    Use clear headings. Be concise but complete.
    """

# ── Benchmark runner ───────────────────────────────────────────────────────

async def main():
    print()
    print("=" * 62)
    print("  JamJet × Vertex AI — Benchmark")
    print(f"  Model  : {MODEL}")
    print(f"  Project: {project} ({location})")
    print(f"  Date   : {date.today()}")
    print("=" * 62)
    print()

    t_total = time.perf_counter()

    # Step 1 — plan
    print("▶ Step 1: plan()")
    t0 = time.perf_counter()
    outline = await plan(QUERY)
    t_plan = (time.perf_counter() - t0) * 1000

    print(f"  ✓ completed in {t_plan:.0f}ms")
    print()
    print("  Output:")
    for line in outline.strip().splitlines():
        print(f"    {line}")
    print()

    # Step 2 — synthesize
    print("▶ Step 2: synthesize()")
    t0 = time.perf_counter()
    report = await synthesize(f"Query: {QUERY}\n\nOutline:\n{outline}")
    t_synth = (time.perf_counter() - t0) * 1000

    print(f"  ✓ completed in {t_synth:.0f}ms")
    print()

    t_wall = (time.perf_counter() - t_total) * 1000

    # ── Metrics table ──────────────────────────────────────────────────────
    print("─" * 62)
    print("  METRICS")
    print("─" * 62)
    print(f"  {'Step':<28} {'Latency':>10} {'Prompt':>8} {'Compl':>8} {'Total':>8}")
    print(f"  {'─'*28} {'─'*10} {'─'*8} {'─'*8} {'─'*8}")

    labels = ["plan (Gemini Flash)", "synthesize (Gemini Flash)"]
    for i, c in enumerate(call_log):
        label = labels[i] if i < len(labels) else f"call_{i+1}"
        print(
            f"  {label:<28} {c['latency_ms']:>9.0f}ms"
            f" {c['prompt_tokens']:>8} {c['completion_tokens']:>8} {c['total_tokens']:>8}"
        )

    total_prompt = sum(c["prompt_tokens"] for c in call_log)
    total_compl  = sum(c["completion_tokens"] for c in call_log)
    total_tokens = sum(c["total_tokens"] for c in call_log)

    print(f"  {'─'*28} {'─'*10} {'─'*8} {'─'*8} {'─'*8}")
    print(
        f"  {'TOTAL':<28} {t_wall:>9.0f}ms"
        f" {total_prompt:>8} {total_compl:>8} {total_tokens:>8}"
    )
    print("─" * 62)
    print()

    # Gemini Flash pricing (as of 2025): $0.075/1M input, $0.30/1M output
    cost_usd = (total_prompt * 0.075 + total_compl * 0.30) / 1_000_000
    print(f"  Estimated cost : ${cost_usd:.5f}  (Gemini 2.0 Flash pricing)")
    print(f"  Wall-clock time: {t_wall:.0f}ms")
    print(f"  API calls      : {len(call_log)}")
    print()
    print("─" * 62)
    print("  REPORT (truncated to first 800 chars)")
    print("─" * 62)
    print()
    print(report[:800] + ("..." if len(report) > 800 else ""))
    print()
    print("=" * 62)
    print("  Benchmark complete.")
    print("=" * 62)
    print()

if __name__ == "__main__":
    asyncio.run(main())
