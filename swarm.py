"""
AMRIT GODMODE — Swarm / Multi-Agent Queen-Worker System
========================================================
Lightweight queen/worker pattern inspired by bee colonies:
- Queen: plans, delegates, monitors, re-assigns on failure
- Workers: specialized agents executing tasks in parallel
- Consensus: simple majority voting for critical decisions
- Mesh: workers can communicate peer-to-peer via event bus

Design: Zero-dependency, uses existing EventBus + BaseAgent.
Google lightweight principle: no heavy frameworks, pure asyncio.
"""

import asyncio
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from event_bus import EventBus
from state_manager import StateManager
from logger import setup_logger

logger = setup_logger("swarm")


class WorkerState(Enum):
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    STOPPED = "stopped"


class SwarmTopology(Enum):
    HIERARCHY = "hierarchy"   # queen → workers (default)
    MESH = "mesh"             # peer-to-peer
    PIPELINE = "pipeline"     # worker → worker chain


@dataclass
class WorkerInfo:
    agent_name: str
    state: WorkerState = WorkerState.IDLE
    current_task: Optional[dict] = None
    completed: int = 0
    failed: int = 0
    score: float = 1.0       # performance score (0-1)
    started_at: float = 0.0


@dataclass
class SwarmTask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    agent: str = "coder"
    data: dict = field(default_factory=dict)
    priority: int = 5
    depends_on: list = field(default_factory=list)
    status: str = "pending"   # pending, running, done, failed
    result: Optional[dict] = None
    retries: int = 0
    max_retries: int = 2


class Queen:
    """
    Queen agent — plans, delegates, monitors swarm workers.
    Lightweight: no extra LLM calls for coordination, pure logic.
    """

    def __init__(self, event_bus: EventBus, agents: dict, state: StateManager):
        self.bus = event_bus
        self.agents = agents         # name → BaseAgent
        self.state = state
        self.workers: dict[str, WorkerInfo] = {}
        self.task_queue: list[SwarmTask] = []
        self.completed_tasks: list[SwarmTask] = []
        self.topology = SwarmTopology.HIERARCHY
        self.max_parallel = 4        # max concurrent workers
        self._running = False

        # Register all agents as workers
        for name in agents:
            self.workers[name] = WorkerInfo(agent_name=name)

        # Listen for worker events
        self.bus.subscribe("swarm.task.done", self._on_task_done)
        self.bus.subscribe("swarm.task.failed", self._on_task_failed)
        self.bus.subscribe("swarm.worker.report", self._on_worker_report)

    async def spawn_swarm(self, objective: str, tasks: list[dict]) -> dict:
        """
        Main entry: decompose objective into tasks, run swarm.
        tasks = [{"name": "...", "agent": "coder", "data": {...}, "priority": 1, "depends_on": []}]
        """
        self._running = True
        logger.info(f"🐝 Queen spawning swarm: {objective}")
        logger.info(f"   Workers: {list(self.workers.keys())}")
        logger.info(f"   Tasks: {len(tasks)}, Topology: {self.topology.value}")

        # Convert to SwarmTasks
        self.task_queue = []
        for t in tasks:
            st = SwarmTask(
                name=t.get("name", "unnamed"),
                agent=t.get("agent", "coder"),
                data=t.get("data", {}),
                priority=t.get("priority", 5),
                depends_on=t.get("depends_on", []),
            )
            self.task_queue.append(st)

        # Sort by priority (lower = higher priority)
        self.task_queue.sort(key=lambda x: x.priority)

        # Run the swarm loop
        results = await self._run_loop()

        self._running = False
        summary = {
            "objective": objective,
            "total": len(tasks),
            "completed": len([t for t in self.task_queue if t.status == "done"]),
            "failed": len([t for t in self.task_queue if t.status == "failed"]),
            "results": results,
            "worker_stats": {
                n: {"completed": w.completed, "failed": w.failed, "score": round(w.score, 2)}
                for n, w in self.workers.items()
                if w.completed + w.failed > 0
            },
        }
        logger.info(f"🐝 Swarm complete: {summary['completed']}/{summary['total']} done")
        await self.bus.publish("swarm.complete", summary, source="queen")
        return summary

    async def _run_loop(self) -> list[dict]:
        """Core swarm execution loop — lightweight async scheduling."""
        results = []
        running_tasks: dict[str, asyncio.Task] = {}  # task_id → asyncio.Task

        while self._running:
            # Check if all tasks are done/failed
            pending = [t for t in self.task_queue if t.status in ("pending", "running")]
            if not pending and not running_tasks:
                break

            # Find ready tasks (dependencies met)
            ready = [
                t for t in self.task_queue
                if t.status == "pending" and self._deps_met(t)
            ]

            # Assign to idle workers (up to max_parallel)
            for task in ready:
                if len(running_tasks) >= self.max_parallel:
                    break

                worker = self._pick_worker(task.agent)
                if not worker:
                    continue

                task.status = "running"
                worker.state = WorkerState.BUSY
                worker.current_task = {"id": task.id, "name": task.name}
                worker.started_at = time.time()

                logger.info(f"   🔧 [{worker.agent_name}] ← {task.name}")
                atask = asyncio.create_task(
                    self._execute_worker(worker, task)
                )
                running_tasks[task.id] = atask

            # Wait for any task to complete
            if running_tasks:
                done, _ = await asyncio.wait(
                    running_tasks.values(),
                    timeout=2.0,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for completed_task in done:
                    result = completed_task.result()
                    if result:
                        results.append(result)
                        # Remove from running
                        tid = result.get("task_id")
                        running_tasks.pop(tid, None)
            else:
                await asyncio.sleep(0.1)

        return results

    async def _execute_worker(self, worker: WorkerInfo, task: SwarmTask) -> dict:
        """Execute a single task on a worker agent."""
        agent = self.agents.get(worker.agent_name)
        if not agent:
            task.status = "failed"
            worker.state = WorkerState.IDLE
            worker.failed += 1
            return {"task_id": task.id, "status": "error", "error": f"Agent {worker.agent_name} not found"}

        try:
            # Pass task data nested under "data" key — agents expect task["data"]
            task_payload = {
                "name": task.name,
                "data": {
                    "action": task.data.get("action", "generate"),
                    "spec": task.data.get("spec", task.name),
                    "goal": task.data.get("goal", task.name),
                    **task.data,
                },
            }
            result = await asyncio.wait_for(
                agent.execute(task_payload),
                timeout=300,
            )
            task.status = "done"
            task.result = result
            worker.state = WorkerState.IDLE
            worker.current_task = None
            worker.completed += 1
            worker.score = min(1.0, worker.score + 0.05)

            await self.bus.publish("swarm.task.done", {
                "task_id": task.id, "task_name": task.name,
                "worker": worker.agent_name, "result": result,
            }, source="queen")

            return {"task_id": task.id, "task_name": task.name, "status": "done", "result": result}

        except asyncio.TimeoutError:
            logger.warning(f"   ⏰ [{worker.agent_name}] timeout: {task.name}")
            return await self._handle_failure(worker, task, "timeout")

        except Exception as e:
            logger.error(f"   ❌ [{worker.agent_name}] error: {e}")
            return await self._handle_failure(worker, task, str(e))

    async def _handle_failure(self, worker: WorkerInfo, task: SwarmTask, error: str) -> dict:
        """Handle task failure — retry or re-assign."""
        worker.state = WorkerState.IDLE
        worker.current_task = None
        worker.failed += 1
        worker.score = max(0.0, worker.score - 0.2)

        if task.retries < task.max_retries:
            task.retries += 1
            task.status = "pending"
            logger.info(f"   🔄 Retry {task.retries}/{task.max_retries}: {task.name}")
            await self.bus.publish("swarm.task.retry", {
                "task_id": task.id, "retry": task.retries, "error": error,
            }, source="queen")
            return {}
        else:
            task.status = "failed"
            await self.bus.publish("swarm.task.failed", {
                "task_id": task.id, "task_name": task.name, "error": error,
            }, source="queen")
            return {"task_id": task.id, "status": "failed", "error": error}

    def _deps_met(self, task: SwarmTask) -> bool:
        """Check if all dependencies are completed."""
        if not task.depends_on:
            return True
        done_names = {t.name for t in self.task_queue if t.status == "done"}
        return all(dep in done_names for dep in task.depends_on)

    def _pick_worker(self, preferred_agent: str) -> Optional[WorkerInfo]:
        """Pick best available worker — prefer the requested agent type."""
        # Try preferred agent first
        w = self.workers.get(preferred_agent)
        if w and w.state == WorkerState.IDLE:
            return w

        # Fallback: any idle worker with highest score
        idle = [
            w for w in self.workers.values()
            if w.state == WorkerState.IDLE
        ]
        if idle:
            return max(idle, key=lambda x: x.score)
        return None

    async def _on_task_done(self, event):
        pass  # Already handled in _execute_worker

    async def _on_task_failed(self, event):
        pass  # Already handled in _handle_failure

    async def _on_worker_report(self, event):
        """Workers can send reports via mesh communication."""
        data = event.data if hasattr(event, 'data') else event
        logger.info(f"   📨 Worker report: {data}")

    def get_status(self) -> dict:
        """Current swarm status snapshot."""
        return {
            "running": self._running,
            "topology": self.topology.value,
            "workers": {
                n: {"state": w.state.value, "score": round(w.score, 2),
                    "completed": w.completed, "failed": w.failed}
                for n, w in self.workers.items()
            },
            "queue": {
                "pending": len([t for t in self.task_queue if t.status == "pending"]),
                "running": len([t for t in self.task_queue if t.status == "running"]),
                "done": len([t for t in self.task_queue if t.status == "done"]),
                "failed": len([t for t in self.task_queue if t.status == "failed"]),
            },
        }

    async def vote(self, question: str, voters: list[str] = None) -> dict:
        """
        Simple majority consensus — ask workers to vote on a decision.
        Returns majority answer. Lightweight: one LLM call per voter.
        """
        if voters is None:
            voters = list(self.agents.keys())[:3]  # max 3 voters for speed

        votes = {}
        for name in voters:
            agent = self.agents.get(name)
            if not agent:
                continue
            try:
                answer = await agent.ask_llm(
                    f"Vote YES or NO on: {question}\nAnswer only YES or NO.",
                    max_tokens=10,
                )
                vote = "YES" if "YES" in answer.upper() else "NO"
                votes[name] = vote
            except Exception:
                votes[name] = "ABSTAIN"

        yes_count = sum(1 for v in votes.values() if v == "YES")
        no_count = sum(1 for v in votes.values() if v == "NO")
        decision = "YES" if yes_count > no_count else "NO"

        result = {"question": question, "votes": votes, "decision": decision}
        logger.info(f"🗳️ Consensus: {decision} ({yes_count}Y/{no_count}N)")
        await self.bus.publish("swarm.vote", result, source="queen")
        return result
