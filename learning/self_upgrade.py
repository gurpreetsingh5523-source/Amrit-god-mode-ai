"""Self Upgrade — Analyzes and improves system components autonomously."""
import re
from pathlib import Path
from logger import setup_logger

logger = setup_logger("SelfUpgrade")

class SelfUpgrade:
    def __init__(self):
        self._upgrades = []

    async def analyze_and_upgrade(self, orchestrator) -> dict:
        coder   = orchestrator.get_agent("coder")
        orchestrator.get_agent("tester")
        results = []
        py_files = list(Path(".").rglob("*.py"))[:20]
        
        for fp in py_files:
            try:
                code = fp.read_text(errors="ignore")
                
                if any("TODO" in ln for ln in code.splitlines()):
                    if coder:
                        result = await coder.execute({
                            "name": f"Improve {fp.name}",
                            "data": {
                                "action": "refactor",
                                "code": code,
                                "goal": "implement TODOs and improve quality"
                            }
                        })
                        
                        if "code" in result:
                            fp.write_text(result["code"])
                            results.append({"file": str(fp), "status": "upgraded"})
                
                else:
                    results.append({"file": str(fp), "status": "no_action_needed"})
            except Exception as e:
                logger.error(f"Error processing {fp}: {e}")
                results.append({"file": str(fp), "status": "error", "error": str(e)})
        
        self._upgrades.extend(results)
        
        return {
            "upgraded": len([r for r in results if r["status"] == "upgraded"]),
            "total_analyzed": len(py_files),
            "results": results
        }

    def history(self) -> list: 
        return list(self._upgrades)