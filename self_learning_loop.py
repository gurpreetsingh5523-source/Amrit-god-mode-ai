"""Self Learning Loop — Learns from experience and improves strategies."""
from logger import setup_logger
logger = setup_logger("SelfLearningLoop")

class SelfLearningLoop:
    def __init__(self): self._strategies=[]; self._n=0

    async def learn(self, xp_log, orchestrator=None) -> dict:
        self._n += 1
        all_xp = xp_log.get_all() if hasattr(xp_log,"get_all") else []
        if not all_xp: return {"learned":False}
        failures  = [e for e in all_xp if not e.get("success",True)]
        successes = [e for e in all_xp if e.get("success",True)]
        try:
            from llm_router import LLMRouter
            prompt = f"""Analyze agent experiences and extract lessons:
SUCCESSES ({len(successes)}): {str(successes[-3:])}
FAILURES  ({len(failures)}):  {str(failures[-3:])}
Return 3 actionable lessons to improve performance."""
            lessons = await LLMRouter().complete(prompt, max_tokens=500)
        except Exception as e:
            lessons = self._rule_lessons(failures)
        strategy = {"n":self._n,"lessons":lessons,"failures":len(failures),"successes":len(successes)}
        self._strategies.append(strategy)
        logger.info(f"Learning iteration {self._n}: {len(failures)} failures → {len(successes)} successes")
        return {"learned":True,"strategy":strategy}

    def _rule_lessons(self, failures: list) -> str:
        if not failures: return "No failures to learn from."
        agents = [f.get("agent") for f in failures]
        top = max(set(agents),key=agents.count) if agents else "unknown"
        return f"Agent '{top}' failed most. Add retries or switch agent."

    def strategies(self) -> list: return list(self._strategies)
    def latest(self) -> str:
        return self._strategies[-1].get("lessons","") if self._strategies else "None"
