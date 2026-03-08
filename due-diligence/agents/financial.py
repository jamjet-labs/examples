"""
agents/financial.py — Financial Research Agent

Implements RAG (Retrieval-Augmented Generation) over knowledge/financials.md.

RAG pipeline:
  1. Load financials.md at startup and chunk by section (## headings)
  2. On each query, score all chunks by keyword overlap with the query
  3. Retrieve the top-3 highest-scoring chunks
  4. Pass chunks as context in the LLM system prompt
  5. Ask the LLM to produce a structured financial analysis

This avoids hallucination on specific financial figures: the LLM is grounded
by real documents rather than parametric memory. In production, replace the
keyword scorer with a vector embedding index (e.g., pgvector, FAISS).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

from .base import AgentSkill, BaseA2AAgent, Task

# ── Configuration ──────────────────────────────────────────────────────────────

AGENT_PORT = 7701
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
KNOWLEDGE_FILE = Path(__file__).parent.parent / "knowledge" / "financials.md"
TOP_K_CHUNKS = 3


# ── RAG: document loading and retrieval ────────────────────────────────────────

def _load_chunks(path: Path) -> list[dict]:
    """
    Parse financials.md into chunks, one per ## section.
    Each chunk: {heading: str, body: str, tokens: list[str]}
    """
    text = path.read_text(encoding="utf-8")
    chunks: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            # Save the previous chunk (only if it has a heading — skip file preamble)
            if current_lines and current_heading:
                body = "\n".join(current_lines).strip()
                chunks.append({
                    "heading": current_heading,
                    "body": body,
                    # Pre-tokenize for fast keyword scoring
                    "tokens": set(re.findall(r"\w+", (current_heading + " " + body).lower())),
                })
            current_heading = line[3:].strip()
            current_lines = []
        elif not line.startswith("# "):  # skip top-level title lines
            current_lines.append(line)

    # Don't forget the last chunk
    if current_lines and current_heading:
        body = "\n".join(current_lines).strip()
        chunks.append({
            "heading": current_heading,
            "body": body,
            "tokens": set(re.findall(r"\w+", (current_heading + " " + body).lower())),
        })

    return chunks


def _retrieve(chunks: list[dict], query: str, k: int = TOP_K_CHUNKS) -> list[dict]:
    """
    Score each chunk by keyword overlap with the query.
    Returns top-k chunks sorted by descending score.

    This is a bag-of-words retrieval model — fast and interpretable for demos.
    Production replacement: embed query + chunks with text-embedding-3-small,
    compute cosine similarity, retrieve top-k.
    """
    query_tokens = set(re.findall(r"\w+", query.lower()))
    scored: list[tuple[float, dict]] = []

    for chunk in chunks:
        # Jaccard-like overlap: |intersection| / |query_tokens|
        # (asymmetric: we care about query coverage, not chunk coverage)
        overlap = len(query_tokens & chunk["tokens"])
        # Boost chunks whose heading directly contains a query word
        heading_tokens = set(re.findall(r"\w+", chunk["heading"].lower()))
        heading_bonus = 2 * len(query_tokens & heading_tokens)
        score = overlap + heading_bonus
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:k] if _ > 0]


# ── Agent ──────────────────────────────────────────────────────────────────────

class FinancialAgent(BaseA2AAgent):
    """
    Answers financial research questions about AI companies using RAG.

    Skill: analyze_financials
      Input:  company name + research question
      Output: structured financial analysis with key metrics and risks
    """

    agent_id = "financial-agent"
    agent_name = "Financial Research Agent"
    agent_description = (
        "Analyzes financial data for AI companies using RAG over a curated "
        "financial knowledge base. Provides revenue, margins, funding history, "
        "unit economics, and key financial risks."
    )
    agent_version = "1.0.0"
    agent_port = AGENT_PORT

    skills = [
        AgentSkill(
            id="analyze_financials",
            name="Analyze Financials",
            description=(
                "RAG-powered financial analysis. Retrieves relevant financial "
                "data and synthesizes it into a structured report."
            ),
        )
    ]

    def __init__(self) -> None:
        super().__init__()
        # Load and chunk the knowledge base at startup
        self._chunks = _load_chunks(KNOWLEDGE_FILE)
        print(f"[{self.agent_id}] loaded {len(self._chunks)} RAG chunks from financials.md")
        # OpenAI client (reads OPENAI_API_KEY + OPENAI_BASE_URL from env)
        self._client = AsyncOpenAI()

    async def execute(self, task: Task) -> None:
        """RAG pipeline: retrieve → augment prompt → call LLM → return analysis."""

        # ── Step 1: Retrieval ────────────────────────────────────────────────
        t_rag_start = time.perf_counter()
        relevant_chunks = _retrieve(self._chunks, task.input)
        rag_latency_ms = (time.perf_counter() - t_rag_start) * 1000

        if not relevant_chunks:
            # Fallback: use all comparative benchmark chunks
            relevant_chunks = [c for c in self._chunks if "Benchmark" in c["heading"]]

        # Format retrieved context
        context_sections = "\n\n---\n\n".join(
            f"### {c['heading']}\n{c['body']}" for c in relevant_chunks
        )
        chunks_used = [c["heading"] for c in relevant_chunks]

        # ── Step 2: LLM call ─────────────────────────────────────────────────
        system_prompt = (
            "You are a senior investment analyst specializing in AI company due diligence. "
            "You have been provided with excerpts from a proprietary financial knowledge base. "
            "Use ONLY the provided context to answer. Do not fabricate numbers. "
            "If information is not in the context, say so explicitly.\n\n"
            "Structure your response as:\n"
            "**Revenue & ARR:** <key figures>\n"
            "**Business Model:** <monetization mechanics>\n"
            "**Unit Economics:** <margins, burn rate, efficiency>\n"
            "**Funding & Valuation:** <history and current valuation>\n"
            "**Key Financial Risks:** <top 3 risks as bullet points>\n"
            "**Analyst View:** <one paragraph synthesis>"
        )
        user_prompt = (
            f"Research question: {task.input}\n\n"
            f"=== RETRIEVED FINANCIAL CONTEXT ===\n{context_sections}\n"
            f"=== END CONTEXT ===\n\n"
            "Provide a structured financial analysis based strictly on the above context."
        )

        t_llm_start = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,  # low temperature for factual financial analysis
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
