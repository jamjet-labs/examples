"""
agents/market.py — Market Intelligence Agent

Answers market positioning and competitive analysis questions by doing RAG
over knowledge/markets.md.

Same RAG pipeline as the Financial Agent but targeting market intelligence:
  - Competitive landscape
  - Market size and growth
  - Moats and differentiation
  - Macro risk factors

In production, this agent would also call live web search APIs (Brave Search,
Serper, Tavily) to supplement the knowledge base with fresh data. For this demo,
the knowledge base provides realistic depth without live API dependencies.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

from .base import AgentSkill, BaseA2AAgent, Task

# ── Configuration ──────────────────────────────────────────────────────────────

AGENT_PORT = 7702
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
KNOWLEDGE_FILE = Path(__file__).parent.parent / "knowledge" / "markets.md"
TOP_K_CHUNKS = 3


# ── RAG helpers (same keyword-overlap approach as financial.py) ────────────────

def _load_chunks(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    chunks: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines and current_heading:
                body = "\n".join(current_lines).strip()
                chunks.append({
                    "heading": current_heading,
                    "body": body,
                    "tokens": set(re.findall(r"\w+", (current_heading + " " + body).lower())),
                })
            current_heading = line[3:].strip()
            current_lines = []
        elif not line.startswith("# "):
            current_lines.append(line)

    if current_lines and current_heading:
        body = "\n".join(current_lines).strip()
        chunks.append({
            "heading": current_heading,
            "body": body,
            "tokens": set(re.findall(r"\w+", (current_heading + " " + body).lower())),
        })

    return chunks


def _retrieve(chunks: list[dict], query: str, k: int = TOP_K_CHUNKS) -> list[dict]:
    query_tokens = set(re.findall(r"\w+", query.lower()))
    scored: list[tuple[float, dict]] = []

    for chunk in chunks:
        overlap = len(query_tokens & chunk["tokens"])
        heading_tokens = set(re.findall(r"\w+", chunk["heading"].lower()))
        heading_bonus = 2 * len(query_tokens & heading_tokens)
        score = overlap + heading_bonus
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:k] if _ > 0]


# ── Agent ──────────────────────────────────────────────────────────────────────

class MarketAgent(BaseA2AAgent):
    """
    Answers market intelligence questions for AI company due diligence.

    Skill: analyze_market
      Input:  company name + market research question
      Output: competitive positioning, market size, moats, macro risks
    """

    agent_id = "market-agent"
    agent_name = "Market Intelligence Agent"
    agent_description = (
        "Provides market intelligence and competitive analysis for AI companies. "
        "Covers market sizing, competitive landscape, strategic moats, and macro "
        "risk factors using a curated market knowledge base."
    )
    agent_version = "1.0.0"
    agent_port = AGENT_PORT

    skills = [
        AgentSkill(
            id="analyze_market",
            name="Analyze Market",
            description=(
                "RAG-powered market and competitive intelligence. Retrieves "
                "relevant market data and synthesizes competitive positioning."
            ),
        )
    ]

    def __init__(self) -> None:
        super().__init__()
        self._chunks = _load_chunks(KNOWLEDGE_FILE)
        print(f"[{self.agent_id}] loaded {len(self._chunks)} RAG chunks from markets.md")
        self._client = AsyncOpenAI()

    async def execute(self, task: Task) -> None:
        """RAG pipeline: retrieve market context → augment → call LLM."""

        # ── Step 1: Retrieval ────────────────────────────────────────────────
        t_rag_start = time.perf_counter()
        relevant_chunks = _retrieve(self._chunks, task.input)
        rag_latency_ms = (time.perf_counter() - t_rag_start) * 1000

        if not relevant_chunks:
            # Fallback: use the overall market size chunk
            relevant_chunks = [c for c in self._chunks if "Market" in c["heading"]][:TOP_K_CHUNKS]

        context_sections = "\n\n---\n\n".join(
            f"### {c['heading']}\n{c['body']}" for c in relevant_chunks
        )
        chunks_used = [c["heading"] for c in relevant_chunks]

        # ── Step 2: LLM call ─────────────────────────────────────────────────
        system_prompt = (
            "You are a senior market analyst specializing in the AI industry. "
            "You have been provided with excerpts from a market intelligence knowledge base. "
            "Use ONLY the provided context. Do not fabricate market data. "
            "If a specific figure is not in the context, say so.\n\n"
            "Structure your response as:\n"
            "**Market Position:** <rank and share in key segments>\n"
            "**Competitive Moats:** <top 3-5 durable advantages>\n"
            "**Key Competitors:** <primary threats and competitive dynamics>\n"
            "**Market Size & Growth:** <TAM, SAM, growth rates>\n"
            "**Strategic Risks:** <top 3 competitive threats>\n"
            "**Analyst View:** <one paragraph synthesis of competitive positioning>"
        )
        user_prompt = (
            f"Research question: {task.input}\n\n"
            f"=== RETRIEVED MARKET INTELLIGENCE CONTEXT ===\n{context_sections}\n"
            f"=== END CONTEXT ===\n\n"
            "Provide a structured market and competitive analysis based strictly on the above context."
        )

        t_llm_start = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        llm_latency_ms = (time.perf_counter() - t_llm_start) * 1000

        task.output = response.choices[0].message.content

        # ── Step 3: Record telemetry ─────────────────────────────────────────
        usage = response.usage
        task.metadata.update({
            "model": MODEL,
            "rag_latency_ms": round(rag_latency_ms, 1),
            "llm_latency_ms": round(llm_latency_ms, 1),
            "chunks_retrieved": len(relevant_chunks),
            "chunks_used": chunks_used,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        })
