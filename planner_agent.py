"""Planner Agent — LLM-powered goal decomposition into task graphs."""
import json, re
from base_agent import BaseAgent

class PlannerAgent(BaseAgent):
    def __init__(self, eb, state): super().__init__("PlannerAgent", eb, state)

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

        prompt = f"""Decompose this goal into 2-4 ordered tasks for an autonomous AI system.
GOAL: {goal}
Available agents: planner, coder, researcher, tester, debugger, tool, memory, internet, dataset, monitor
Return ONLY JSON array: [{{"name":"...","agent":"...","priority":1,"data":{{}},"depends_on":[]}}]"""
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
        if not m: return self._fallback("")
        return [{**t, "priority": int(t.get("priority", 5))} for t in json.loads(m.group())]

    def _fallback(self, goal: str) -> list:
        return [
            {"name": f"Research: {goal}", "agent": "researcher", "priority": 1, "data": {"query": goal}},
            {"name": f"Execute: {goal}",  "agent": "tool",       "priority": 2, "data": {}},
            {"name": f"Verify: {goal}",   "agent": "tester",     "priority": 3, "data": {}},
        ]
