"""
Simple Vertex AI integration — plain OpenAI SDK, no JamJet.

Shows the raw approach before you add @task/@tool.
Compare this with workflow.py to see what JamJet removes.

Run:
    python simple.py
"""

import asyncio
import os
import subprocess
from pathlib import Path

# Load .env
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if v:
                os.environ.setdefault(k.strip(), v.strip())

# ── Vertex AI config ───────────────────────────────────────────────────────
project  = os.environ["VERTEX_PROJECT"]
location = os.environ.get("VERTEX_LOCATION", "us-central1")

base_url = (
    f"https://{location}-aiplatform.googleapis.com"
    f"/v1beta1/projects/{project}/locations/{location}/endpoints/openapi"
)

# Access token (refresh every ~55 min in production via google-auth)
token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()

# ── OpenAI-compatible client pointed at Vertex AI ─────────────────────────
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=token, base_url=base_url)

MODEL = "google/gemini-2.0-flash-001"


# ── Approach 1: single call ────────────────────────────────────────────────

async def single_call(question: str) -> str:
    """Simplest possible — one prompt, one response."""
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content or ""


# ── Approach 2: with a tool ────────────────────────────────────────────────

async def call_with_tool(question: str) -> str:
    """Single call with a tool — manual tool loop."""
    from datetime import date

    tools = [
        {
            "type": "function",
            "function": {
                "name": "current_date",
                "description": "Returns today's date.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }
    ]

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": question},
    ]

    while True:
        response = await client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        messages.append(msg)
        for tc in msg.tool_calls:
            if tc.function.name == "current_date":
                result = date.today().isoformat()
            else:
                result = "unknown tool"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    print(f"Model : {MODEL}")
    print(f"Endpoint: {base_url}")
    print()

    # 1. Simple call
    print("── Approach 1: single call ──────────────────────")
    answer = await single_call("What is the Model Context Protocol (MCP)?")
    print(answer[:400])
    print()

    # 2. With a tool
    print("── Approach 2: with tool (current_date) ─────────")
    answer = await call_with_tool("What year is it and what should I know about AI agents this year?")
    print(answer[:400])
    print()

    print("Done. Compare with workflow.py to see the JamJet @task/@tool version.")


if __name__ == "__main__":
    asyncio.run(main())
