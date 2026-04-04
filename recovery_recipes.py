"""
Recovery Recipes — Known failure → fix mappings with auto-resolution.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a classified failure matches a known scenario, the
RecoveryEngine runs a recipe: a sequence of typed steps
(bash, file_edit, retry, escalate) to fix the problem
without human intervention.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Awaitable
import asyncio, time
from logger import setup_logger
from failure_taxonomy import ClassifiedFailure, FailureClass, Severity

logger = setup_logger("RecoveryRecipes")


class FailureScenario(Enum):
    """Named scenarios we have recipes for."""
    MISSING_PACKAGE     = auto()
    MERGE_CONFLICT      = auto()
    LLM_TIMEOUT         = auto()
    LLM_RATE_LIMIT      = auto()
    PORT_IN_USE         = auto()
    STALE_AGENT         = auto()
    DISK_FULL           = auto()
    PERMISSION_DENIED   = auto()
    CORRUPT_STATE       = auto()
    GIT_DIVERGED        = auto()
    MODEL_NOT_FOUND     = auto()
    IMPORT_ERROR        = auto()
    TEST_FAILURE        = auto()
    JSON_PARSE_ERROR    = auto()


class StepType(Enum):
    BASH     = "bash"       # Run a shell command
    PYTHON   = "python"     # Execute a Python callable
    RETRY    = "retry"      # Retry the original operation
    WAIT     = "wait"       # Wait N seconds
    ESCALATE = "escalate"   # Give up and escalate to user/orchestrator


@dataclass
class RecoveryStep:
    """One step in a recipe."""
    step_type: StepType
    description: str
    command: str = ""                  # For BASH steps
    callable: Optional[Callable] = field(default=None, repr=False)  # For PYTHON steps
    wait_seconds: float = 0            # For WAIT steps
    fail_ok: bool = False              # Continue even if this step fails


@dataclass
class RecoveryRecipe:
    """A named sequence of steps to fix a known failure."""
    name: str
    scenario: FailureScenario
    description: str
    steps: list[RecoveryStep] = field(default_factory=list)
    max_attempts: int = 2
    cooldown_seconds: float = 5.0


@dataclass
class RecoveryContext:
    """Runtime context passed to recovery execution."""
    failure: ClassifiedFailure
    terminal_exec: Optional[Callable[..., Awaitable]] = field(default=None, repr=False)
    event_publish: Optional[Callable[..., Awaitable]] = field(default=None, repr=False)
    attempt: int = 0
    step_results: list[dict] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Built-in Recipes
# ═══════════════════════════════════════════════════════════════

_BUILTIN_RECIPES: list[RecoveryRecipe] = [
    RecoveryRecipe(
        name="auto_install_missing_package",
        scenario=FailureScenario.MISSING_PACKAGE,
        description="Detect missing Python module and pip install it",
        steps=[
            RecoveryStep(StepType.BASH, "Install missing package",
                         "pip install {missing_module}"),
            RecoveryStep(StepType.RETRY, "Retry original operation"),
        ],
    ),
    RecoveryRecipe(
        name="llm_timeout_retry",
        scenario=FailureScenario.LLM_TIMEOUT,
        description="Wait and retry LLM call with backoff",
        steps=[
            RecoveryStep(StepType.WAIT, "Backoff before retry", wait_seconds=5),
            RecoveryStep(StepType.RETRY, "Retry LLM call"),
        ],
        max_attempts=3,
    ),
    RecoveryRecipe(
        name="llm_rate_limit",
        scenario=FailureScenario.LLM_RATE_LIMIT,
        description="Wait longer for rate limit to clear",
        steps=[
            RecoveryStep(StepType.WAIT, "Wait for rate limit reset", wait_seconds=30),
            RecoveryStep(StepType.RETRY, "Retry after cooldown"),
        ],
        max_attempts=2,
    ),
    RecoveryRecipe(
        name="model_not_found_pull",
        scenario=FailureScenario.MODEL_NOT_FOUND,
        description="Pull missing Ollama model",
        steps=[
            RecoveryStep(StepType.BASH, "Pull model from Ollama",
                         "ollama pull {model_name}"),
            RecoveryStep(StepType.RETRY, "Retry with fresh model"),
        ],
    ),
    RecoveryRecipe(
        name="import_error_install",
        scenario=FailureScenario.IMPORT_ERROR,
        description="Install missing import dependency",
        steps=[
            RecoveryStep(StepType.BASH, "Pip install missing module",
                         "pip install {missing_module}"),
            RecoveryStep(StepType.RETRY, "Retry import"),
        ],
    ),
    RecoveryRecipe(
        name="corrupt_state_reset",
        scenario=FailureScenario.CORRUPT_STATE,
        description="Back up and reset corrupt state file",
        steps=[
            RecoveryStep(StepType.BASH, "Backup corrupt state",
                         "cp workspace/state.json workspace/state.json.bak 2>/dev/null || true",
                         fail_ok=True),
            RecoveryStep(StepType.BASH, "Reset state to empty",
                         "echo '{}' > workspace/state.json"),
            RecoveryStep(StepType.RETRY, "Retry with clean state"),
        ],
    ),
    RecoveryRecipe(
        name="port_in_use_kill",
        scenario=FailureScenario.PORT_IN_USE,
        description="Kill process using the port and retry",
        steps=[
            RecoveryStep(StepType.BASH, "Find and kill process on port",
                         "lsof -ti:{port} | xargs kill -9 2>/dev/null || true",
                         fail_ok=True),
            RecoveryStep(StepType.WAIT, "Wait for port release", wait_seconds=2),
            RecoveryStep(StepType.RETRY, "Retry binding"),
        ],
    ),
    RecoveryRecipe(
        name="git_diverged_resolve",
        scenario=FailureScenario.GIT_DIVERGED,
        description="Stash local changes, pull, and re-apply",
        steps=[
            RecoveryStep(StepType.BASH, "Stash local changes",
                         "git stash"),
            RecoveryStep(StepType.BASH, "Pull latest",
                         "git pull --rebase"),
            RecoveryStep(StepType.BASH, "Pop stash",
                         "git stash pop", fail_ok=True),
        ],
    ),
    RecoveryRecipe(
        name="json_parse_fix",
        scenario=FailureScenario.JSON_PARSE_ERROR,
        description="Attempt to fix malformed JSON",
        steps=[
            RecoveryStep(StepType.PYTHON, "Try to repair JSON",
                         callable=None),  # Filled at runtime
            RecoveryStep(StepType.RETRY, "Retry with repaired JSON"),
        ],
    ),
]


# ═══════════════════════════════════════════════════════════════
# Scenario Matching — ClassifiedFailure → FailureScenario
# ═══════════════════════════════════════════════════════════════

_SCENARIO_MAP: list[tuple[FailureClass, list[str], FailureScenario]] = [
    (FailureClass.DEPENDENCY,  ["no module", "modulenotfound", "import"],    FailureScenario.MISSING_PACKAGE),
    (FailureClass.DEPENDENCY,  ["importerror"],                              FailureScenario.IMPORT_ERROR),
    (FailureClass.LLM_CALL,    ["timeout", "timed out"],                     FailureScenario.LLM_TIMEOUT),
    (FailureClass.LLM_CALL,    ["rate limit", "429", "quota"],               FailureScenario.LLM_RATE_LIMIT),
    (FailureClass.LLM_CALL,    ["model not found", "no model"],              FailureScenario.MODEL_NOT_FOUND),
    (FailureClass.PERMISSION,  ["permission"],                               FailureScenario.PERMISSION_DENIED),
    (FailureClass.STATE,       ["corrupt", "keyerror", "stale"],             FailureScenario.CORRUPT_STATE),
    (FailureClass.EXTERNAL_SVC,["merge conflict", "diverge"],                FailureScenario.GIT_DIVERGED),
    (FailureClass.PARSE,       ["json", "jsondecodeerror"],                  FailureScenario.JSON_PARSE_ERROR),
    (FailureClass.TOOL_RUNTIME,["address already in use", "port"],           FailureScenario.PORT_IN_USE),
]


def match_scenario(failure: ClassifiedFailure) -> Optional[FailureScenario]:
    """Try to match a classified failure to a known scenario."""
    err_lower = failure.error.lower()
    for fc, keywords, scenario in _SCENARIO_MAP:
        if failure.failure_class == fc and any(k in err_lower for k in keywords):
            return scenario
    return None


def _extract_vars(failure: ClassifiedFailure) -> dict:
    """Extract template variables from failure context/error text."""
    import re
    v = dict(failure.context)
    err = failure.error
    # Extract module name from "No module named 'xxx'"
    m = re.search(r"no module named ['\"]?(\w+)", err, re.I)
    if m:
        v.setdefault("missing_module", m.group(1))
    # Extract port from "port NNNN"
    m = re.search(r"port\s+(\d+)", err, re.I)
    if m:
        v.setdefault("port", m.group(1))
    # Extract model name
    m = re.search(r"model ['\"]?([a-zA-Z0-9_.:-]+)", err, re.I)
    if m:
        v.setdefault("model_name", m.group(1))
    return v


# ═══════════════════════════════════════════════════════════════
# Recovery Engine
# ═══════════════════════════════════════════════════════════════

class RecoveryEngine:
    """Matches failures to recipes and executes recovery steps."""

    def __init__(self):
        self._recipes: dict[FailureScenario, RecoveryRecipe] = {}
        self._history: list[dict] = []
        # Load builtins
        for r in _BUILTIN_RECIPES:
            self._recipes[r.scenario] = r

    def register(self, recipe: RecoveryRecipe):
        """Register a custom recipe (overrides builtin if same scenario)."""
        self._recipes[recipe.scenario] = recipe
        logger.info(f"Registered recipe: {recipe.name}")

    def find_recipe(self, failure: ClassifiedFailure) -> Optional[RecoveryRecipe]:
        """Find a recipe for a classified failure."""
        scenario = match_scenario(failure)
        if scenario and scenario in self._recipes:
            return self._recipes[scenario]
        return None

    async def attempt_recovery(self, failure: ClassifiedFailure,
                                terminal_exec=None,
                                event_publish=None) -> dict:
        """Try to auto-recover from a failure. Returns result dict."""
        recipe = self.find_recipe(failure)
        if not recipe:
            logger.debug(f"No recipe for {failure.tag}: {failure.error[:60]}")
            return {"recovered": False, "reason": "no_recipe"}

        ctx = RecoveryContext(
            failure=failure,
            terminal_exec=terminal_exec,
            event_publish=event_publish,
        )
        logger.info(f"Attempting recovery: {recipe.name} for [{failure.tag}]")

        template_vars = _extract_vars(failure)
        success = True

        for step in recipe.steps:
            step_result = {"step": step.description, "type": step.step_type.value}

            if step.step_type == StepType.BASH:
                cmd = step.command.format_map(template_vars)
                if terminal_exec:
                    try:
                        out = await terminal_exec(cmd)
                        step_result["output"] = str(out)[:200]
                        step_result["success"] = True
                    except Exception as e:
                        step_result["error"] = str(e)[:200]
                        step_result["success"] = step.fail_ok
                        if not step.fail_ok:
                            success = False
                            break
                else:
                    import subprocess
                    try:
                        r = subprocess.run(cmd, shell=True, capture_output=True,
                                           text=True, timeout=60)
                        step_result["output"] = r.stdout[:200]
                        step_result["success"] = r.returncode == 0 or step.fail_ok
                        if r.returncode != 0 and not step.fail_ok:
                            step_result["stderr"] = r.stderr[:200]
                            success = False
                            break
                    except Exception as e:
                        step_result["error"] = str(e)[:200]
                        step_result["success"] = step.fail_ok
                        if not step.fail_ok:
                            success = False
                            break

            elif step.step_type == StepType.WAIT:
                await asyncio.sleep(step.wait_seconds)
                step_result["success"] = True

            elif step.step_type == StepType.RETRY:
                step_result["success"] = True
                step_result["action"] = "retry_signaled"

            elif step.step_type == StepType.ESCALATE:
                step_result["success"] = False
                step_result["action"] = "escalated"
                if event_publish:
                    await event_publish("recovery.escalated", {
                        "recipe": recipe.name,
                        "failure": failure.to_dict(),
                    }, source="RecoveryEngine")
                success = False
                break

            elif step.step_type == StepType.PYTHON and step.callable:
                try:
                    result = step.callable(ctx)
                    if asyncio.iscoroutine(result):
                        result = await result
                    step_result["success"] = True
                    step_result["output"] = str(result)[:200]
                except Exception as e:
                    step_result["error"] = str(e)[:200]
                    step_result["success"] = step.fail_ok
                    if not step.fail_ok:
                        success = False
                        break

            ctx.step_results.append(step_result)

        entry = {
            "recipe": recipe.name,
            "failure_tag": failure.tag,
            "recovered": success,
            "steps": ctx.step_results,
            "timestamp": time.time(),
        }
        self._history.append(entry)
        if event_publish:
            evt = "recovery.success" if success else "recovery.failed"
            await event_publish(evt, entry, source="RecoveryEngine")

        if success:
            logger.info(f"Recovery SUCCESS: {recipe.name}")
        else:
            logger.warning(f"Recovery FAILED: {recipe.name}")

        return entry

    def history(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]

    def stats(self) -> dict:
        total = len(self._history)
        ok = sum(1 for h in self._history if h["recovered"])
        return {
            "total_attempts": total,
            "successes": ok,
            "failures": total - ok,
            "success_rate": f"{ok/total*100:.0f}%" if total else "N/A",
            "recipes_loaded": len(self._recipes),
        }
