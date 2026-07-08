"""
test_integration.py — Amrit ENGINE self-tests (regression for orchestration bugs)
══════════════════════════════════════════════════════════════════════════════
test_godmode.py covers GENERATED output. THIS suite covers Amrit's OWN engine —
the multi-agent integration paths that had silent runtime bugs (path doubling,
loose deps, blocked CDN, cross-domain skill replay). Wired into self-evolution's
test phase so Amrit can DETECT + self-fix bugs in what it IS, not just what it builds.

Each test fails if its bug regresses.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


# ── BUG 1: coder output_dir / path-doubling ───────────────────────────────
def test_coder_output_dir_respected():
    from coder_agent import CoderAgent
    out_base, fn = CoderAgent.resolve_output_path("workspace/expense_app", "api.py")
    assert str(out_base) == "workspace/expense_app"
    assert fn == "api.py"


def test_coder_no_path_doubling():
    """Planner sometimes puts a full path in filename → must NOT double."""
    from coder_agent import CoderAgent
    out_base, fn = CoderAgent.resolve_output_path(
        "workspace/amrit_dashboard", "workspace/amrit_dashboard/index.html")
    assert str(out_base) == "workspace/amrit_dashboard"
    assert fn == "index.html"                      # basename only
    full = out_base / fn
    assert str(full).count("amrit_dashboard") == 1  # not doubled


def test_coder_bare_dir_gets_workspace_prefix():
    from coder_agent import CoderAgent
    out_base, _ = CoderAgent.resolve_output_path("myproj", "a.py")
    assert str(out_base) == "workspace/myproj"


# ── BUG 2: swarm deps tolerance (name/index/phantom) ──────────────────────
def _queen():
    from swarm import Queen
    from event_bus import EventBus
    from state_manager import StateManager
    return Queen(EventBus(), {}, StateManager())


def test_swarm_deps_by_name_and_phantom():
    from swarm import SwarmTask
    q = _queen()
    a = SwarmTask(id="aa", name="Build HTML", status="done")
    b = SwarmTask(id="bb", name="Add chat", depends_on=["Build HTML"])     # by name
    c = SwarmTask(id="cc", name="Stats", depends_on=["0"])                  # by index
    d = SwarmTask(id="dd", name="Polish", depends_on=["ghost-task"])        # phantom
    q.task_queue = [a, b, c, d]
    assert q._deps_met(b) is True
    assert q._deps_met(c) is True
    assert q._deps_met(d) is True      # phantom dep ignored → no stall


def test_swarm_deps_waits_for_unfinished():
    from swarm import SwarmTask
    q = _queen()
    a = SwarmTask(id="aa", name="Build", status="running")
    b = SwarmTask(id="bb", name="Next", depends_on=["Build"])
    q.task_queue = [a, b]
    assert q._deps_met(b) is False     # real unfinished dep → correctly waits


# ── BUG 3: web_verify blocked-CDN swap ────────────────────────────────────
def test_web_verify_swaps_blocked_cdn():
    from web_verify import swap_blocked_cdns
    bad = '<script src="https://cdnjs.cloudflare.com/ajax/libs/3d-force-graph/1.73.0/3d-force-graph.min.js"></script>'
    fixed = swap_blocked_cdns(bad)
    assert "cdnjs.cloudflare.com" not in fixed
    assert "cdn.jsdelivr.net/npm/3d-force-graph" in fixed


def test_web_verify_leaves_good_cdn():
    from web_verify import swap_blocked_cdns
    good = '<script src="https://cdn.jsdelivr.net/npm/3d-force-graph"></script>'
    assert swap_blocked_cdns(good) == good


# ── BUG 4: skill crystallization (no cross-domain replay, fresh-goal spec) ──
def test_skill_no_cross_domain_match():
    from skill_crystallizer import SkillCrystallizer
    import shutil
    d = Path("workspace/skills_test"); shutil.rmtree(d, ignore_errors=True)
    sc = SkillCrystallizer()
    sc._skills = []  # isolate
    sc.crystallize("build a fastapi analytics dashboard with charts",
                   [{"name": "x", "agent": "coder", "data": {"action": "generate"}}], True)
    # an unrelated goal must NOT match (high threshold)
    assert sc.find_match("translate a document to Punjabi") is None


def test_skill_replay_uses_new_goal_as_spec():
    from skill_crystallizer import SkillCrystallizer
    sc = SkillCrystallizer()
    skill = {"skill_id": "x", "steps": 2, "execution_path": [
        {"agent": "coder", "action": "generate", "name": "old api /stats"},
        {"agent": "tester", "action": "run", "name": "old test"}]}
    tasks = sc.replay_tasks(skill, "build a NEW expense tracker")
    assert len(tasks) == 2
    for t in tasks:
        assert t["data"]["spec"] == "build a NEW expense tracker"   # NEW goal, not old name
        assert t["data"]["goal"] == "build a NEW expense tracker"


# ── BUG 5: tester import/path normalization ───────────────────────────────
def test_tester_fixes_wrong_module_import():
    from tester_agent import TesterAgent
    bad = "from main import app\nclient = TestClient(main.app)\n\ndef test_x():\n    assert client.get('/').status_code == 200\n"
    fixed = TesterAgent._fix_imports(bad, "api", is_fastapi=True)
    assert "import api" in fixed
    assert "from main import" not in fixed
    assert "TestClient(api.app)" in fixed


def test_tester_extracts_code_from_prose():
    from tester_agent import TesterAgent
    reply = "Sure! Here are the tests:\n```python\nimport api\n\ndef test_a():\n    assert True\n```\nHope this helps!"
    code = TesterAgent._extract_code(reply)
    assert code.startswith("import api")
    assert "Hope this helps" not in code


# ── SAFETY WIRING: orphan safety subsystems now gate execution ────────────
def _tool_agent():
    from tool_agent import ToolAgent
    from event_bus import EventBus
    from state_manager import StateManager
    return ToolAgent(EventBus(), StateManager())


def test_safety_subsystems_wired():
    ta = _tool_agent()
    assert ta.code_safety is not None
    assert ta.safety_layer is not None
    assert ta.sandbox is not None


def test_sandbox_blocks_os_system_python():
    import asyncio
    ta = _tool_agent()
    r = asyncio.run(ta.execute({"data": {"tool": "run_python", "code": "import os\nos.system('echo x')"}}))
    assert "FAILED" in str(r) or r.get("status") == "error" or r.get("success") is False


def test_safety_layer_blocks_destructive_terminal():
    import asyncio
    ta = _tool_agent()
    r = asyncio.run(ta.execute({"data": {"tool": "terminal", "command": "sudo rm -rf /"}}))
    assert "FAILED" in str(r) or r.get("success") is False


def test_safe_code_still_runs():
    import asyncio
    ta = _tool_agent()
    r = asyncio.run(ta.execute({"data": {"tool": "run_python", "code": "print(40+2)"}}))
    assert "42" in str(r)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


# ── SUBSYSTEM WIRING: orphan capability engines now connected to brain ──────
def test_subsystem_registry_connects_all():
    from subsystems import SubsystemRegistry
    r = SubsystemRegistry()
    assert len(r.loaded) >= 15, f"only {len(r.loaded)} connected: {r.failed}"
    for key in ("self_graph", "evaluation_engine", "reward_engine",
                "error_analyzer", "dream_engine", "self_learning_loop"):
        assert r.get(key) is not None
