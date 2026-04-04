"""Strategy Builder — Selects execution strategy."""
from logger import setup_logger
logger = setup_logger("StrategyBuilder")

STRATS = {
    "sequential": {"parallel":False,"chunk":1,"notes":"Safe, one at a time"},
    "parallel":   {"parallel":True, "chunk":4,"notes":"All independent tasks"},
    "hybrid":     {"parallel":True, "chunk":2,"notes":"Parallel within dep groups"},
    "cautious":   {"parallel":False,"chunk":1,"notes":"Sequential + validation"},
}

class StrategyBuilder:
    def build(self, goal: str, tasks=None, context=None) -> dict:
        tasks = tasks or []; n = len(tasks); gl = goal.lower()
        if "safe" in gl or n <= 2: s = "cautious"
        elif n >= 6 and all(not t.get("depends_on") for t in tasks): s = "parallel"
        elif n >= 3: s = "hybrid"
        else: s = "sequential"
        logger.info(f"Strategy: {s}")
        return {"name": s, **STRATS[s]}
