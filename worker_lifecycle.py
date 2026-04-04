"""
Worker Lifecycle — Agent state machine with event journal.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tracks each agent through a well-defined lifecycle:
  Spawning → Initializing → Ready → Running → (Blocked | Finished | Failed)

Every state transition is journaled as a WorkerEvent.
Enables: dashboards, stale detection, policy decisions.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import time
from logger import setup_logger

logger = setup_logger("WorkerLifecycle")


class WorkerStatus(Enum):
    """Agent lifecycle states."""
    SPAWNING      = auto()  # Being constructed
    INITIALIZING  = auto()  # Loading config, connecting to services
    READY         = auto()  # Idle, waiting for work
    RUNNING       = auto()  # Executing a task
    BLOCKED       = auto()  # Waiting on external dependency / permission
    FINISHED      = auto()  # Task completed, can be recycled
    FAILED        = auto()  # Crashed or unrecoverable error
    TERMINATED    = auto()  # Deliberately shut down


# Valid state transitions
_VALID_TRANSITIONS: dict[WorkerStatus, set[WorkerStatus]] = {
    WorkerStatus.SPAWNING:     {WorkerStatus.INITIALIZING, WorkerStatus.FAILED},
    WorkerStatus.INITIALIZING: {WorkerStatus.READY, WorkerStatus.FAILED},
    WorkerStatus.READY:        {WorkerStatus.RUNNING, WorkerStatus.TERMINATED},
    WorkerStatus.RUNNING:      {WorkerStatus.READY, WorkerStatus.BLOCKED,
                                 WorkerStatus.FINISHED, WorkerStatus.FAILED},
    WorkerStatus.BLOCKED:      {WorkerStatus.RUNNING, WorkerStatus.FAILED,
                                 WorkerStatus.TERMINATED},
    WorkerStatus.FINISHED:     {WorkerStatus.READY, WorkerStatus.TERMINATED},
    WorkerStatus.FAILED:       {WorkerStatus.INITIALIZING, WorkerStatus.TERMINATED},
}


@dataclass
class WorkerEvent:
    """A single lifecycle transition event."""
    agent_name: str
    from_status: WorkerStatus
    to_status: WorkerStatus
    reason: str = ""
    task_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "from": self.from_status.name,
            "to": self.to_status.name,
            "reason": self.reason,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
        }


@dataclass
class WorkerState:
    """Current state of a single agent/worker."""
    agent_name: str
    status: WorkerStatus = WorkerStatus.SPAWNING
    current_task_id: str = ""
    last_transition: float = field(default_factory=time.time)
    error_count: int = 0
    tasks_completed: int = 0

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_transition

    @property
    def is_active(self) -> bool:
        return self.status in (WorkerStatus.RUNNING, WorkerStatus.BLOCKED)

    @property
    def is_terminal(self) -> bool:
        return self.status in (WorkerStatus.TERMINATED,)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "status": self.status.name,
            "current_task": self.current_task_id,
            "idle_seconds": round(self.idle_seconds, 1),
            "error_count": self.error_count,
            "tasks_completed": self.tasks_completed,
        }


class WorkerLifecycleManager:
    """Manages lifecycle state machines for all agents."""

    def __init__(self):
        self._workers: dict[str, WorkerState] = {}
        self._journal: list[WorkerEvent] = []
        self._max_journal: int = 1000

    def register(self, agent_name: str) -> WorkerState:
        """Register a new agent, starting in SPAWNING state."""
        ws = WorkerState(agent_name=agent_name)
        self._workers[agent_name] = ws
        logger.info(f"Registered worker: {agent_name}")
        return ws

    def transition(self, agent_name: str, to_status: WorkerStatus,
                   reason: str = "", task_id: str = "") -> bool:
        """Transition an agent to a new status. Returns False if invalid."""
        ws = self._workers.get(agent_name)
        if not ws:
            logger.warning(f"Unknown agent: {agent_name}")
            return False

        valid = _VALID_TRANSITIONS.get(ws.status, set())
        if to_status not in valid:
            logger.warning(
                f"Invalid transition for {agent_name}: "
                f"{ws.status.name} → {to_status.name} "
                f"(valid: {[s.name for s in valid]})")
            return False

        event = WorkerEvent(
            agent_name=agent_name,
            from_status=ws.status,
            to_status=to_status,
            reason=reason,
            task_id=task_id or ws.current_task_id,
        )

        # Update state
        old = ws.status
        ws.status = to_status
        ws.last_transition = time.time()

        if to_status == WorkerStatus.RUNNING:
            ws.current_task_id = task_id
        elif to_status == WorkerStatus.FINISHED:
            ws.tasks_completed += 1
            ws.current_task_id = ""
        elif to_status == WorkerStatus.FAILED:
            ws.error_count += 1
        elif to_status == WorkerStatus.READY:
            ws.current_task_id = ""

        # Journal
        self._journal.append(event)
        if len(self._journal) > self._max_journal:
            self._journal = self._journal[-self._max_journal:]

        logger.debug(f"{agent_name}: {old.name} → {to_status.name} ({reason})")
        return True

    # ── Convenience transitions ────────────────────────────────
    def mark_initializing(self, name: str):
        self.transition(name, WorkerStatus.INITIALIZING, "agent loading")

    def mark_ready(self, name: str):
        self.transition(name, WorkerStatus.READY, "initialization complete")

    def mark_running(self, name: str, task_id: str = ""):
        self.transition(name, WorkerStatus.RUNNING, "task assigned", task_id)

    def mark_blocked(self, name: str, reason: str = ""):
        self.transition(name, WorkerStatus.BLOCKED, reason)

    def mark_finished(self, name: str):
        self.transition(name, WorkerStatus.FINISHED, "task completed")

    def mark_failed(self, name: str, reason: str = ""):
        self.transition(name, WorkerStatus.FAILED, reason)

    def mark_terminated(self, name: str):
        self.transition(name, WorkerStatus.TERMINATED, "shutdown")

    # ── Queries ────────────────────────────────────────────────
    def get_status(self, agent_name: str) -> Optional[WorkerStatus]:
        ws = self._workers.get(agent_name)
        return ws.status if ws else None

    def get_state(self, agent_name: str) -> Optional[WorkerState]:
        return self._workers.get(agent_name)

    def active_workers(self) -> list[WorkerState]:
        return [w for w in self._workers.values() if w.is_active]

    def idle_workers(self, threshold_seconds: float = 60) -> list[WorkerState]:
        """Workers that have been idle longer than threshold."""
        return [
            w for w in self._workers.values()
            if w.status == WorkerStatus.READY and w.idle_seconds > threshold_seconds
        ]

    def stale_workers(self, threshold_seconds: float = 120) -> list[WorkerState]:
        """Workers stuck in RUNNING or BLOCKED for too long."""
        return [
            w for w in self._workers.values()
            if w.status in (WorkerStatus.RUNNING, WorkerStatus.BLOCKED)
            and w.idle_seconds > threshold_seconds
        ]

    def failed_workers(self) -> list[WorkerState]:
        return [w for w in self._workers.values() if w.status == WorkerStatus.FAILED]

    def journal(self, agent_name: str | None = None,
                limit: int = 50) -> list[dict]:
        events = self._journal
        if agent_name:
            events = [e for e in events if e.agent_name == agent_name]
        return [e.to_dict() for e in events[-limit:]]

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for w in self._workers.values():
            k = w.status.name
            counts[k] = counts.get(k, 0) + 1
        return {
            "total_workers": len(self._workers),
            "by_status": counts,
            "active": len(self.active_workers()),
            "stale": len(self.stale_workers()),
            "failed": len(self.failed_workers()),
            "total_events": len(self._journal),
        }

    def dashboard(self) -> list[dict]:
        """Quick overview of all workers."""
        return [w.to_dict() for w in self._workers.values()]
