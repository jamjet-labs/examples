"""
Specialized A2A agents for investment due diligence.

Each agent is an independent HTTP service implementing the A2A protocol:
  - GET  /.well-known/agent.json  →  Agent Card (discovery)
  - POST /a2a/tasks               →  Submit task
  - GET  /a2a/tasks/{id}          →  Poll for result

Import agents here for use in run.py / benchmark.py.
"""

from .financial import FinancialAgent
from .market import MarketAgent
from .risk import RiskAgent

__all__ = ["FinancialAgent", "MarketAgent", "RiskAgent"]
