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
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

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
                                 "research"],
                        help="Execution mode")
    parser.add_argument("--config",  type=str,  default="config.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workflow",type=str,  help="Path to workflow YAML file")
    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = ConfigLoader(args.config)
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
