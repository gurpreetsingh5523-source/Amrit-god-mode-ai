"""
dashboard_data.py — REAL Amrit state for the dashboard (no fabrication)
══════════════════════════════════════════════════════════════════════
Introspects the live system and writes workspace/amrit_dashboard/amrit_state.json
+ returns the dict. The dashboard embeds this so it shows the REAL 19 agents,
real crystallized skills, real FailureDNA patterns, etc. — never invented names
like the hallucinated "Hermes".

    python dashboard_data.py        # writes the JSON
"""
import json
import sqlite3
from pathlib import Path


def collect_state() -> dict:
    root = Path(__file__).parent
    state = {}

    # 1. Real registered agents (the source of truth, not a guess)
    try:
        import asyncio
        from orchestrator import Orchestrator
        from event_bus import EventBus
        async def _agents():
            orc = Orchestrator(event_bus=EventBus())
            await orc.initialize()
            names = sorted(orc.agents.keys())
            await orc.shutdown()
            return names
        agents = asyncio.run(_agents())
    except Exception:
        agents = []
    state["agents"] = agents
    state["agent_count"] = len(agents)

    # 2. Crystallized skills
    skills = []
    for f in (root / "workspace" / "skills").glob("*.json"):
        try:
            s = json.loads(f.read_text())
            skills.append({"id": s.get("skill_id"), "steps": s.get("steps"),
                           "uses": s.get("usage_count", 0),
                           "tokens_saved": s.get("tokens_saved", 0)})
        except Exception:
            pass
    state["skills"] = skills
    state["skill_count"] = len(skills)
    state["tokens_saved"] = sum(s.get("tokens_saved", 0) for s in skills)

    # 3. FailureDNA patterns
    patterns = []
    try:
        from failure_dna import FailureDNA
        db = FailureDNA().db
        with sqlite3.connect(db) as c:
            for row in c.execute(
                "select error_type, count, severity from failure_strands order by count desc limit 12"):
                patterns.append({"type": row[0], "count": row[1], "severity": row[2]})
    except Exception:
        pass
    state["failure_patterns"] = patterns
    state["failure_count"] = len(patterns)

    # 4. Evolution lessons
    try:
        lessons = json.loads((root / "workspace" / "evolution_lessons.json").read_text())
        state["lesson_count"] = len(lessons)
    except Exception:
        state["lesson_count"] = 0

    # 5. Additive test coverage (generated tests)
    state["generated_tests"] = len(list((root / "generated_tests").glob("test_*.py"))) \
        if (root / "generated_tests").exists() else 0

    # 6. Self-verify systems present
    state["self_verify"] = {
        "dual_brain": (root / "dual_brain_engine_v3.py").exists(),
        "web_verify": (root / "web_verify.py").exists(),
        "tester_loop": (root / "tester_agent.py").exists(),
    }

    # 6b. Connected capability subsystems (previously orphaned)
    try:
        from subsystems import SubsystemRegistry
        reg = SubsystemRegistry()
        state["subsystems"] = reg.loaded + getattr(reg, "io_loaded", [])
        state["subsystem_count"] = len(state["subsystems"])
    except Exception:
        state["subsystems"] = []
        state["subsystem_count"] = 0

    # 6c. Graph structure (nodes + links) so the 3D dashboard can render directly.
    nodes = [{"id": "core", "name": "Amrit Core", "group": "core", "color": "#ffcf5c", "val": 18}]
    links = []
    for a in state["agents"]:
        nodes.append({"id": a, "name": a, "group": "agent", "color": "#7aa2ff", "val": 5})
        links.append({"source": "core", "target": a, "label": "agent"})
    for sysname in ("memory", "tools", "self-verify"):
        nodes.append({"id": sysname, "name": sysname, "group": "sys", "color": "#4ade80", "val": 8})
        links.append({"source": "core", "target": sysname, "label": "system"})
    for s in state["skills"][:6]:
        sid = "skill:" + str(s.get("id", "?"))[:14]
        nodes.append({"id": sid, "name": sid, "group": "skill", "color": "#a875ff", "val": 4})
        links.append({"source": "core", "target": sid, "label": "skill"})
    state["nodes"] = nodes
    state["links"] = links

    # 7. Test suite counts
    def _count_tests(fp):
        try:
            return (root / fp).read_text().count("def test_")
        except Exception:
            return 0
    state["tests"] = {
        "godmode": _count_tests("test_godmode.py"),
        "integration": _count_tests("test_integration.py"),
    }
    return state


def write_state() -> dict:
    state = collect_state()
    out_dir = Path(__file__).parent / "workspace" / "amrit_dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "amrit_state.json").write_text(json.dumps(state, indent=2))
    return state


if __name__ == "__main__":
    s = write_state()
    print("✅ Real Amrit state written → workspace/amrit_dashboard/amrit_state.json")
    print(f"  agents: {s['agent_count']} {s['agents']}")
    print(f"  skills: {s['skill_count']} | tokens saved: {s['tokens_saved']}")
    print(f"  failure patterns: {s['failure_count']} | lessons: {s['lesson_count']}")
    print(f"  generated tests: {s['generated_tests']} | self-verify: {s['self_verify']}")
    print(f"  tests: {s['tests']}")
