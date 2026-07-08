"""
Task Packet — Machine-readable, retryable task encoding.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A TaskPacket is a complete, self-contained instruction unit.
Contains everything an agent needs: objective, scope, branch
policy, acceptance tests, escalation rules.
Packets are serializable, diffable, versionable.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Optional
import json
import time
import hashlib
from logger import setup_logger

logger = setup_logger("TaskPacket")


class BranchPolicy(Enum):
    NEW_BRANCH    = "new_branch"       # Always create feature branch
    CURRENT       = "current"          # Work on current branch
    AUTO          = "auto"             # Let agent decide based on scope


class CommitPolicy(Enum):
    PER_SUBTASK   = "per_subtask"      # Commit after each subtask
    ON_COMPLETE   = "on_complete"      # Single commit when done
    MANUAL        = "manual"           # Don't auto-commit


class EscalationPolicy(Enum):
    RETRY_THEN_ESCALATE = "retry_then_escalate"  # Retry N times, then escalate
    ESCALATE_IMMEDIATE  = "escalate_immediate"   # Escalate on first failure
    SILENT_FAIL         = "silent_fail"           # Log and continue


class PacketStatus(Enum):
    PENDING    = auto()
    ACTIVE     = auto()
    BLOCKED    = auto()
    COMPLETED  = auto()
    FAILED     = auto()
    ESCALATED  = auto()


@dataclass
class AcceptanceTest:
    """A single pass/fail condition for task completion."""
    description: str
    check_type: str = "manual"        # "manual", "command", "file_exists", "test_pass"
    check_value: str = ""             # Command to run, file to check, etc.
    passed: bool = False


@dataclass
class TaskPacket:
    """Complete, self-contained task instruction for an agent."""

    # ── Core ──────────────────────────────────
    objective: str                         # What to accomplish
    assigned_agent: str = ""               # Which agent handles this
    priority: int = 5                      # 1 (critical) → 10 (nice-to-have)

    # ── Scope ─────────────────────────────────
    scope_files: list[str] = field(default_factory=list)     # Files in scope
    scope_dirs: list[str] = field(default_factory=list)      # Directories in scope
    scope_description: str = ""            # Natural language scope

    # ── Policies ──────────────────────────────
    branch_policy: BranchPolicy = BranchPolicy.AUTO
    commit_policy: CommitPolicy = CommitPolicy.PER_SUBTASK
    escalation_policy: EscalationPolicy = EscalationPolicy.RETRY_THEN_ESCALATE
    max_retries: int = 3

    # ── Acceptance ────────────────────────────
    acceptance_tests: list[AcceptanceTest] = field(default_factory=list)

    # ── Context ───────────────────────────────
    context: dict = field(default_factory=dict)   # Extra info for the agent
    parent_packet_id: str = ""            # If this is a subtask
    depends_on: list[str] = field(default_factory=list)  # Packet IDs that must complete first

    # ── Tracking ──────────────────────────────
    status: PacketStatus = PacketStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    attempt: int = 0
    error_log: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)

    # ── Identity ──────────────────────────────
    packet_id: str = ""

    def __post_init__(self):
        if not self.packet_id:
            raw = f"{self.objective}:{self.created_at}:{id(self)}"
            self.packet_id = hashlib.sha256(raw.encode()).hexdigest()[:12]

    # ── Lifecycle ─────────────────────────────
    def start(self):
        self.status = PacketStatus.ACTIVE
        self.started_at = time.time()
        self.attempt += 1
        logger.info(f"[{self.packet_id}] Started (attempt {self.attempt}): {self.objective[:60]}")

    def complete(self, result: Optional[dict] = None):
        self.status = PacketStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result or {}
        logger.info(f"[{self.packet_id}] Completed in {self.elapsed:.1f}s")

    def fail(self, error: str):
        self.error_log.append(error)
        if self.attempt >= self.max_retries:
            if self.escalation_policy == EscalationPolicy.ESCALATE_IMMEDIATE or \
               self.escalation_policy == EscalationPolicy.RETRY_THEN_ESCALATE:
                self.status = PacketStatus.ESCALATED
                logger.warning(f"[{self.packet_id}] Escalated after {self.attempt} attempts")
            else:
                self.status = PacketStatus.FAILED
                logger.error(f"[{self.packet_id}] Failed silently after {self.attempt} attempts")
        else:
            self.status = PacketStatus.PENDING  # Ready for retry
            logger.info(f"[{self.packet_id}] Failed attempt {self.attempt}, will retry")

    def block(self, reason: str = ""):
        self.status = PacketStatus.BLOCKED
        self.error_log.append(f"BLOCKED: {reason}")
        logger.warning(f"[{self.packet_id}] Blocked: {reason}")

    # ── Queries ───────────────────────────────
    @property
    def elapsed(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at if self.started_at else 0.0

    @property
    def is_terminal(self) -> bool:
        return self.status in (PacketStatus.COMPLETED, PacketStatus.FAILED, PacketStatus.ESCALATED)

    @property
    def can_retry(self) -> bool:
        return not self.is_terminal and self.attempt < self.max_retries

    def acceptance_passed(self) -> bool:
        return all(t.passed for t in self.acceptance_tests)

    # ── Serialization ─────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        d["branch_policy"] = self.branch_policy.value
        d["commit_policy"] = self.commit_policy.value
        d["escalation_policy"] = self.escalation_policy.value
        d["status"] = self.status.name
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "TaskPacket":
        d = dict(d)  # shallow copy
        d["branch_policy"] = BranchPolicy(d.get("branch_policy", "auto"))
        d["commit_policy"] = CommitPolicy(d.get("commit_policy", "per_subtask"))
        d["escalation_policy"] = EscalationPolicy(d.get("escalation_policy", "retry_then_escalate"))
        d["status"] = PacketStatus[d.get("status", "PENDING")]
        d["acceptance_tests"] = [AcceptanceTest(**t) if isinstance(t, dict) else t
                                  for t in d.get("acceptance_tests", [])]
        return cls(**d)


class PacketStore:
    """In-memory packet registry with lookup and status queries."""

    def __init__(self):
        self._packets: dict[str, TaskPacket] = {}

    def add(self, packet: TaskPacket):
        self._packets[packet.packet_id] = packet

    def get(self, packet_id: str) -> Optional[TaskPacket]:
        return self._packets.get(packet_id)

    def pending(self) -> list[TaskPacket]:
        return [p for p in self._packets.values() if p.status == PacketStatus.PENDING]

    def active(self) -> list[TaskPacket]:
        return [p for p in self._packets.values() if p.status == PacketStatus.ACTIVE]

    def escalated(self) -> list[TaskPacket]:
        return [p for p in self._packets.values() if p.status == PacketStatus.ESCALATED]

    def by_agent(self, agent: str) -> list[TaskPacket]:
        return [p for p in self._packets.values() if p.assigned_agent == agent]

    def ready(self) -> list[TaskPacket]:
        """Packets that are pending and have all dependencies met."""
        done_ids = {p.packet_id for p in self._packets.values() if p.status == PacketStatus.COMPLETED}
        return [
            p for p in self.pending()
            if all(dep in done_ids for dep in p.depends_on)
        ]

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for p in self._packets.values():
            k = p.status.name
            counts[k] = counts.get(k, 0) + 1
        return {"total": len(self._packets), "by_status": counts}
