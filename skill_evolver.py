"""Skill Evolver — Evolves agent skills through reinforcement and rewriting."""
from pathlib import Path
from logger import setup_logger
logger = setup_logger("SkillEvolver")

class SkillEvolver:
    def __init__(self): self._evolved = []

    async def evolve_skill(self, skill_path: str, performance_score: float,
                            orchestrator=None) -> dict:
        p = Path(skill_path)
        if not p.exists(): return {"status":"error","error":"File not found"}
        if performance_score >= 0.8:
            return {"status":"skipped","reason":"Performance already good","score":performance_score}
        code = p.read_text(errors="ignore")
        if not orchestrator: return {"status":"skipped","reason":"No orchestrator"}
        coder = orchestrator.get_agent("coder")
        if not coder: return {"status":"skipped","reason":"No coder"}
        result = await coder.execute({"name":f"Evolve {p.name}",
            "data":{"action":"refactor","code":code,
                    "goal":f"improve performance (current score: {performance_score:.2f})"}})
        if result.get("code"):
            backup = str(p)+".bak"; Path(backup).write_text(code)
            p.write_text(result["code"])
            self._evolved.append({"skill":skill_path,"score":performance_score})
            logger.info(f"Evolved: {p.name}")
            return {"status":"evolved","file":skill_path,"backup":backup}
        return {"status":"unchanged","file":skill_path}

    def history(self) -> list: return list(self._evolved)
