"""
Permission Enforcer — Fine-grained per-tool enforcement layer.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sits on top of PermissionManager and adds:
  • Per-tool required permissions
  • Workspace boundary enforcement (no writes outside project)
  • Structured Allow/Deny results with reasons
  • Dry-run mode for planning
"""
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Union
from logger import setup_logger
from permission_manager import PermissionManager

logger = setup_logger("PermissionEnforcer")


class Decision(Enum):
    ALLOW = auto()
    DENY  = auto()


@dataclass
class EnforcementResult:
    decision: Decision
    reason: str
    tool: str
    agent: str
    action: str

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW

    def __bool__(self) -> bool:
        return self.allowed


# ── Tool → required permission mapping ────────────────────────────
TOOL_PERMISSIONS: dict[str, str] = {
    # File operations
    "file.read":       "file.read",
    "file.write":      "file.write",
    "file.delete":     "file.write",
    "file.list":       "file.read",
    # Terminal
    "terminal.exec":   "terminal.exec",
    "terminal.kill":   "terminal.exec",
    # Git
    "git.commit":      "git.all",
    "git.push":        "git.all",
    "git.branch":      "git.all",
    "git.clone":       "git.all",
    # Web
    "web.search":      "web.search",
    "web.fetch":       "web.fetch",
    "web.download":    "web.download",
    # LLM
    "llm.call":        "llm.call",
    "llm.embed":       "llm.call",
    # Memory
    "memory.read":     "memory.read",
    "memory.write":    "memory.write",
    # System
    "pip.install":     "pip.install",
    "system.read":     "system.read",
}


class PermissionEnforcer:
    """Enforces tool-level permissions with workspace boundary checks."""

    def __init__(self, perm_manager: PermissionManager,
                 workspace_root: Optional[Union[str, Path]] = None):
        self.pm = perm_manager
        self.workspace = Path(workspace_root).resolve() if workspace_root else None
        self._denied_log: list[EnforcementResult] = []

    def check(self, agent: str, tool: str,
              target_path: Optional[str] = None) -> EnforcementResult:
        """Check if agent can use tool, optionally on a specific path."""
        action = TOOL_PERMISSIONS.get(tool, tool)

        # 1) RBAC check via PermissionManager
        if not self.pm.can(agent, action):
            result = EnforcementResult(
                Decision.DENY,
                f"{agent} lacks permission '{action}' for tool '{tool}'",
                tool, agent, action,
            )
            self._denied_log.append(result)
            logger.warning(f"DENIED: {result.reason}")
            return result

        # 2) Workspace boundary check for file/git operations
        if target_path and self.workspace and tool.startswith(("file.", "git.")):
            resolved = Path(target_path).resolve()
            if not str(resolved).startswith(str(self.workspace)):
                result = EnforcementResult(
                    Decision.DENY,
                    f"Path '{target_path}' is outside workspace boundary",
                    tool, agent, action,
                )
                self._denied_log.append(result)
                logger.warning(f"BOUNDARY DENIED: {result.reason}")
                return result

        # 3) Allow
        return EnforcementResult(
            Decision.ALLOW,
            f"{agent} authorized for '{tool}'",
            tool, agent, action,
        )

    def require(self, agent: str, tool: str,
                target_path: Optional[str] = None) -> EnforcementResult:
        """Like check(), but raises PermissionError on deny."""
        result = self.check(agent, tool, target_path)
        if not result:
            raise PermissionError(result.reason)
        return result

    def denied_history(self, limit: int = 50) -> list[dict]:
        return [
            {"tool": r.tool, "agent": r.agent, "reason": r.reason}
            for r in self._denied_log[-limit:]
        ]

    def register_tool(self, tool: str, required_permission: str):
        """Register a new tool → permission mapping at runtime."""
        TOOL_PERMISSIONS[tool] = required_permission
        logger.info(f"Registered tool '{tool}' → '{required_permission}'")
