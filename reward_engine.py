"""Reward Engine — Reinforcement signal for agent improvement."""
from logger import setup_logger
logger = setup_logger("RewardEngine")

class RewardEngine:
    def __init__(self): self._history = []

    def score(self, task: dict, result: dict) -> float:
        reward = 0.0
        if result.get("status") in ("ok","completed","done"): reward += 1.0
        elif result.get("status") == "error": reward -= 0.5
        if result.get("retries",0) > 0:  reward -= 0.1 * result["retries"]
        if result.get("duration_s",0) > 0:
            duration = result["duration_s"]
            if duration < 5:   reward += 0.2
            elif duration > 60: reward -= 0.1
        self._history.append({"task":task.get("name",""),"agent":task.get("agent",""),
                               "reward":reward,"result":result.get("status","")})
        return round(reward, 3)

    def agent_scores(self) -> dict:
        scores = {}
        for h in self._history:
            a = h["agent"]
            scores.setdefault(a, []).append(h["reward"])
        return {a: round(sum(v)/len(v),3) for a,v in scores.items()}

    def best_agent_for(self, task_type: str) -> str:
        relevant = [h for h in self._history if task_type.lower() in h["task"].lower()]
        if not relevant: return "planner"
        by_agent = {}
        for h in relevant: by_agent.setdefault(h["agent"],[]).append(h["reward"])
        return max(by_agent, key=lambda a: sum(by_agent[a])/len(by_agent[a]))

    def history(self, n=50) -> list: return self._history[-n:]
