"""
Task Graph — DAG-based task dependency management.
Supports topological sort, cycle detection, and parallel group extraction.
"""
import uuid
from collections import defaultdict, deque
from enum import Enum
from datetime import datetime
from logger import setup_logger

logger = setup_logger("TaskGraph")


class TaskStatus(str, Enum):
    PENDING   = "pending"
    READY     = "ready"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    SKIPPED   = "skipped"
    BLOCKED   = "blocked"


class Task:
    def __init__(self, name: str, agent: str = "planner", priority: int = 5,
                 data: dict = None, depends_on: list = None, tags: list = None,
                 timeout: int = 300, max_retries: int = 2):
        self.id           = str(uuid.uuid4())[:8]
        self.name         = name
        self.agent        = agent
        self.priority     = priority
        self.data         = data or {}
        self.depends_on   = depends_on or []
        self.tags         = tags or []
        self.timeout      = timeout
        self.max_retries  = max_retries
        self.retries      = 0
        self.status       = TaskStatus.PENDING
        self.result       = None
        self.error        = None
        self.created_at   = datetime.now().isoformat()
        self.started_at   = None
        self.completed_at = None
        self.duration_s   = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def mark_running(self):
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def mark_done(self, result=None):
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now().isoformat()
        if self.started_at:
            from datetime import datetime as dt
            s = dt.fromisoformat(self.started_at)
            self.duration_s = round((dt.now() - s).total_seconds(), 2)

    def mark_failed(self, error: str):
        self.error = error
        if self.retries < self.max_retries:
            self.retries += 1
            self.status = TaskStatus.PENDING
        else:
            self.status = TaskStatus.FAILED

    def __repr__(self):
        return f"Task(id={self.id}, name={self.name!r}, agent={self.agent}, status={self.status})"


class TaskGraph:
    """Directed Acyclic Graph of tasks with dependency resolution."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._adj:   dict[str, list] = defaultdict(list)  # id → [dependent ids]

    def add(self, task_or_dict) -> Task:
        if isinstance(task_or_dict, dict):
            t = Task(
                name       = task_or_dict.get("name", "unnamed"),
                agent      = task_or_dict.get("agent", "planner"),
                priority   = task_or_dict.get("priority", 5),
                data       = task_or_dict.get("data", {}),
                depends_on = task_or_dict.get("depends_on", []),
                tags       = task_or_dict.get("tags", []),
                timeout    = task_or_dict.get("timeout", 300),
            )
        else:
            t = task_or_dict

        self._tasks[t.id] = t
        for dep_id in t.depends_on:
            self._adj[dep_id].append(t.id)

        logger.debug(f"Task added to graph: {t}")
        return t

    def add_many(self, items: list) -> list:
        return [self.add(i) for i in items]

    def get_ready(self) -> list[Task]:
        """Tasks whose dependencies are all completed."""
        completed = {tid for tid, t in self._tasks.items()
                     if t.status == TaskStatus.COMPLETED}
        ready = []
        for t in self._tasks.values():
            if t.status == TaskStatus.PENDING:
                if all(dep in completed for dep in t.depends_on):
                    ready.append(t)
        ready.sort(key=lambda t: t.priority)
        return ready

    def get_parallel_groups(self) -> list[list[Task]]:
        """Return tasks grouped by execution level (topological layers)."""
        in_degree = defaultdict(int)
        for t in self._tasks.values():
            for dep in t.depends_on:
                in_degree[t.id] += 1

        queue  = deque([t for t in self._tasks.values() if in_degree[t.id] == 0])
        groups = []

        while queue:
            group = list(queue)
            queue.clear()
            groups.append(sorted(group, key=lambda t: t.priority))
            for t in group:
                for dependent_id in self._adj.get(t.id, []):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        dep_task = self._tasks.get(dependent_id)
                        if dep_task:
                            queue.append(dep_task)

        return groups

    def has_cycle(self) -> bool:
        visited, rec_stack = set(), set()
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for nb in self._adj.get(node, []):
                if nb not in visited:
                    if dfs(nb): return True
                elif nb in rec_stack:
                    return True
            rec_stack.discard(node)
            return False
        return any(dfs(n) for n in self._tasks if n not in visited)

    def is_complete(self) -> bool:
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)
                   for t in self._tasks.values())

    def has_pending(self) -> bool:
        return any(t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
                   for t in self._tasks.values())

    def summary(self) -> dict:
        counts = defaultdict(int)
        for t in self._tasks.values():
            counts[t.status] += 1
        return dict(counts)

    def get(self, task_id: str) -> Task:
        return self._tasks.get(task_id)

    def all_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def failed_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.FAILED]

    def completed_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]

    def print_summary(self):
        s = self.summary()
        parts = [f"{status}={count}" for status, count in s.items()]
        print(f"\n📊 Task Graph: {' | '.join(parts)}\n")
