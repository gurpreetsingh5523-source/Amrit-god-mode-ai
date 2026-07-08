"""
Failure Taxonomy — Structured error classification for AMRIT GODMODE.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Inspired by claw-code's classification system.
Every failure gets a class, severity, and retryable flag.
Enables: dashboards, auto-recovery, policy decisions.
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Union
import traceback
import time
from logger import setup_logger

logger = setup_logger("FailureTaxonomy")


class FailureClass(Enum):
    """Top-level failure categories — every error maps to exactly one."""
    TOOL_RUNTIME    = auto()   # Tool execution failed (bash, file, browser)
    LLM_CALL        = auto()   # LLM API error (timeout, rate limit, bad response)
    PERMISSION      = auto()   # Action denied by permission system
    AGENT_SPAWN     = auto()   # Agent failed to start / initialize
    DEPENDENCY      = auto()   # Missing package, binary, or service
    NETWORK         = auto()   # Connection, DNS, HTTP errors
    RESOURCE        = auto()   # OOM, disk full, GPU unavailable
    PARSE           = auto()   # JSON/YAML/AST parse failure
    VALIDATION      = auto()   # Input validation, schema mismatch
    STATE           = auto()   # Corrupt state, missing context, stale cache
    EXTERNAL_SVC    = auto()   # External API (HuggingFace, GitHub, Telegram)
    COMPILE_BUILD   = auto()   # Code compilation or build failure
    TEST            = auto()   # Test execution or assertion failure
    INFRA           = auto()   # System-level (process crash, signal, kernel)
    UNKNOWN         = auto()   # Unclassified — needs manual triage


class Severity(Enum):
    CRITICAL = "CRITICAL"   # System down, data loss risk
    HIGH     = "HIGH"       # Feature broken, needs immediate fix
    MEDIUM   = "MEDIUM"     # Degraded but functional, auto-retry possible
    LOW      = "LOW"        # Cosmetic, logging-only


@dataclass
class ClassifiedFailure:
    """A failure with its classification attached."""
    error: str
    failure_class: FailureClass
    severity: Severity
    retryable: bool = False
    source: str = ""
    context: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    original_exception: Optional[Exception] = field(default=None, repr=False)
    traceback_str: str = ""

    @property
    def tag(self) -> str:
        return f"{self.failure_class.name}/{self.severity.value}"

    def to_dict(self) -> dict:
        return {
            "error": self.error,
            "class": self.failure_class.name,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "source": self.source,
            "context": self.context,
            "timestamp": self.timestamp,
            "tag": self.tag,
        }


# ── Classification Rules ─────────────────────────────────────────
# Pattern → (FailureClass, Severity, retryable)
_RULES: list[tuple[list[str], FailureClass, Severity, bool]] = [
    # LLM errors
    (["timeout", "timed out", "deadline exceeded"],
     FailureClass.LLM_CALL, Severity.MEDIUM, True),
    (["rate limit", "429", "too many requests", "quota"],
     FailureClass.LLM_CALL, Severity.MEDIUM, True),
    (["ollama", "llm", "model not found", "no model"],
     FailureClass.LLM_CALL, Severity.HIGH, True),

    # Permission
    (["permission denied", "permissionerror", "not allowed", "access denied", "forbidden"],
     FailureClass.PERMISSION, Severity.HIGH, False),

    # Network
    (["connectionerror", "connection refused", "dns", "unreachable", "ssl", "certificate"],
     FailureClass.NETWORK, Severity.MEDIUM, True),
    (["httperror", "status 4", "status 5", "bad gateway", "502", "503"],
     FailureClass.NETWORK, Severity.MEDIUM, True),

    # Resource
    (["out of memory", "oom", "kIOGPU", "memory", "no space", "disk full"],
     FailureClass.RESOURCE, Severity.CRITICAL, False),
    (["gpu", "cuda", "metal", "mps"],
     FailureClass.RESOURCE, Severity.HIGH, False),

    # Dependency
    (["modulenotfounderror", "no module named", "import error", "importerror"],
     FailureClass.DEPENDENCY, Severity.HIGH, False),
    (["command not found", "not installed", "which:"],
     FailureClass.DEPENDENCY, Severity.HIGH, False),

    # Parse
    (["json", "jsondecodeerror", "yaml", "yamlscanner", "syntaxerror", "unexpected token"],
     FailureClass.PARSE, Severity.MEDIUM, False),
    (["ast", "indentationerror", "unterminated"],
     FailureClass.PARSE, Severity.MEDIUM, False),

    # Compile/Build
    (["compile", "build failed", "cargo", "gcc", "clang", "linker"],
     FailureClass.COMPILE_BUILD, Severity.HIGH, False),

    # Test
    (["assertionerror", "test failed", "assert ", "expected ", "unittest"],
     FailureClass.TEST, Severity.MEDIUM, False),

    # External services
    (["huggingface", "hf_hub", "gated", "401", "403"],
     FailureClass.EXTERNAL_SVC, Severity.MEDIUM, True),
    (["github", "git", "push", "pull", "merge conflict"],
     FailureClass.EXTERNAL_SVC, Severity.MEDIUM, False),
    (["telegram", "bot api"],
     FailureClass.EXTERNAL_SVC, Severity.LOW, True),

    # Validation
    (["valueerror", "invalid", "validation", "schema", "typeerror", "missing required"],
     FailureClass.VALIDATION, Severity.MEDIUM, False),

    # State
    (["keyerror", "attributeerror", "nonetype", "stale", "corrupt", "not initialized"],
     FailureClass.STATE, Severity.MEDIUM, False),

    # Tool runtime
    (["subprocess", "returncode", "command failed", "exit code", "calledprocesserror"],
     FailureClass.TOOL_RUNTIME, Severity.MEDIUM, True),

    # Infra
    (["killed", "signal", "segfault", "bus error", "core dumped"],
     FailureClass.INFRA, Severity.CRITICAL, False),
]


def classify(error: Union[str, Exception], source: str = "",
             context: Optional[dict] = None) -> ClassifiedFailure:
    """Classify an error string or exception into a structured failure."""
    exc = error if isinstance(error, Exception) else None
    err_str = str(error).lower()
    tb = ""
    if exc:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb = "".join(tb[-5:])  # last 5 frames

    for patterns, fc, sev, retry in _RULES:
        if any(p in err_str for p in patterns):
            cf = ClassifiedFailure(
                error=str(error)[:500],
                failure_class=fc, severity=sev, retryable=retry,
                source=source, context=context or {},
                original_exception=exc, traceback_str=tb,
            )
            logger.debug(f"Classified [{cf.tag}] {source}: {str(error)[:80]}")
            return cf

    # Unknown
    cf = ClassifiedFailure(
        error=str(error)[:500],
        failure_class=FailureClass.UNKNOWN, severity=Severity.MEDIUM,
        retryable=False, source=source, context=context or {},
        original_exception=exc, traceback_str=tb,
    )
    logger.warning(f"Unclassified failure from {source}: {str(error)[:80]}")
    return cf


class FailureTracker:
    """Accumulates classified failures for dashboarding / policy decisions."""

    def __init__(self, max_history: int = 500):
        self._history: list[ClassifiedFailure] = []
        self._max = max_history

    def record(self, failure: ClassifiedFailure):
        self._history.append(failure)
        if len(self._history) > self._max:
            self._history = self._history[-self._max:]

    def record_exception(self, exc: Exception, source: str = "", ctx: Optional[dict] = None):
        self.record(classify(exc, source, ctx))

    @property
    def count(self) -> int:
        return len(self._history)

    def by_class(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self._history:
            k = f.failure_class.name
            counts[k] = counts.get(k, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self._history:
            k = f.severity.value
            counts[k] = counts.get(k, 0) + 1
        return counts

    def recent(self, n: int = 10) -> list[dict]:
        return [f.to_dict() for f in self._history[-n:]]

    def retryable(self) -> list[ClassifiedFailure]:
        return [f for f in self._history if f.retryable]

    def critical(self) -> list[ClassifiedFailure]:
        return [f for f in self._history if f.severity == Severity.CRITICAL]

    def summary(self) -> dict:
        return {
            "total": self.count,
            "by_class": self.by_class(),
            "by_severity": self.by_severity(),
            "critical_count": len(self.critical()),
            "retryable_count": len(self.retryable()),
        }
