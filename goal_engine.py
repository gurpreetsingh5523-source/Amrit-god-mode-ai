# amrit_core/goal_engine.py
import uuid
from datetime import datetime
from typing import Optional


class Goal:
    def __init__(self, description: str, priority: int = 1):
        self.id = str(uuid.uuid4())
        self.description = description
        self.priority = priority
        self.created_at = datetime.now()
        self.status = "pending"   # pending → active → done / failed
        self.tasks = []
        self.result = None
        self.error = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "tasks": self.tasks,
            "result": self.result,
            "error": self.error,
        }

    def __repr__(self):
        return f"<Goal [{self.status}] P{self.priority}: {self.description[:50]}>"


class GoalEngine:
    MAX_TASKS_PER_GOAL = 10
    def __init__(self, planner, memory, agents=None):
        self.goals: list[Goal] = []
        self.planner = planner
        self.memory = memory
        self.agents = agents or {}

    # ─── Goal Management ──────────────────────────────────────

    def add_goal(self, description: str, priority: int = 1) -> Goal:
        goal = Goal(description, priority)
        self.goals.append(goal)
        # ਮੈਮੋਰੀ ਵਿੱਚ ਸੇਵ ਕਰੋ ਤਾਂ ਜੋ restart ਤੋਂ ਬਾਅਦ ਵੀ ਰਹੇ
        self._persist(goal, event="added")
        print(f"[GoalEngine] ✅ Goal added: {goal}")
        return goal

    def remove_goal(self, goal_id: str) -> bool:
        before = len(self.goals)
        self.goals = [g for g in self.goals if g.id != goal_id]
        return len(self.goals) < before

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return next((g for g in self.goals if g.id == goal_id), None)

    def pending_goals(self) -> list[Goal]:
        """Priority ਅਨੁਸਾਰ sort ਕਰਕੇ pending goals ਦਿਓ"""
        return sorted(
            [g for g in self.goals if g.status == "pending"],
            key=lambda g: g.priority,
            reverse=True,
        )

    # ─── Core Processing ──────────────────────────────────────

    async def process_goals(self) -> list[Goal]:
        """
        ਸਾਰੇ pending goals ਨੂੰ priority ਅਨੁਸਾਰ process ਕਰੋ।
        ਹਰ goal ਲਈ planner ਤੋਂ plan ਬਣਾਓ ਤੇ execute ਕਰੋ।
        """
        completed = []


        for goal in self.pending_goals():
            print(f"\n[GoalEngine] 🎯 Processing: {goal}")
            goal.status = "active"
            try:
                # Planner ਤੋਂ task list ਲਓ
                tasks = await self.planner.create_plan(goal.description)
                if not tasks:
                    raise ValueError("Planner returned no tasks")
                # Enforce MAX_TASKS_PER_GOAL
                if len(tasks) > self.MAX_TASKS_PER_GOAL:
                    tasks = tasks[:self.MAX_TASKS_PER_GOAL]
                goal.tasks.extend(tasks)
                # ਹਰ task execute ਕਰੋ
                results = []
                for i, task in enumerate(goal.tasks):
                    # Ensure task is a dict; if not, wrap it
                    if isinstance(task, str):
                        task = {"name": task, "agent": "tool", "priority": 5, "data": {}}
                    print(f"  [Task {i+1}/{len(goal.tasks)}] {task}")
                    result = await self.execute_task(task) if hasattr(self, 'execute_task') and callable(getattr(self, 'execute_task')) and hasattr(self.execute_task, '__call__') and hasattr(self.execute_task, '__await__') else self.execute_task(task)
                    results.append(result)
                goal.result = results
                goal.status = "done"
                completed.append(goal)
                self._persist(goal, event="completed")
                print(f"[GoalEngine] ✅ Done: {goal}")
            except Exception as e:
                goal.status = "failed"
                goal.error = str(e)
                self._persist(goal, event="failed")
                print(f"[GoalEngine] ❌ Failed: {goal} — {e}")
        return completed
    def execute_task(self, task):
        agent_type = task.get("type")
        if agent_type in self.agents:
            return self.agents[agent_type].run(task.get("input"))
        return f"No agent for {agent_type}"

    def retry_failed(self) -> list[Goal]:
        """ਸਾਰੇ failed goals ਨੂੰ pending ਕਰਕੇ ਦੁਬਾਰਾ try ਕਰੋ"""
        failed = [g for g in self.goals if g.status == "failed"]
        for g in failed:
            g.status = "pending"
            g.error = None
            g.tasks = []
        print(f"[GoalEngine] 🔄 Retrying {len(failed)} failed goal(s)")
        return self.process_goals()

    # ─── Memory Persistence ───────────────────────────────────

    def _persist(self, goal: Goal, event: str):
        """Goal ਨੂੰ memory ਵਿੱਚ ਸੇਵ ਕਰੋ"""
        try:
            if self.memory:
                self.memory.store(
                    key=f"goal:{goal.id}",
                    value={**goal.to_dict(), "event": event},
                )
        except Exception as e:
            print(f"[GoalEngine] ⚠️ Memory persist failed: {e}")

    def load_from_memory(self):
        """ਪੁਰਾਣੇ goals memory ਤੋਂ restore ਕਰੋ"""
        try:
            if self.memory:
                saved = self.memory.list_keys(prefix="goal:")
                for key in saved:
                    data = self.memory.retrieve(key)
                    if data and data.get("status") == "pending":
                        g = Goal(data["description"], data.get("priority", 1))
                        g.id = data["id"]
                        g.status = "pending"
                        self.goals.append(g)
                print(f"[GoalEngine] 📂 Loaded {len(saved)} goals from memory")
        except Exception as e:
            print(f"[GoalEngine] ⚠️ Memory load failed: {e}")

    # ─── Stats ────────────────────────────────────────────────

    def summary(self) -> dict:
        total = len(self.goals)
        return {
            "total": total,
            "pending":  sum(1 for g in self.goals if g.status == "pending"),
            "active":   sum(1 for g in self.goals if g.status == "active"),
            "done":     sum(1 for g in self.goals if g.status == "done"),
            "failed":   sum(1 for g in self.goals if g.status == "failed"),
        }

    def __repr__(self):
        s = self.summary()
        return (
            f"<GoalEngine goals={s['total']} "
            f"pending={s['pending']} done={s['done']} failed={s['failed']}>"
        )
        