"""
Vertex AI + JamJet — research agent using Gemini via the OpenAI-compatible endpoint.

Vertex AI exposes an OpenAI-compatible API, so JamJet works with it out of the box.
Just set two env vars and use any Gemini model as your model string.

Setup:
    gcloud auth application-default login
    export VERTEX_PROJECT=your-gcp-project-id
    export VERTEX_LOCATION=us-central1   # or europe-west4, asia-northeast1, etc.

Run:
    python workflow.py
"""

import asyncio
import os
from pathlib import Path

# Load .env if present
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if v:
                os.environ.setdefault(k.strip(), v.strip())

from jamjet import task, tool

# Vertex AI OpenAI-compatible endpoint — set automatically from env vars.
# JamJet reads OPENAI_API_KEY and OPENAI_BASE_URL the same way the OpenAI SDK does.
project = os.environ["VERTEX_PROJECT"]
location = os.environ.get("VERTEX_LOCATION", "us-central1")

os.environ.setdefault(
    "OPENAI_BASE_URL",
    f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/endpoints/openapi",
)

# Access token from gcloud — rotates every hour.
# In production use google-auth to refresh automatically (see README).
if "OPENAI_API_KEY" not in os.environ:
    import subprocess
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    os.environ["OPENAI_API_KEY"] = token


# ── Tools ──────────────────────────────────────────────────────────────────

@tool
async def current_date() -> str:
    """Return today's date so the agent can reason about recency."""
    from datetime import date
    return date.today().isoformat()


# ── Tasks (agents) ────────────────────────────────────────────────────────

GEMINI_FLASH = "google/gemini-2.0-flash-001"


@task(model=GEMINI_FLASH, tools=[current_date])
async def plan(query: str) -> str:
    """
    You are a research planner. Break the user's query into 3-5 focused
    sub-questions that together will produce a complete answer.
    Return only a numbered list of sub-questions, nothing else.
    """


@task(model=GEMINI_FLASH, tools=[current_date])
async def synthesize(query_and_outline: str) -> str:
    """
    You are a research analyst. Write a thorough, well-structured report
    that addresses the query using the provided outline as your guide.
    Use clear headings. Be concise but complete.
    """


async def main() -> None:
    query = "What are the key trends in AI agents in 2025?"

    print(f"Query: {query}\n")
    print("Planning sub-questions...")
    outline = await plan(query)
    print(f"\nOutline:\n{outline}\n")

    print("Synthesizing report...")
    report = await synthesize(f"Query: {query}\n\nOutline:\n{outline}")
    print(f"\nReport:\n{report}")


if __name__ == "__main__":
    asyncio.run(main())
