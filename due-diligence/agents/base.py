"""
agents/base.py — BaseA2AAgent

Every specialized agent in this example inherits from BaseA2AAgent.
It provides:
  - An aiohttp HTTP server implementing the A2A protocol subset:
      GET  /.well-known/agent.json  →  Agent Card
      POST /a2a/tasks               →  Submit a task (returns {task_id, status})
      GET  /a2a/tasks/{id}          →  Poll for result
  - In-memory task state (sufficient for a demo; swap for Redis/Postgres in production)
  - Structured logging via print() (swap for structlog/OpenTelemetry in production)

The A2A protocol spec used here is the community-published subset from Google's
April 2025 specification, covering the core task lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class AgentSkill:
    """A single capability advertised in the Agent Card."""
    id: str
    name: str
    description: str
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "inputModes": self.input_modes,
            "outputModes": self.output_modes,
        }


@dataclass
class Task:
    """In-flight or completed A2A task."""
    task_id: str
    skill_id: str
    input: str
    status: str = "pending"          # pending | running | completed | failed
    output: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    metadata: dict = field(default_factory=dict)  # telemetry, token counts, etc.

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "skill_id": self.skill_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ── Base class ─────────────────────────────────────────────────────────────────

class BaseA2AAgent(ABC):
    """
    Abstract base for A2A-compliant agents.

    Subclasses must implement:
      - agent_id, agent_name, agent_description, agent_version (class attrs)
      - skills (list[AgentSkill])
      - execute(task: Task) → None  (modifies task.output / task.status in place)
    """

    # Subclasses override these:
    agent_id: str = "base-agent"
    agent_name: str = "Base Agent"
    agent_description: str = "A base A2A agent."
    agent_version: str = "1.0.0"
    agent_port: int = 8000
    skills: list[AgentSkill] = []

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._app = self._build_app()

    # ── Agent Card ─────────────────────────────────────────────────────────────

    def agent_card(self) -> dict:
        """Returns the A2A Agent Card as a dict (served at /.well-known/agent.json)."""
        return {
            "id": self.agent_id,
            "name": self.agent_name,
            "description": self.agent_description,
            "version": self.agent_version,
            "url": f"http://localhost:{self.agent_port}",
            "skills": [s.to_dict() for s in self.skills],
        }

    # ── Abstract: subclasses implement task execution ──────────────────────────

    @abstractmethod
    async def execute(self, task: Task) -> None:
        """
        Execute the task. Set task.output and task.status = 'completed'.
        On error, set task.status = 'failed' and task.error.
        May also populate task.metadata with telemetry (tokens, latency, etc.)
        """

    # ── HTTP handlers ──────────────────────────────────────────────────────────

    async def _handle_agent_card(self, request: web.Request) -> web.Response:
        return web.json_response(self.agent_card())

    async def _handle_submit_task(self, request: web.Request) -> web.Response:
        """POST /a2a/tasks — accepts {skill_id, input} and returns {task_id, status}."""
        try:
            body: dict[str, Any] = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON body"}, status=400)

        skill_id = body.get("skill_id", "")
        input_text = body.get("input", "")

        if not skill_id or not input_text:
            return web.json_response(
                {"error": "missing required fields: skill_id, input"}, status=400
            )

        # Validate skill_id
        valid_skill_ids = {s.id for s in self.skills}
        if skill_id not in valid_skill_ids:
            return web.json_response(
                {"error": f"unknown skill_id '{skill_id}'. Valid: {sorted(valid_skill_ids)}"},
                status=400,
            )

        task_id = str(uuid.uuid4())
        task = Task(task_id=task_id, skill_id=skill_id, input=input_text)
        self._tasks[task_id] = task

        # Run task asynchronously so the HTTP response returns immediately.
        # The caller polls GET /a2a/tasks/{id} for the result.
        asyncio.create_task(self._run_task(task))

        print(f"[{self.agent_id}] task {task_id[:8]} submitted (skill={skill_id})")
        return web.json_response({"task_id": task_id, "status": "pending"}, status=202)

    async def _handle_get_task(self, request: web.Request) -> web.Response:
        """GET /a2a/tasks/{id} — returns current task state."""
        task_id = request.match_info["task_id"]
        task = self._tasks.get(task_id)
        if task is None:
            return web.json_response({"error": "task not found"}, status=404)
        return web.json_response(task.to_dict())

    # ── Task lifecycle ─────────────────────────────────────────────────────────

    async def _run_task(self, task: Task) -> None:
        """Mark task running, call execute(), catch errors, mark completed/failed."""
        task.status = "running"
        try:
            t0 = time.perf_counter()
            await self.execute(task)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            task.status = "completed"
            task.completed_at = time.time()
            task.metadata["wall_clock_ms"] = round(elapsed_ms, 1)
            print(
                f"[{self.agent_id}] task {task.task_id[:8]} completed "
                f"in {elapsed_ms:.0f}ms"
            )
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            task.completed_at = time.time()
            print(f"[{self.agent_id}] task {task.task_id[:8]} FAILED: {exc}")

    # ── Server ─────────────────────────────────────────────────────────────────

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/.well-known/agent.json", self._handle_agent_card)
        app.router.add_post("/a2a/tasks", self._handle_submit_task)
        app.router.add_get("/a2a/tasks/{task_id}", self._handle_get_task)
        return app

    async def start(self) -> None:
        """Start the aiohttp server on self.agent_port."""
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.agent_port)
        await site.start()
        print(f"[{self.agent_id}] listening on http://localhost:{self.agent_port}")

    def run(self) -> None:
        """Convenience: run agent as standalone process (used for direct invocation)."""
        asyncio.run(self._run_standalone())

    async def _run_standalone(self) -> None:
        await self.start()
        print(f"[{self.agent_id}] Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()  # block forever
        except asyncio.CancelledError:
            pass
