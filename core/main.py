"""
╔══════════════════════════════════════════════════════════════════════╗
║        AMRIT GODMODE — Autonomous Intelligence Platform             ║
║        100+ files | Voice | Vision | Self-Learning | Internet       ║
║        Version: 2.0.0  |  Production Ready                         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import argparse
import sys
from pathlib import Path

# ─── PATH INJECTION FOR MODULAR STRUCTURE ───
_base_dir = Path(__file__).resolve().parent
if _base_dir.name in ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]:
    _base_dir = _base_dir.parent
_subdirs = ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]
for _sd in _subdirs:
    _path_str = str(_base_dir / _sd)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)
# ───────────────────────────────────────────

from orchestrator import Orchestrator
from event_bus import EventBus
from logger import setup_logger
from banner import print_banner
from config_loader import ConfigLoader

logger = setup_logger("GODMODE")


async def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="AMRIT GODMODE — Autonomous AI Platform",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--goal",    type=str,  help="High-level goal to execute")
    parser.add_argument("--mode",    type=str,  default="interactive",
                        choices=["interactive", "autonomous", "voice", "vision",
                                 "internet", "godmode", "evolve", "selftest", "selffix",
                                 "research", "mcp", "swarm", "distributed"],
                        help="Execution mode")
    parser.add_argument("--config",  type=str,  default="config.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workflow",type=str,  help="Path to workflow YAML file")
    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    ConfigLoader(args.config)
    logger.info(f"AMRIT GODMODE starting in [{args.mode.upper()}] mode")

    event_bus    = EventBus()
    orchestrator = Orchestrator(event_bus=event_bus, config_path=args.config)

    try:
        await orchestrator.initialize()

        if args.dry_run and args.goal:
            tasks = await orchestrator.goal_parser.parse(args.goal)
            print("\n[DRY RUN] Parsed task graph:")
            for i, t in enumerate(tasks, 1):
                deps = t.get("depends_on", [])
                print(f"  {i}. [{t.get('agent'):12}] {t.get('name')} "
                      f"(pri={t.get('priority')}, deps={deps})")
            return

        if args.workflow:
            await orchestrator.run_workflow(args.workflow)
        elif args.mode == "godmode":
            await orchestrator.run_godmode()
        elif args.mode == "evolve":
            from self_evolution import SelfEvolution
            evo = SelfEvolution(orchestrator)
            if args.goal:
                await evo.run(max_cycles=5, single_task=args.goal)
            else:
                await evo.run(max_cycles=5)
        elif args.mode == "selftest":
            await orchestrator._run_selftest()
        elif args.mode == "selffix":
            await orchestrator._run_selffix()
        elif args.mode == "mcp":
            from mcp_server import MCPServer
            transport = "sse" if not args.goal else args.goal  # --goal sse|stdio
            server = MCPServer()
            await server.initialize(orchestrator)
            logger.info(f"Starting MCP server ({transport})")
            if transport == "stdio":
                await server.run_stdio()
            else:
                await server.run_sse()
        elif args.mode == "swarm":
            if args.goal:
                # 💎 SKILL CRYSTALLIZATION: replay a proven skill only if the goal
                # is a near-identical match (high threshold) AND it's been validated
                # before (usage_count>=1). Otherwise plan fresh.
                tasks = None
                _replayed = False
                _sc = None
                _replayed_skill_id = None
                try:
                    from skill_crystallizer import SkillCrystallizer
                    _sc = SkillCrystallizer()
                    _skill = _sc.find_match(args.goal)
                    if _skill and _skill.get("success_rate", 1.0) >= 0.9:
                        tasks = _sc.replay_tasks(_skill, args.goal)
                        _replayed = True
                        _replayed_skill_id = _skill["skill_id"]
                        logger.info(f"⚡ Replaying proven skill '{_skill['skill_id']}' "
                                    f"(rate {_skill.get('success_rate',1.0):.2f}, "
                                    f"{len(tasks)} steps) — planner skipped")
                        # NOTE: outcome is recorded AFTER the swarm runs (real result).
                except Exception as _e:
                    logger.debug(f"skill match skipped: {_e}")

                # Use planner to decompose goal into multi-step tasks (if no skill match)
                planner = orchestrator.get_agent("planner")
                if tasks is None and planner:
                    plan_result = await planner.execute({"name": args.goal, "data": {"goal": args.goal}})
                    tasks = plan_result.get("plan", [])
                    # If planner returned direct output (simple task), wrap it
                    if not tasks or plan_result.get("direct"):
                        tasks = [{"name": args.goal, "agent": "coder", "priority": 1,
                                  "data": {"spec": args.goal, "action": "generate"}}]
                    # Inject original goal as spec into each task's data
                    import re as _re
                    _fn_match = _re.search(r'(\w+\.py)\b', args.goal)
                    _target_fn = _fn_match.group(1) if _fn_match else ""
                    # Extract a target output DIR from the goal. Only treat it as a
                    # directory when it ends with a slash (e.g. "workspace/expense_app/").
                    # Drop any filename segments (those containing a ".") so a path like
                    # "workspace/learned_patterns.json" or ".../index.html" does NOT
                    # become a folder (the recurring nested-path bug).
                    _out_dir = "workspace"
                    _dir_match = _re.search(r'workspace/([\w\-/]+)/', args.goal)
                    if _dir_match:
                        _segs = [s for s in _dir_match.group(1).split('/') if '.' not in s]
                        if _segs:
                            _out_dir = "workspace/" + "/".join(_segs)
                    for t in tasks:
                        t.setdefault("data", {})
                        t["data"].setdefault("spec", t.get("name", args.goal))
                        t["data"].setdefault("goal", args.goal)
                        t["data"].setdefault("output_dir", _out_dir)
                        if _target_fn:
                            t["data"].setdefault("filename", _target_fn)
                elif tasks is None:
                    # No skill match AND no planner → single fallback task
                    tasks = [{"name": args.goal, "agent": "coder", "priority": 1,
                              "data": {"spec": args.goal, "action": "generate"}}]
                result = await orchestrator.queen.spawn_swarm(
                    args.goal, tasks, allow_crystallize=not _replayed)
                logger.info(f"Swarm result: {result.get('completed')}/{result.get('total')} done")
                # Close the feedback loop: record the REAL outcome of a replayed skill
                # so its success_rate reflects reality (bad skills get pruned).
                if _replayed and _sc and _replayed_skill_id:
                    _ok = result.get("completed", 0) >= max(1, result.get("total", 1) - 1)
                    _sc.record_usage(_replayed_skill_id, success=_ok,
                                     tokens_saved=800 if _ok else 0)
                    logger.info(f"📊 skill '{_replayed_skill_id}' replay outcome recorded: "
                                f"{'success' if _ok else 'FAILURE (rate will drop)'}")
            else:
                print("\n  \u274c --goal required for swarm mode")
                print("  Example: python3 main.py --mode swarm --goal 'build REST API'\n")
        elif args.mode == "research":
            if args.goal:
                await orchestrator._run_research(args.goal)
            else:
                print("\n  ❌ --goal required for research mode")
                print("  Example: python3 main.py --mode research --goal 'quantum computing applications'\n")
        elif args.mode == "voice":
            await orchestrator.run_voice_mode()
        elif args.mode == "vision":
            await orchestrator.run_vision_mode()
        elif args.mode == "internet":
            await orchestrator.run_internet_mode()
        elif args.mode == "distributed":
            if args.goal:
                # Optionally allow agent_id via --agent-id
                agent_id = getattr(args, "agent_id", None) if hasattr(args, "agent_id") else None
                result = await orchestrator.run_goal_with_agent(args.goal, agent_id=agent_id)
                print("\n[Distributed Agent Result]")
                print(result)
            else:
                print("\n  ❌ --goal required for distributed mode")
                print("  Example: python3 main.py --mode distributed --goal 'Learn Python and build a project'\n")
        elif args.goal:
            await orchestrator.run_goal(args.goal)
        else:
            await orchestrator.run_interactive()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down...")
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
