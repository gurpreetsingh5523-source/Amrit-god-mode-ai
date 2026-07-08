"""Priority Engine — Multi-factor dynamic prioritization."""
from logger import setup_logger
logger = setup_logger("PriorityEngine")

AGENT_W = {"researcher":1,"internet":1,"planner":2,"memory":1,"coder":3,
           "debugger":2,"tester":4,"tool":3,"dataset":3,"monitor":2,"upgrade":3}
URGENT  = ["critical","urgent","fix","error","broken","crash"]
QUICK   = ["check","status","list","get"]

class PriorityEngine:
    def assign(self, tasks: list) -> list:
        scored = sorted(tasks, key=self._score)
        for i,t in enumerate(scored):
            t["priority"] = i+1
        return scored

    def _score(self, t):
        name  = t.get("name","").lower()
        score = float(t.get("priority",5)) + AGENT_W.get(t.get("agent","tool"),3)*0.1
        score += len(t.get("depends_on",[]))*0.5
        if any(w in name for w in URGENT):
            score -= 3
        if any(w in name for w in QUICK):
            score -= 1
        return score
