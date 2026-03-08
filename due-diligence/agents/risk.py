"""
agents/risk.py — Risk Assessment Agent

Synthesizes the outputs from the Financial Agent and Market Agent into a
final investment risk score and recommendation.

This agent does NOT do RAG — it receives pre-processed intelligence from the
other two agents as its input. Its job is structured reasoning over the
synthesized inputs:
  1. Read the financial analysis
  2. Read the market analysis
  3. Apply a structured risk scoring rubric
  4. Produce an investment recommendation with confidence level

The risk scoring rubric covers 6 dimensions:
  - Financial health (revenue, margins, burn)
  - Market position (moat, competitive dynamics)
  - Execution risk (team, product, roadmap)
  - Regulatory & legal risk
  - Technology & platform risk
  - Capital & funding risk

Each dimension is scored 1–5 (1=high risk, 5=low risk). A weighted composite
yields the overall risk rating: LOW / MEDIUM / HIGH / VERY HIGH.
"""

from __future__ import annotations

import os
import time

from openai import AsyncOpenAI

from .base import AgentSkill, BaseA2AAgent, Task

# ── Configuration ──────────────────────────────────────────────────────────────

AGENT_PORT = 7703
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Risk scoring rubric baked into the system prompt.
# The LLM applies this rubric to the synthesized financial + market inputs.
RISK_RUBRIC = """
RISK SCORING RUBRIC (score each dimension 1–5, where 1=highest risk, 5=lowest risk):

1. Financial Health (weight: 25%)
   5 = Profitable or path-to-profit <18 months, healthy NRR >120%, low burn multiple
   3 = Growing revenue, moderate burn, negative but improving margins
   1 = High burn, declining growth, cash runway <12 months

2. Market Position (weight: 20%)
   5 = #1 or strong #2 with durable moat, high switching costs
   3 = Competitive position established but contested
   1 = No clear moat, commoditized market, losing share

3. Execution Risk (weight: 20%)
   5 = Proven team, consistent delivery, low key-person concentration
   3 = Strong team but dependent on 1-2 key individuals
   1 = Unproven leadership, high turnover risk, missed milestones

4. Regulatory & Legal Risk (weight: 15%)
   5 = Operates in well-understood regulatory environment, compliant
   3 = Regulatory uncertainty, possible compliance costs ahead
   1 = Active regulatory investigations, existential legal risk

5. Technology & Platform Risk (weight: 10%)
   5 = Proprietary technology with deep moat, not easily replicated
   3 = Strong technology but at risk from open-source or larger players
   1 = Technology easily replicated, platform dependency (e.g., single cloud)

6. Capital & Funding Risk (weight: 10%)
   5 = Well-capitalized (>24 months runway), strategic investors locked in
   3 = 12–24 months runway, next round uncertain but feasible
   1 = <12 months runway, funding round uncertain, hostile investor relations

COMPOSITE SCORE:
  Weighted average → Risk Rating:
  4.0–5.0: LOW RISK — Invest / Strong Consideration
  3.0–3.9: MEDIUM RISK — Invest with conditions / Monitor closely
  2.0–2.9: HIGH RISK — Only invest with significant discount / deep due diligence
  1.0–1.9: VERY HIGH RISK — Avoid or pass
"""


# ── Agent ──────────────────────────────────────────────────────────────────────

class RiskAgent(BaseA2AAgent):
    """
    Synthesizes financial + market intelligence into an investment risk score.

    Skill: assess_risk
      Input:  combined financial + market analysis (structured text from other agents)
      Output: risk scorecard, composite rating, and investment recommendation
    """

    agent_id = "risk-agent"
    agent_name = "Risk Assessment Agent"
    agent_description = (
        "Synthesizes financial analysis and market intelligence into a structured "
        "investment risk scorecard. Scores 6 risk dimensions and produces a composite "
        "rating (LOW/MEDIUM/HIGH/VERY HIGH) with an investment recommendation."
    )
    agent_version = "1.0.0"
    agent_port = AGENT_PORT

    skills = [
        AgentSkill(
            id="assess_risk",
            name="Assess Investment Risk",
            description=(
                "Synthesizes pre-processed financial and market intelligence into "
                "a structured risk scorecard and investment recommendation."
            ),
        )
    ]

    def __init__(self) -> None:
        super().__init__()
        self._client = AsyncOpenAI()

    async def execute(self, task: Task) -> None:
        """Apply risk rubric over synthesized inputs and produce investment recommendation."""

        system_prompt = (
            "You are a senior investment committee analyst at a top-tier venture capital firm. "
            "You receive synthesized financial and market intelligence from specialist research agents "
            "and produce a structured investment risk assessment.\n\n"
            f"{RISK_RUBRIC}\n\n"
            "Output format — use EXACTLY this structure:\n\n"
            "## Risk Scorecard\n"
            "| Dimension | Score (1–5) | Rationale |\n"
            "|-----------|------------|----------|\n"
            "| Financial Health | X.X | <one line> |\n"
            "| Market Position | X.X | <one line> |\n"
            "| Execution Risk | X.X | <one line> |\n"
            "| Regulatory & Legal | X.X | <one line> |\n"
            "| Technology & Platform | X.X | <one line> |\n"
            "| Capital & Funding | X.X | <one line> |\n\n"
            "## Composite Risk Score\n"
            "**Weighted Score:** X.X / 5.0\n"
            "**Risk Rating:** [LOW / MEDIUM / HIGH / VERY HIGH]\n\n"
            "## Investment Recommendation\n"
            "<2–3 paragraph analysis covering: why this rating, key upside catalysts, "
            "key risks that would change the rating, and the recommended investor action>\n\n"
            "## Key Conditions / Covenants (if investing)\n"
            "<3–5 bullet points: conditions under which investment should be structured>\n\n"
            "## Confidence Level\n"
            "**Confidence:** [HIGH / MEDIUM / LOW] — <one sentence explaining data quality and gaps>"
        )

        user_prompt = (
            f"Please assess the investment risk for the following company based on "
            f"the synthesized research below.\n\n{task.input}"
        )

        t_llm_start = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # slightly higher for nuanced risk reasoning
        )
        llm_latency_ms = (time.perf_counter() - t_llm_start) * 1000

        task.output = response.choices[0].message.content

        usage = response.usage
        task.metadata.update({
            "model": MODEL,
            "llm_latency_ms": round(llm_latency_ms, 1),
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        })
