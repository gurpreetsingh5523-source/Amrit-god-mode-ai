"""Evaluation Engine — Performance measurement for agents and outputs."""
from logger import setup_logger
logger = setup_logger("EvaluationEngine")

class EvaluationEngine:
    def evaluate_tasks(self, task_graph) -> dict:
        tasks = task_graph.all_tasks()
        total = len(tasks) or 1
        done  = len(task_graph.completed_tasks())
        failed= len(task_graph.failed_tasks())
        rate  = round(done/total, 3)
        return {"total":total,"completed":done,"failed":failed,
                "success_rate":rate,"grade":self._grade(rate)}

    def evaluate_output(self, expected: str, actual: str) -> dict:
        exp_w = set(expected.lower().split()); act_w = set(actual.lower().split())
        if not exp_w: return {"score":0.0,"match":False}
        overlap = len(exp_w & act_w) / len(exp_w)
        return {"score":round(overlap,3),"match":overlap>0.7}

    def evaluate_code(self, code: str) -> dict:
        from code_analysis import CodeAnalyzer
        a = CodeAnalyzer(); analysis = a.analyze(code); syntax = a.syntax_check(code)
        score = 1.0 - (0.5 if not syntax["valid"] else 0) - min(0.3, len(analysis["issues"]) * 0.05)
        return {"score":max(0.0,round(score,2)),"syntax":syntax,"issues":analysis["issues"],
                "grade":self._grade(score)}

    def _grade(self, s: float) -> str:
        return "A" if s>=0.9 else "B" if s>=0.75 else "C" if s>=0.6 else "D" if s>=0.4 else "F"

    def benchmark_agent(self, name: str, xp_log) -> dict:
        records = [e for e in xp_log.get_all() if e.get("agent")==name]
        if not records: return {"agent":name,"total":0}
        succ = sum(1 for r in records if r.get("success",True))
        return {"agent":name,"total":len(records),"success":succ,
                "rate":round(succ/len(records),3)}
