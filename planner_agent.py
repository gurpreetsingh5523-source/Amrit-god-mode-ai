
from base_agent import BaseAgent
"""Planner Agent — LLM-powered goal decomposition into task graphs."""
import asyncio
import json
import re

class PlannerAgent(BaseAgent):

    async def create_plan(self, goal_description: str):
        """
        Wrapper for GoalEngine: creates a plan using agent's async logic.
        """
        task_payload = {"action": "plan", "goal": goal_description}
        return await self.execute(task_payload)

    def __init__(self, eb, state):
        super().__init__("PlannerAgent", eb, state)

    # Simple goals that don't need decomposition — just do them directly
    _SIMPLE_KEYWORDS = {"poem", "story", "song", "essay", "letter", "joke",
                        "ਕਵਿਤਾ", "ਗੀਤ", "ਕਹਾਣੀ", "ਲੇਖ", "ਚਿੱਠੀ", "ਸ਼ਾਇਰੀ", "ਚੁਟਕਲਾ"}

    async def execute(self, task: dict) -> dict:
        goal = task.get("data", {}).get("goal") or task.get("name", "")
        await self.report(f"Planning: {goal!r}")

        # Skip decomposition for simple creative tasks — just produce the output
        low = goal.lower()
        if any(w in low for w in self._SIMPLE_KEYWORDS):
            result = await self.ask_llm(f"ਪੰਜਾਬੀ ਗੁਰਮੁਖੀ ਵਿੱਚ ਲਿਖੋ: {goal}")
            return self.ok(output=result, direct=True)

        prompt = f"""Decompose this goal into 2-5 ordered tasks for an autonomous AI system.
GOAL: {goal}
Available agents and their roles:
- researcher: search internet, gather info, read docs
- coder: write code, create files, build features
- tester: test code, run checks, validate
- debugger: find and fix bugs
- tool: run shell commands, install packages
- internet: fetch web pages, APIs
Rules:
- Each task must have a clear one-line name describing WHAT to do
- Include relevant data in "data" dict (spec, language, filename, query)
- Set dependencies if a task needs another task's output
- Priority 1 = highest (do first)
Return ONLY JSON array: [{{"name":"short task description","agent":"agent_name","priority":1,"data":{{"spec":"detailed description","action":"generate"}},"depends_on":[]}}]"""
        try:
            resp   = await self.ask_llm(prompt)
            tasks  = self._parse(resp)
        except Exception:
            tasks  = self._fallback(goal)
        for t in tasks:
            await self.emit("task.new", t)
        return self.ok(plan=tasks, count=len(tasks))

    def _parse(self, text: str) -> list:
        clean = re.sub(r"```(?:json)?|```", "", text).strip()
        m = re.search(r'\[.*\]', clean, re.DOTALL)
        if not m:
            return self._fallback("")
        return [{**t, "priority": int(t.get("priority", 5))} for t in json.loads(m.group())]

    def _fallback(self, goal: str) -> list:
        return [
            {"name": f"Research: {goal}", "agent": "researcher", "priority": 1, "data": {"query": goal}},
            {"name": f"Execute: {goal}",  "agent": "tool",       "priority": 2, "data": {}},
            {"name": f"Verify: {goal}",   "agent": "tester",     "priority": 3, "data": {}},
        ]
