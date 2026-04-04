"""Permission Manager — Agent RBAC."""
from logger import setup_logger
logger = setup_logger("PermissionManager")

DEFAULTS = {
    "PlannerAgent":   ["task.create","task.list","state.read","llm.call"],
    "CoderAgent":     ["file.read","file.write","llm.call","state.read"],
    "ResearchAgent":  ["web.search","web.fetch","file.read","llm.call"],
    "TesterAgent":    ["file.read","terminal.exec","file.write","llm.call"],
    "DebuggerAgent":  ["file.read","terminal.exec","llm.call"],
    "ToolAgent":      ["file.*","terminal.exec","git.all"],
    "MemoryAgent":    ["memory.read","memory.write","state.*"],
    "UpgradeAgent":   ["file.read","llm.call","pip.install"],
    "MonitorAgent":   ["system.read","state.read"],
    "VoiceAgent":     ["audio.record","audio.speak"],
    "VisionAgent":    ["file.read","image.process","llm.call"],
    "InternetAgent":  ["web.search","web.fetch","web.download"],
    "DatasetAgent":   ["file.read","file.write","data.process","llm.call"],
    "SimulationAgent":["compute","file.write","llm.call"],
    "system":         ["*"],
}

class PermissionManager:
    def __init__(self): self._perms = dict(DEFAULTS); self._audit = []

    def can(self, agent: str, action: str) -> bool:
        allowed = self._perms.get(agent,[])
        if "*" in allowed: return True
        if action in allowed: return True
        prefix = action.split(".")[0]+".*"
        result = prefix in allowed
        self._audit.append({"agent":agent,"action":action,"granted":result})
        return result

    def grant(self, agent: str, perm: str):
        self._perms.setdefault(agent,[])
        if perm not in self._perms[agent]: self._perms[agent].append(perm)
        logger.info(f"Granted {agent}: {perm}")

    def revoke(self, agent: str, perm: str):
        if agent in self._perms:
            try: self._perms[agent].remove(perm)
            except ValueError: pass

    def list_perms(self, agent: str) -> list: return self._perms.get(agent,[])
    def audit(self, limit=50) -> list: return self._audit[-limit:]
    def require(self, agent: str, action: str):
        if not self.can(agent,action): raise PermissionError(f"{agent} cannot {action}")
