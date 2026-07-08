"""
Policy Engine — Conditional automation rules for AMRIT GODMODE.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rules are IF condition THEN action, evaluated by priority.
Conditions compose (And, Or, Not).
Actions: MergeToDev, RecoverOnce, Escalate, RestartAgent,
         NotifyUser, CloseTask, RunCommand, Custom.

Use case examples:
  • IF all tests pass AND branch is feature/* THEN auto-merge
  • IF agent stale > 60s THEN restart agent
  • IF failure count > 5 in 10 min THEN escalate to user
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable
import time
from logger import setup_logger

logger = setup_logger("PolicyEngine")


# ═══════════════════════════════════════════════════════════════
# Conditions
# ═══════════════════════════════════════════════════════════════

class ConditionType(Enum):
    AND              = auto()
    OR               = auto()
    NOT              = auto()
    TESTS_PASS       = auto()   # All tests in scope are green
    BRANCH_MATCHES   = auto()   # Current branch matches pattern
    AGENT_STALE      = auto()   # Agent idle > N seconds
    FAILURE_COUNT    = auto()   # N failures in time window
    TASK_STATUS      = auto()   # Task has specific status
    FILE_EXISTS      = auto()   # File exists in workspace
    TIME_ELAPSED     = auto()   # Seconds since event
    CUSTOM           = auto()   # User-provided callable


@dataclass
class PolicyCondition:
    """A composable boolean condition."""
    ctype: ConditionType
    value: str = ""               # Pattern, filename, status, etc.
    threshold: float = 0          # For numeric comparisons
    window_seconds: float = 0     # Time window for rate conditions
    children: list["PolicyCondition"] = field(default_factory=list)  # For AND, OR, NOT
    check_fn: Optional[Callable] = field(default=None, repr=False)  # For CUSTOM

    def evaluate(self, ctx: dict) -> bool:
        """Evaluate condition against a context dict."""
        if self.ctype == ConditionType.AND:
            return all(c.evaluate(ctx) for c in self.children)

        if self.ctype == ConditionType.OR:
            return any(c.evaluate(ctx) for c in self.children)

        if self.ctype == ConditionType.NOT:
            return not self.children[0].evaluate(ctx) if self.children else True

        if self.ctype == ConditionType.TESTS_PASS:
            return ctx.get("tests_pass", False)

        if self.ctype == ConditionType.BRANCH_MATCHES:
            import fnmatch
            branch = ctx.get("branch", "")
            return fnmatch.fnmatch(branch, self.value)

        if self.ctype == ConditionType.AGENT_STALE:
            idle = ctx.get("agent_idle_seconds", 0)
            return idle > self.threshold

        if self.ctype == ConditionType.FAILURE_COUNT:
            recent = ctx.get("recent_failures", [])
            cutoff = time.time() - self.window_seconds
            count = sum(1 for f in recent if f.get("timestamp", 0) > cutoff)
            return count >= self.threshold

        if self.ctype == ConditionType.TASK_STATUS:
            return ctx.get("task_status", "") == self.value

        if self.ctype == ConditionType.FILE_EXISTS:
            from pathlib import Path
            return Path(self.value).exists()

        if self.ctype == ConditionType.TIME_ELAPSED:
            elapsed = ctx.get("elapsed_seconds", 0)
            return elapsed > self.threshold

        if self.ctype == ConditionType.CUSTOM and self.check_fn:
            return self.check_fn(ctx)

        return False


# ═══════════════════════════════════════════════════════════════
# Actions
# ═══════════════════════════════════════════════════════════════

class ActionType(Enum):
    MERGE_TO_DEV     = auto()   # Auto-merge branch into dev/main
    RECOVER_ONCE     = auto()   # Trigger recovery engine for current failure
    ESCALATE         = auto()   # Notify user / orchestrator
    RESTART_AGENT    = auto()   # Restart a stale/failed agent
    NOTIFY_USER      = auto()   # Send notification (Telegram, log)
    CLOSE_TASK       = auto()   # Mark task as closed/completed
    RUN_COMMAND      = auto()   # Execute shell command
    BLOCK_TASK       = auto()   # Block task until manual review
    CUSTOM           = auto()   # User-provided callable


@dataclass
class PolicyAction:
    """An action to execute when policy condition is met."""
    action_type: ActionType
    description: str = ""
    target: str = ""          # Agent name, branch, command, etc.
    params: dict = field(default_factory=dict)
    execute_fn: Optional[Callable] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "type": self.action_type.name,
            "description": self.description,
            "target": self.target,
            "params": self.params,
        }


# ═══════════════════════════════════════════════════════════════
# Policy Rule
# ═══════════════════════════════════════════════════════════════

@dataclass
class PolicyRule:
    """IF condition THEN action, with priority for ordering."""
    name: str
    condition: PolicyCondition
    action: PolicyAction
    priority: int = 5           # 1 = highest, 10 = lowest
    enabled: bool = True
    cooldown_seconds: float = 0   # Minimum time between firings
    _last_fired: float = 0

    def can_fire(self) -> bool:
        if not self.enabled:
            return False
        if self.cooldown_seconds > 0:
            return (time.time() - self._last_fired) >= self.cooldown_seconds
        return True

    def mark_fired(self):
        self._last_fired = time.time()


# ═══════════════════════════════════════════════════════════════
# Policy Engine
# ═══════════════════════════════════════════════════════════════

class PolicyEngine:
    """Evaluates policy rules against context and returns triggered actions."""

    def __init__(self):
        self._rules: list[PolicyRule] = []
        self._fire_log: list[dict] = []
        self._load_defaults()

    def add_rule(self, rule: PolicyRule):
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        logger.info(f"Added policy rule: {rule.name} (priority {rule.priority})")

    def remove_rule(self, name: str):
        self._rules = [r for r in self._rules if r.name != name]

    def evaluate(self, ctx: dict) -> list[PolicyAction]:
        """Evaluate all rules and return list of triggered actions."""
        triggered: list[PolicyAction] = []
        for rule in self._rules:
            if not rule.can_fire():
                continue
            try:
                if rule.condition.evaluate(ctx):
                    triggered.append(rule.action)
                    rule.mark_fired()
                    self._fire_log.append({
                        "rule": rule.name,
                        "action": rule.action.to_dict(),
                        "timestamp": time.time(),
                    })
                    logger.info(f"Policy triggered: {rule.name} → {rule.action.action_type.name}")
            except Exception as e:
                logger.error(f"Policy eval error in '{rule.name}': {e}")

        return triggered

    def fire_log(self, limit: int = 30) -> list[dict]:
        return self._fire_log[-limit:]

    @property
    def rules(self) -> list[dict]:
        return [
            {"name": r.name, "priority": r.priority, "enabled": r.enabled,
             "action": r.action.action_type.name}
            for r in self._rules
        ]

    def _load_defaults(self):
        """Load sensible default policies."""

        # 1) Auto-escalate on 5+ failures in 10 minutes
        self.add_rule(PolicyRule(
            name="escalate_on_failure_burst",
            condition=PolicyCondition(
                ConditionType.FAILURE_COUNT, threshold=5, window_seconds=600),
            action=PolicyAction(
                ActionType.ESCALATE,
                description="Too many failures in 10 min — escalating to user"),
            priority=1,
            cooldown_seconds=300,
        ))

        # 2) Restart stale agent after 120s idle
        self.add_rule(PolicyRule(
            name="restart_stale_agent",
            condition=PolicyCondition(
                ConditionType.AGENT_STALE, threshold=120),
            action=PolicyAction(
                ActionType.RESTART_AGENT,
                description="Agent idle > 120s — restarting"),
            priority=3,
            cooldown_seconds=60,
        ))

        # 3) Auto-merge when tests pass on feature branch
        self.add_rule(PolicyRule(
            name="auto_merge_green_feature",
            condition=PolicyCondition(
                ConditionType.AND, children=[
                    PolicyCondition(ConditionType.TESTS_PASS),
                    PolicyCondition(ConditionType.BRANCH_MATCHES, value="feature/*"),
                ]),
            action=PolicyAction(
                ActionType.MERGE_TO_DEV,
                description="All tests pass on feature branch — auto-merging"),
            priority=5,
        ))

        # 4) Try recovery once on any recoverable failure
        self.add_rule(PolicyRule(
            name="auto_recover_once",
            condition=PolicyCondition(
                ConditionType.CUSTOM,
                check_fn=lambda ctx: ctx.get("failure_retryable", False)
                                     and ctx.get("recovery_attempts", 0) < 1),
            action=PolicyAction(
                ActionType.RECOVER_ONCE,
                description="Retryable failure detected — attempting auto-recovery"),
            priority=2,
        ))
