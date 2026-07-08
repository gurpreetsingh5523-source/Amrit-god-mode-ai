"""Auto Refactor — Automatically refactors code for quality."""
from pathlib import Path
from logger import setup_logger
logger = setup_logger("AutoRefactor")

class AutoRefactor:
    def __init__(self, orchestrator=None):
        self.orc = orchestrator
        self._log = []

    async def refactor_file(self, filepath: str) -> dict:
        p = Path(filepath)
        if not p.exists():
            return {"status":"error","error":"File not found"}
        code = p.read_text(errors="ignore")
        if not self.orc:
            return {"status":"skipped","reason":"No orchestrator"}
        coder = self.orc.get_agent("coder")
        if not coder:
            return {"status":"skipped","reason":"No coder agent"}
        result = await coder.execute({"name":f"Refactor {p.name}",
            "data":{"action":"refactor","code":code,"goal":"add type hints, docstrings, error handling"}})
        if result.get("code"):
            # Backup original
            backup = str(p)+".bak"
            Path(backup).write_text(code)
            p.write_text(result["code"])
            self._log.append({"file":filepath,"backup":backup,"status":"refactored"})
            logger.info(f"Refactored: {filepath}")
            return {"status":"refactored","file":filepath,"backup":backup}
        return {"status":"unchanged","file":filepath}

    async def refactor_project(self, root=".", pattern="*.py", max_files=10) -> dict:
        files = list(Path(root).rglob(pattern))[:max_files]
        results = [await self.refactor_file(str(f)) for f in files]
        return {"total":len(files),"refactored":len([r for r in results if r["status"]=="refactored"]),
                "results":results}

    def log(self) -> list: return list(self._log)
