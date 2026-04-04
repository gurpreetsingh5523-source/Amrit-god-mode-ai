"""
Orchestrator — GODMODE Central Command.
Manages 14 agents, task graph, event bus, workflow engine,
interactive CLI, and all execution modes.
"""
import asyncio
from typing import Dict, Optional
from event_bus import EventBus
from task_graph import TaskGraph
from state_manager import StateManager
from scheduler import Scheduler
from autonomy_loop import AutonomyLoop
from workflow_engine import WorkflowEngine
from goal_parser import GoalParser
from logger import setup_logger
from config_loader import ConfigLoader

# ── Smart Infrastructure (v2) ─────────────────────────────────
from failure_taxonomy import classify, FailureTracker
from permission_enforcer import PermissionEnforcer
from permission_manager import PermissionManager
from task_packet import TaskPacket, PacketStore
from recovery_recipes import RecoveryEngine
from policy_engine import PolicyEngine
from worker_lifecycle import WorkerLifecycleManager

logger = setup_logger("Orchestrator")


class Orchestrator:
    def __init__(self, event_bus: EventBus, config_path: str = "config.yaml"):
        self.event_bus   = event_bus
        self.config      = ConfigLoader(config_path)
        self.task_graph  = TaskGraph()
        self.state       = StateManager()
        self.scheduler   = Scheduler(self.task_graph)
        self.goal_parser = GoalParser()
        self.autonomy    = AutonomyLoop(self)
        self.workflow    = WorkflowEngine(self)
        self.agents: Dict[str, object] = {}
        self._ready      = False

        # ── Smart Infrastructure (v2) ─────────────────────────
        self.perm_manager  = PermissionManager()
        self.enforcer      = PermissionEnforcer(self.perm_manager)
        self.failure_tracker = FailureTracker()
        self.packet_store  = PacketStore()
        self.recovery      = RecoveryEngine()
        self.policy        = PolicyEngine()
        self.lifecycle     = WorkerLifecycleManager()

    # ── Init ──────────────────────────────────────────────────────

    async def initialize(self):
        if self._ready: return
        logger.info("Initializing AMRIT GODMODE...")
        await self.event_bus.start()
        self._load_agents()
        self._register_handlers()
        await self.state.set("status", "running")
        self._ready = True
        logger.info(f"GODMODE ready ✅  ({len(self.agents)} agents loaded)")

    def _load_agents(self):
        from planner_agent    import PlannerAgent
        from coder_agent      import CoderAgent
        from research_agent   import ResearchAgent
        from tester_agent     import TesterAgent
        from debugger_agent   import DebuggerAgent
        from tool_agent       import ToolAgent
        from memory_agent     import MemoryAgent
        from upgrade_agent    import UpgradeAgent
        from monitor_agent    import MonitorAgent
        from voice_agent      import VoiceAgent
        from vision_agent     import VisionAgent
        from internet_agent   import InternetAgent
        from dataset_agent    import DatasetAgent
        from simulation_agent import SimulationAgent

        self.agents = {
            "planner":    PlannerAgent(self.event_bus, self.state),
            "coder":      CoderAgent(self.event_bus, self.state),
            "researcher": ResearchAgent(self.event_bus, self.state),
            "tester":     TesterAgent(self.event_bus, self.state),
            "debugger":   DebuggerAgent(self.event_bus, self.state),
            "tool":       ToolAgent(self.event_bus, self.state),
            "memory":     MemoryAgent(self.event_bus, self.state),
            "upgrade":    UpgradeAgent(self.event_bus, self.state),
            "monitor":    MonitorAgent(self.event_bus, self.state),
            "voice":      VoiceAgent(self.event_bus, self.state),
            "vision":     VisionAgent(self.event_bus, self.state),
            "internet":   InternetAgent(self.event_bus, self.state),
            "dataset":    DatasetAgent(self.event_bus, self.state),
            "simulation": SimulationAgent(self.event_bus, self.state),
        }
        logger.info(f"Agents: {list(self.agents.keys())}")
        # Register all agents in lifecycle manager
        for name in self.agents:
            self.lifecycle.register(name)
            self.lifecycle.mark_initializing(name)
            self.lifecycle.mark_ready(name)

    def _register_handlers(self):
        self.event_bus.subscribe("task.new",       self._on_new_task)
        self.event_bus.subscribe("task.complete",  self._on_task_done)
        self.event_bus.subscribe("agent.error",    self._on_error)
        self.event_bus.subscribe("system.upgrade", self._on_upgrade)
        # v2 smart handlers
        self.event_bus.subscribe("recovery.success",  self._on_recovery)
        self.event_bus.subscribe("recovery.failed",   self._on_recovery)
        self.event_bus.subscribe("recovery.escalated", self._on_recovery)

    # ── Event Handlers ────────────────────────────────────────────

    async def _on_new_task(self, event):
        self.task_graph.add(event.data)

    async def _on_task_done(self, event):
        logger.debug(f"Task done event: {event.data.get('name')}")

    async def _on_error(self, event):
        logger.error(f"Agent error event: {event.data}")
        # ── v2: Classify + track + auto-recover ──
        error_str = str(event.data.get("error", event.data))
        source = event.data.get("agent", "unknown")
        failure = classify(error_str, source=source)
        self.failure_tracker.record(failure)
        self.lifecycle.mark_failed(source, reason=error_str[:100])
        # Run policy engine
        ctx = {
            "failure_retryable": failure.retryable,
            "recovery_attempts": 0,
            "recent_failures": self.failure_tracker.recent(20),
        }
        actions = self.policy.evaluate(ctx)
        for action in actions:
            if action.action_type.name == "RECOVER_ONCE":
                await self.recovery.attempt_recovery(
                    failure,
                    event_publish=self.event_bus.publish,
                )
            elif action.action_type.name == "ESCALATE":
                logger.critical(f"⚠️  ESCALATION: {action.description}")
            elif action.action_type.name == "RESTART_AGENT":
                logger.info(f"Restarting agent: {source}")
                self.lifecycle.transition(source, __import__('worker_lifecycle').WorkerStatus.INITIALIZING, "auto-restart")
                self.lifecycle.mark_ready(source)

    async def _on_upgrade(self, event):
        logger.info(f"System upgrade triggered: {event.data}")

    async def _on_recovery(self, event):
        logger.info(f"Recovery event: {event.data.get('recipe', '?')} — recovered={event.data.get('recovered')}")

    # ── Execution Modes ───────────────────────────────────────────

    async def run_goal(self, goal: str):
        logger.info(f"Goal: {goal!r}")
        await self.state.set("current_goal", goal)
        tasks = await self.goal_parser.parse(goal)
        self.task_graph.add_many(tasks)
        logger.info(f"Graph: {len(tasks)} tasks")
        await self.autonomy.run()
        self.task_graph.print_summary()

    async def run_interactive(self):
        print("\n\033[92m⚡ GODMODE Interactive\033[0m  (type 'help' for commands / 'ਮਦਦ' ਲਈ ਟਾਈਪ ਕਰੋ)\n")
        while True:
            try:
                inp = input("\033[95m[GODMODE]> \033[0m").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not inp: continue
            cmd = inp.lower()
            if cmd in ("exit", "quit", "ਬੰਦ"): break
            elif cmd in ("help", "ਮਦਦ"):    self._print_help()
            elif cmd in ("status", "ਸਥਿਤੀ"):  self._print_status()
            elif cmd in ("agents", "ਏਜੰਟ"):  self._print_agents()
            elif cmd in ("graph", "ਗ੍ਰਾਫ"):   self.task_graph.print_summary()
            elif cmd in ("history", "ਇਤਿਹਾਸ"): self._print_history()
            elif cmd.startswith("goal "):
                await self.run_goal(inp[5:])
            elif cmd == "godmode": await self.run_godmode()
            elif cmd in ("evolve", "ਵਿਕਾਸ"):
                await self._run_evolve_cycles()
            elif cmd in ("selftest", "ਸਵੈ-ਟੈਸਟ"):
                await self._run_selftest()
            elif cmd in ("selffix", "ਸਵੈ-ਠੀਕ"):
                await self._run_selffix()
            elif cmd.startswith("research ") or cmd.startswith("ਖੋਜ "):
                topic = inp.split(" ", 1)[1] if " " in inp else ""
                await self._run_research(topic)
            elif cmd.startswith("arxiv "):
                await self._run_arxiv(inp[6:])
            elif cmd.startswith("pubmed "):
                await self._run_pubmed(inp[7:])
            elif cmd.startswith("hypothesis ") or cmd.startswith("ਪਰੀਕਲਪਨਾ "):
                topic = inp.split(" ", 1)[1] if " " in inp else ""
                await self._run_hypothesis(topic)
            elif cmd.startswith("think ") or cmd.startswith("ਸੋਚ "):
                question = inp.split(" ", 1)[1] if " " in inp else ""
                await self._run_think(question)
            elif cmd.startswith("optimize ") or cmd.startswith("ਅਨੁਕੂਲ "):
                filepath = inp.split(" ", 1)[1] if " " in inp else ""
                await self._run_optimize(filepath)
            elif cmd in ("memory", "ਯਾਦਦਾਸ਼ਤ"):
                await self._run_memory_stats()
            elif cmd in ("llmstats", "ਅੰਕੜੇ"):
                self._run_llm_stats()
            elif cmd in ("internet", "ਇੰਟਰਨੈੱਟ"):
                await self.run_internet_mode()
            elif cmd in ("voice", "ਅਵਾਜ਼"):
                await self.run_voice_mode()
            elif cmd in ("clear", "ਸਾਫ਼"):
                import os; os.system("clear")
            else:
                await self.run_goal(inp)

    async def run_godmode(self):
        """Ultimate autonomous mode — self-evolution: analyze, fix, optimize, learn, repeat."""
        from self_evolution import SelfEvolution
        logger.info("🔥 GODMODE ENGAGED — Full Self-Evolution / ਪੂਰਾ ਸਵੈ-ਵਿਕਾਸ")
        print("\n\033[91m  ⚡ GODMODE: Self-Evolution Engine Active ⚡\033[0m")
        print("  ਸਿਸਟਮ ਆਪਣੇ ਆਪ ਨੂੰ ਚੈੱਕ, ਠੀਕ, ਤੇਜ਼ ਬਣਾਏਗਾ")
        print("  Press Ctrl+C to stop / ਰੋਕਣ ਲਈ Ctrl+C ਦਬਾਓ\n")
        evo = SelfEvolution(self)
        try:
            await evo.run(max_cycles=0)  # infinite — true autonomous
        except KeyboardInterrupt:
            evo.stop()
            print("\n\033[93m  ⏹  GODMODE stopped by user.\033[0m\n")

    async def run_voice_mode(self):
        v = self.get_agent("voice")
        if v: await v.listen_loop(self)
        else: logger.error("Voice agent not available")

    async def run_vision_mode(self):
        v = self.get_agent("vision")
        if v: await v.interactive_loop(self)
        else: logger.error("Vision agent not available")

    async def run_internet_mode(self):
        a = self.get_agent("internet")
        if a: await a.interactive_loop(self)
        else: logger.error("Internet agent not available")

    async def run_workflow(self, path: str):
        result = await self.workflow.run_file(path)
        logger.info(f"Workflow result: {result.get('status')}")

    # ── Self-Evolution Commands ───────────────────────────────────

    async def _run_evolve_cycles(self):
        """Run 3 self-evolution cycles: analyze → test → fix → optimize → learn."""
        from self_evolution import SelfEvolution
        print("\n\033[93m  🔄 Running 3 Self-Evolution Cycles...\033[0m\n")
        evo = SelfEvolution(self)
        await evo.run(max_cycles=3)
        print("\033[92m  ✅ Evolution complete!\033[0m\n")

    async def _run_selftest(self):
        """Run a single self-analysis + test cycle and print report."""
        from self_evolution import SelfEvolution
        print("\n\033[93m  🧪 Running Self-Test...\033[0m\n")
        evo = SelfEvolution(self)
        report = await evo.run_single_analysis()
        print(f"  📊 Files: {report['total_files']} | Quality: {report['avg_quality']}")
        print(f"  ✅ Tests Passed: {report['test_passed']} | ❌ Failed: {report['test_failed']}")
        print(f"  ⚠️  Import Errors: {report['import_errors']}")
        if report["weakest_files"]:
            print("  📉 Weakest files:")
            for f, s in report["weakest_files"]:
                print(f"      {f}: {s:.2f}")
        if report["import_error_details"]:
            print("  🚨 Import Errors:")
            for ie in report["import_error_details"][:5]:
                print(f"      {ie['module']}: {ie['error'][:80]}")
        print()

    async def _run_selffix(self):
        """Run one fix cycle: analyze → test → fix → test again."""
        from self_evolution import SelfEvolution
        print("\n\033[93m  🔧 Running Self-Fix Cycle...\033[0m\n")
        evo = SelfEvolution(self)
        report = await evo.run_fix_cycle()
        icon = "✅" if report.get("improved") else "➖"
        print(f"  {icon} Before: {report['before']['passed']}✅ {report['before']['failed']}❌")
        print(f"  {icon} After:  {report['after']['passed']}✅ {report['after']['failed']}❌")
        print()

    # ── Scientific Research Commands ──────────────────────────────

    async def _run_research(self, topic: str):
        """Full scientific research pipeline."""
        from research_brain import ResearchBrain
        print(f"\n\033[96m  🔬 Full Research Pipeline: {topic}\033[0m\n")
        brain = ResearchBrain(self)
        report = await brain.full_research(topic)

        # Print summary
        steps = report.get("steps", {})
        print(f"\n  {'─' * 50}")
        print(f"  │ 🔬 RESEARCH COMPLETE / ਖੋਜ ਮੁਕੰਮਲ")
        print(f"  │ ⏱  Time: {report.get('elapsed_seconds', 0)}s")
        if steps.get("literature"):
            print(f"  │ 📚 Literature: {steps['literature'].get('results', 0)} sources")
        if steps.get("arxiv"):
            print(f"  │ 📄 arXiv papers: {len(steps['arxiv'])}")
        if steps.get("hypotheses"):
            print(f"  │ 💡 Hypotheses: {len(steps['hypotheses'])}")
            for i, h in enumerate(steps["hypotheses"][:3], 1):
                hyp = h.get("hypothesis", str(h))[:80]
                print(f"  │    {i}. {hyp}")
        print(f"  │ 📝 Report saved in workspace/research/")
        print(f"  {'─' * 50}\n")

    async def _run_arxiv(self, query: str):
        """Search arXiv for papers."""
        internet = self.get_agent("internet")
        if not internet:
            print("  ❌ Internet agent not available")
            return
        print(f"\n\033[96m  📄 Searching arXiv: {query}\033[0m\n")
        result = await internet.execute({
            "name": f"arXiv: {query}",
            "data": {"action": "arxiv", "query": query, "max_results": 5}
        })
        papers = result.get("papers", [])
        if papers:
            for i, p in enumerate(papers, 1):
                print(f"  {i}. {p.get('title', 'N/A')}")
                print(f"     📅 {p.get('date', '')} | 👤 {', '.join(p.get('authors', []))}")
                print(f"     🔗 {p.get('url', '')}")
                print()
        print(f"  📊 Summary: {result.get('summary', '')[:300]}\n")

    async def _run_pubmed(self, query: str):
        """Search PubMed for medical papers."""
        internet = self.get_agent("internet")
        if not internet:
            print("  ❌ Internet agent not available")
            return
        print(f"\n\033[96m  🏥 Searching PubMed: {query}\033[0m\n")
        result = await internet.execute({
            "name": f"PubMed: {query}",
            "data": {"action": "pubmed", "query": query, "max_results": 5}
        })
        papers = result.get("papers", [])
        if papers:
            for i, p in enumerate(papers, 1):
                print(f"  {i}. {p.get('title', 'N/A')}")
                print(f"     📅 {p.get('date', '')} | 📰 {p.get('journal', '')}")
                print(f"     🔗 {p.get('url', '')}")
                print()
        print(f"  📊 Summary: {result.get('summary', '')[:300]}\n")

    async def _run_hypothesis(self, observation: str):
        """Generate hypotheses from an observation."""
        from research_brain import ResearchBrain
        print(f"\n\033[96m  💡 Generating Hypotheses: {observation[:60]}\033[0m\n")
        brain = ResearchBrain(self)
        hypotheses = await brain.generate_hypotheses(observation)
        for i, h in enumerate(hypotheses, 1):
            hyp = h.get("hypothesis", str(h))
            conf = h.get("confidence", "?")
            test = h.get("test", "")
            print(f"  {i}. 💡 {hyp}")
            print(f"     🎯 Confidence: {conf}")
            if test:
                print(f"     🧪 Test: {test[:100]}")
            print()

    # ── Deep Thinking Commands ────────────────────────────────────

    async def _run_think(self, question: str):
        """Deep multi-candidate reasoning — ਡੂੰਘੀ ਸੋਚ."""
        from reasoning_engine import ReasoningEngine
        print(f"\n\033[96m  🧠 Deep Thinking: {question[:60]}\033[0m\n")
        engine = ReasoningEngine(self)
        result = await engine.think(question)

        print(f"  {'─' * 50}")
        print(f"  │ 🧠 REASONING RESULT / ਸੋਚ ਦਾ ਨਤੀਜਾ")
        print(f"  │ 📊 Confidence: {result.get('confidence', '?')}")
        print(f"  │ ⚡ Complexity: {result.get('complexity', '?')}")
        print(f"  │ 🔬 Strategy: {result.get('strategy', '?')}")
        print(f"  │ ⏱  Time: {result.get('elapsed', 0)}s")
        if result.get("all_scores"):
            print(f"  │ 📈 Scores: {result['all_scores']}")
        if result.get("validation", {}).get("critique"):
            crit = result["validation"]["critique"][:150]
            print(f"  │ 🔍 Validation: {crit}")
        print(f"  {'─' * 50}")
        print(f"\n{result.get('answer', 'No answer')}\n")

    async def _run_optimize(self, filepath: str):
        """Run code optimization analysis on a file."""
        debugger = self.get_agent("debugger")
        if not debugger:
            print("  ❌ Debugger agent not available")
            return
        print(f"\n\033[96m  ⚡ Optimizing: {filepath}\033[0m\n")
        result = await debugger.execute({
            "name": f"Optimize {filepath}",
            "data": {"action": "optimize", "file": filepath}
        })
        suggestions = result.get("suggestions", [])
        if suggestions:
            for i, s in enumerate(suggestions, 1):
                stype = s.get("type", "?")
                msg = s.get("message", str(s))[:120]
                line = s.get("line", "")
                loc = f" (line {line})" if line else ""
                print(f"  {i}. [{stype}]{loc}: {msg}")
            print()
        else:
            print("  ✅ No optimization issues found!\n")

    async def _run_memory_stats(self):
        """Show unified memory system statistics."""
        memory = self.get_agent("memory")
        if not memory:
            print("  ❌ Memory agent not available")
            return
        result = await memory.execute({
            "name": "Memory Stats",
            "data": {"action": "stats"}
        })
        print(f"\n  \033[93m🧠 Memory System Stats / ਯਾਦਦਾਸ਼ਤ ਅੰਕੜੇ\033[0m")
        print(f"  ├── Context Buffer: {result.get('context_size', '?')} items")
        print(f"  ├── Long-Term Keys: {result.get('long_term_keys', '?')}")
        print(f"  ├── Knowledge Topics: {result.get('knowledge_topics', '?')}")
        print(f"  ├── Episodes: {result.get('episodes', '?')}")
        xp = result.get('experience_total', {})
        print(f"  ├── Experience: {xp.get('total', 0)} total "
              f"({xp.get('success', 0)}✅ {xp.get('failed', 0)}❌)")
        fp = result.get('failure_patterns', {})
        print(f"  ├── Failure Patterns: {fp.get('total_patterns', 0)} "
              f"({fp.get('fixed', 0)} fixed, {fp.get('unfixed', 0)} unfixed)")
        pl = result.get('plans', {})
        print(f"  └── Plans: {pl.get('total_plans', 0)}")
        print()

    def _run_llm_stats(self):
        """Show LLM call statistics."""
        try:
            from llm_router import LLMRouter
            stats = LLMRouter().get_stats()
            print(f"\n  \033[93m📊 LLM Statistics / LLM ਅੰਕੜੇ\033[0m")
            print(f"  ├── Total Calls: {stats.get('total', 0)}")
            print(f"  ├── Cache Hits: {stats.get('cache_hits', 0)} "
                  f"({stats.get('cache_hit_rate', 0)*100:.0f}%)")
            print(f"  ├── Errors: {stats.get('errors', 0)}")
            print(f"  ├── Avg Latency: {stats.get('avg_latency', 0)}s")
            print(f"  ├── Cache Size: {stats.get('cache_size', 0)} entries")
            by_model = stats.get("by_model", {})
            if by_model:
                print(f"  └── By Model:")
                for model, ms in by_model.items():
                    avg = round(ms['latency'] / max(ms['calls'], 1), 2)
                    print(f"       {model}: {ms['calls']} calls, avg {avg}s")
            print()
        except Exception as e:
            print(f"  Could not load LLM stats: {e}\n")

    # ── Agent Access ──────────────────────────────────────────────

    def get_agent(self, name: str):
        return self.agents.get(name)

    async def get_or_create_agent(self, name: str, task_data: dict = None):
        """ਜੇ ਏਜੰਟ ਮੌਜੂਦ ਹੈ ਤਾਂ ਵਾਪਸ ਕਰੋ, ਨਹੀਂ ਤਾਂ ਨਵਾਂ ਬਣਾਓ।"""
        agent = self.agents.get(name)
        if agent:
            return agent

        logger.info(f"Agent '{name}' not found — attempting auto-creation")
        try:
            coder = self.get_agent("coder")
            if not coder:
                logger.warning("Cannot auto-create agent: coder agent unavailable")
                return self.get_agent("planner")  # fallback

            # Generate agent code
            spec = (f"Create a new GODMODE agent class called '{name.title()}Agent' "
                    f"that extends BaseAgent. It should handle task: {task_data or name}. "
                    f"Include execute() method. Import from base_agent import BaseAgent.")
            result = await coder.execute({
                "name": f"Create {name} agent",
                "data": {"action": "generate", "spec": spec, "language": "python",
                         "filename": f"{name}_agent.py"}
            })

            # Try to load the new agent
            code = result.get("code", "")
            if code and len(code) > 50:
                from pathlib import Path
                agent_file = Path("workspace") / f"{name}_agent.py"
                agent_file.write_text(code)
                logger.info(f"Auto-created agent file: {agent_file}")

                # Create a dynamic wrapper using planner as fallback
                # The generated file is saved for future improvement
                fallback = self.get_agent("planner")
                if fallback:
                    self.agents[name] = fallback
                    logger.info(f"Agent '{name}' mapped to planner (auto-created code saved)")
                return self.agents.get(name)
            else:
                logger.warning(f"Auto-creation returned empty code for '{name}'")
                return self.get_agent("planner")
        except Exception as e:
            logger.error(f"Auto-create agent failed: {e}")
            return self.get_agent("planner")

    # ── Helpers ───────────────────────────────────────────────────

    def _print_help(self):
        print("""
  \033[93mCommands / ਕਮਾਂਡਾਂ:\033[0m
    goal <text>      — Run a goal / ਟੀਚਾ ਚਲਾਓ
    status           — System status / ਸਥਿਤੀ
    agents           — List agents / ਏਜੰਟ ਵੇਖੋ
    graph            — Task graph summary / ਟਾਸਕ ਗ੍ਰਾਫ
    history          — Past task history / ਇਤਿਹਾਸ

  \033[96m🧠 Deep Reasoning / ਡੂੰਘੀ ਸੋਚ:\033[0m
    think <question> — Multi-candidate deep reasoning / ਡੂੰਘੀ ਸੋਚ
    optimize <file>  — Code optimization analysis / ਕੋਡ ਅਨੁਕੂਲ
    memory           — Memory system stats / ਯਾਦਦਾਸ਼ਤ
    llmstats         — LLM call statistics / LLM ਅੰਕੜੇ

  \033[96m🔬 Scientific Research / ਵਿਗਿਆਨਕ ਖੋਜ:\033[0m
    research <topic> — Full research pipeline / ਪੂਰੀ ਖੋਜ ਪਾਈਪਲਾਈਨ
    arxiv <query>    — Search arXiv papers / ਖੋਜ ਪੇਪਰ ਲੱਭੋ
    pubmed <query>   — Search PubMed / ਮੈਡੀਕਲ ਖੋਜ
    hypothesis <obs> — Generate hypotheses / ਪਰੀਕਲਪਨਾ ਬਣਾਓ

  \033[91m⚡ Self-Evolution / ਸਵੈ-ਵਿਕਾਸ:\033[0m
    godmode          — Full autonomous self-evolution / ਪੂਰਾ ਆਟੋਨੋਮਸ
    evolve           — Run 3 evolution cycles / 3 ਚੱਕਰ ਚਲਾਓ
    selftest         — Analyze & test yourself / ਆਪਣੇ ਆਪ ਨੂੰ ਟੈਸਟ ਕਰੋ
    selffix          — Find & fix bugs / ਕਮੀਆਂ ਆਪੇ ਠੀਕ ਕਰੋ

  \033[94mOther / ਹੋਰ:\033[0m
    internet         — Internet mode / ਇੰਟਰਨੈੱਟ ਮੋਡ
    voice            — Voice mode / ਅਵਾਜ਼ ਮੋਡ
    clear            — Clear screen / ਸਕ੍ਰੀਨ ਸਾਫ਼
    exit             — Quit / ਬੰਦ ਕਰੋ

  \033[90mਤੁਸੀਂ ਸਿੱਧਾ ਪੰਜਾਬੀ ਜਾਂ English ਵਿੱਚ ਕੋਈ ਵੀ ਗੱਲ ਟਾਈਪ ਕਰ ਸਕਦੇ ਹੋ!\033[0m
""")

    def _print_status(self):
        s = self.task_graph.summary()
        print(f"\n  Goal:   {self.state.get('current_goal', 'none')}")
        print(f"  Tasks:  {s}")
        print(f"  Status: {self.state.get('status', '?')}")
        # v2 subsystems
        print(f"\n  \033[96m── Smart Infrastructure ──\033[0m")
        print(f"  Workers:   {self.lifecycle.summary()}")
        print(f"  Failures:  {self.failure_tracker.summary()}")
        print(f"  Recovery:  {self.recovery.stats()}")
        print(f"  Packets:   {self.packet_store.summary()}")
        print(f"  Policies:  {len(self.policy.rules)} active rules")
        print()

    def _print_agents(self):
        print("\n  🤖 Agents / ਏਜੰਟ:")
        for name in self.agents:
            ws = self.lifecycle.get_state(name)
            status = ws.status.name if ws else "?"
            print(f"     • {name:16} [{status}]")
        print()

    def _print_history(self):
        """Show recent task execution history."""
        try:
            from experience_log import ExperienceLog
            log = ExperienceLog()
            recent = log.recent(10)
            stats = log.stats()
            if not recent:
                print("\n  ਕੋਈ ਇਤਿਹਾਸ ਨਹੀਂ / No history yet.\n")
                return
            print(f"\n  \033[93m📊 Task History (ਟਾਸਕ ਇਤਿਹਾਸ)\033[0m")
            print(f"  Total: {stats['total']} | ✅ Success: {stats['success']} | ❌ Failed: {stats['failed']} | Rate: {stats['rate']*100:.0f}%\n")
            for e in recent:
                icon = "✅" if e.get("success") else "❌"
                print(f"    {icon} [{e.get('agent','?'):12}] {e.get('action','')[:50]}  ({e.get('timestamp','')[:16]})")
            print()
        except Exception as e:
            print(f"\n  Could not load history: {e}\n")

    async def shutdown(self):
        self.state.save()
        await self.event_bus.stop()
        self.scheduler.cancel_all()
        logger.info("GODMODE shutdown complete 👋")
