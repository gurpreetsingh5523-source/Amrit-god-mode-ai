#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║  🤖 agent_builder.py — Agent Creation & Orchestration       ║
║                                                              ║
║  System ਆਪ ਆਪਣੇ sub-agents ਬਣਾਉਂਦਾ ਹੈ                     ║
║  ਹਰ agent: specialized purpose + own memory + LLM           ║
║                                                              ║
║  Agent Types:                                                ║
║  • ResearchAgent — ਖੋਜ ਕਰਦਾ                                 ║
║  • CodeAgent — ਕੋਡ ਬਣਾਉਂਦਾ                                  ║
║  • CriticAgent — ਆਲੋਚਨਾ ਕਰਦਾ                               ║
║  • SynthesisAgent — ਵਿਚਾਰ ਮਿਲਾਉਂਦਾ                         ║
║  • CustomAgent — ਤੁਹਾਡੀ ਮਨਮਰਜ਼ੀ                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, field
from config import CFG
from llm_client import LLMClient


# ══════════════════════════════════════════════════════════════
# AGENT DATA STRUCTURE
# ══════════════════════════════════════════════════════════════

@dataclass
class AgentConfig:
    """Agent ਦੀ ਸੰਰਚਨਾ"""
    name: str
    role: str                        # ਕੀ ਕੰਮ ਕਰਦਾ ਹੈ
    personality: str                 # ਕਿਵੇਂ ਸੋਚਦਾ ਹੈ
    domain: str                      # "research"|"coding"|"critic"|"synthesis"|"custom"
    system_prompt: str               # LLM system prompt
    tools: List[str] = field(default_factory=list)  # ਕਿਹੜੇ tools ਵਰਤ ਸਕਦਾ ਹੈ
    max_turns: int = 5              # ਵੱਧ ਤੋਂ ਵੱਧ ਕਿੰਨੀ ਵਾਰ ਜਵਾਬ ਦੇਵੇ
    memory_limit: int = 20          # ਕਿੰਨੀਆਂ ਗੱਲਾਂ ਯਾਦ ਰੱਖੇ


@dataclass
class AgentMessage:
    """Agent ਦਾ ਸੁਨੇਹਾ"""
    agent_name: str
    role: str            # "user"|"assistant"|"system"
    content: str
    timestamp: str


@dataclass
class AgentResult:
    """ਏਜੰਟ ਦੀ task ਦਾ ਨਤੀਜਾ"""
    agent_name: str
    task: str
    output: str
    confidence: float
    turns_used: int
    success: bool
    metadata: Dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# BASE AGENT
# ══════════════════════════════════════════════════════════════

class BaseAgent:
    """ਹਰ agent ਦਾ ਅਧਾਰ"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = LLMClient(system_prompt=config.system_prompt)
        self.memory: List[AgentMessage] = []
        self.task_count = 0
        self.success_count = 0

    def think(self, prompt: str) -> str:
        """Agent ਸੋਚਦਾ ਹੈ"""
        self.memory.append(AgentMessage(
            agent_name=self.config.name,
            role="user",
            content=prompt,
            timestamp=datetime.now().isoformat()
        ))

        # History ਨਾਲ LLM call
        response = self.llm.ask(prompt)

        self.memory.append(AgentMessage(
            agent_name=self.config.name,
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat()
        ))

        # Memory limit ਰੱਖੋ
        if len(self.memory) > self.config.memory_limit * 2:
            self.memory = self.memory[-self.config.memory_limit:]

        return response

    def execute(self, task: str) -> AgentResult:
        """Task ਚਲਾਓ — override ਕਰੋ"""
        response = self.think(task)
        self.task_count += 1
        self.success_count += 1

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=response,
            confidence=0.7,
            turns_used=1,
            success=True
        )

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.task_count, 1)


# ══════════════════════════════════════════════════════════════
# SPECIALIZED AGENTS
# ══════════════════════════════════════════════════════════════

class ResearchAgent(BaseAgent):
    """ਖੋਜ ਕਰਨ ਵਾਲਾ agent"""

    def __init__(self, name: str = "Khoj"):
        config = AgentConfig(
            name=name,
            role="Research specialist — finds and synthesizes information",
            personality="Curious, thorough, evidence-based",
            domain="research",
            system_prompt=
                "You are Khoj, a research specialist. "
                "Your job: find information, verify facts, synthesize knowledge. "
                "Always cite your reasoning. Be specific, not vague. "
                "If uncertain, say so clearly.",
            tools=["web_search", "memory_read", "ether_query"],
            max_turns=5
        )
        super().__init__(config)

    def execute(self, task: str) -> AgentResult:
        print(f"  🔭 {self.config.name} researching: {task[:50]}")

        # Multi-turn research
        turns = 0
        insights = []

        # Turn 1: Initial analysis
        analysis = self.think(f"Research task: {task}\nFirst, what do I know about this?")
        insights.append(analysis)
        turns += 1

        # Turn 2: Deep dive
        if turns < self.config.max_turns:
            deep = self.think(f"Now deeper: {task}\nWhat specific evidence or examples support this?")
            insights.append(deep)
            turns += 1

        # Turn 3: Synthesis
        if turns < self.config.max_turns:
            synthesis = self.think(
                f"Synthesize: Given what I found about '{task}', what is the most important insight?"
            )
            insights.append(synthesis)
            turns += 1

        final_output = "\n\n".join(insights)
        self.task_count += 1
        self.success_count += 1

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=final_output,
            confidence=0.75,
            turns_used=turns,
            success=True,
            metadata={"insights_count": len(insights)}
        )


class CodeAgent(BaseAgent):
    """ਕੋਡ ਬਣਾਉਣ ਵਾਲਾ agent"""

    def __init__(self, name: str = "Nirman"):
        config = AgentConfig(
            name=name,
            role="Code generation and optimization specialist",
            personality="Precise, efficient, test-driven",
            domain="coding",
            system_prompt=
                "You are Nirman, a code generation expert. "
                "Generate complete, working, well-documented Python code. "
                "Always include: docstrings, error handling, and example usage. "
                "Prefer simplicity over complexity. Test before claiming it works.",
            tools=["mutation_lab", "sandbox_exec"],
            max_turns=4
        )
        super().__init__(config)

    def execute(self, task: str) -> AgentResult:
        print(f"  🔥 {self.config.name} coding: {task[:50]}")

        # Turn 1: Plan
        plan = self.think(f"Code task: {task}\nPlan: What structure should this code have?")
        turns = 1

        # Turn 2: Generate
        code = self.think(
            f"Now write the complete Python code for: {task}\n"
            f"Plan: {plan[:200]}\n"
            f"Output ONLY the code."
        )
        turns += 1

        # Turn 3: Review
        if turns < self.config.max_turns:
            review = self.think(
                f"Review this code for bugs:\n{code[:500]}\n"
                f"List any issues and corrections."
            )
            turns += 1

        self.task_count += 1
        self.success_count += 1

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=code,
            confidence=0.8,
            turns_used=turns,
            success=True,
            metadata={"plan": plan[:200], "reviewed": True}
        )


class CriticAgent(BaseAgent):
    """ਆਲੋਚਨਾ ਕਰਨ ਵਾਲਾ agent — quality guardian"""

    def __init__(self, name: str = "Vivek"):
        config = AgentConfig(
            name=name,
            role="Critical analyst — finds flaws, improves quality",
            personality="Honest, precise, constructive — not harsh",
            domain="critic",
            system_prompt=
                "You are Vivek (discernment), a critical analyst. "
                "Your job: find problems, weaknesses, and gaps in ideas/code. "
                "Be honest but constructive. Suggest specific improvements. "
                "No vague criticism — be precise about what's wrong and why.",
            max_turns=3
        )
        super().__init__(config)

    def execute(self, task: str) -> AgentResult:
        print(f"  🔍 {self.config.name} reviewing: {task[:50]}")

        critique = self.think(
            f"Critically analyze:\n{task}\n\n"
            f"1. What are the 3 main weaknesses?\n"
            f"2. What's missing?\n"
            f"3. How to improve?"
        )

        self.task_count += 1
        self.success_count += 1

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=critique,
            confidence=0.85,
            turns_used=1,
            success=True
        )


class SynthesisAgent(BaseAgent):
    """ਵਿਚਾਰ ਮਿਲਾਉਣ ਵਾਲਾ agent"""

    def __init__(self, name: str = "Sangam"):
        config = AgentConfig(
            name=name,
            role="Synthesis specialist — combines multiple perspectives",
            personality="Creative, integrative, pattern-finding",
            domain="synthesis",
            system_prompt=
                "You are Sangam (confluence), a synthesis expert. "
                "Your job: combine multiple ideas/research into unified insights. "
                "Find unexpected connections. Create emergent understanding. "
                "Be specific about HOW ideas connect, not just THAT they do.",
            max_turns=3
        )
        super().__init__(config)

    def synthesize(self, items: List[str]) -> AgentResult:
        """ਕਈ ਵਿਚਾਰਾਂ ਨੂੰ ਮਿਲਾਓ"""
        combined = "\n".join([f"Item {i+1}: {item[:200]}" for i, item in enumerate(items)])
        task = f"Synthesize these {len(items)} items into unified insight"

        output = self.think(
            f"{combined}\n\n"
            f"Find the unified insight that connects all of these. "
            f"What emerges that wasn't in any single item?"
        )

        self.task_count += 1
        self.success_count += 1

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=output,
            confidence=0.75,
            turns_used=1,
            success=True
        )

    def execute(self, task: str) -> AgentResult:
        return super().execute(task)


# ══════════════════════════════════════════════════════════════
# AGENT BUILDER — ਨਵੇਂ agents ਬਣਾਓ
# ══════════════════════════════════════════════════════════════

class AgentBuilder:
    """
    ਕੋਈ ਵੀ ਨਵਾਂ agent LLM ਤੋਂ design ਕਰੋ।
    System ਆਪ ਆਪਣੇ specialist agents ਬਣਾਉਂਦਾ ਹੈ।
    """

    def __init__(self):
        self.db = CFG.memory_dir / "agents.db"
        self.llm = LLMClient(system_prompt=
            "You are an agent designer. Create optimal AI agent configurations. "
            "Be specific about roles, personalities, and system prompts.")
        self.agents: Dict[str, BaseAgent] = {}
        self._init_db()
        self._load_built_in_agents()
        print(f"🤖 AgentBuilder — {len(self.agents)} agents ready")

    def _init_db(self):
        with sqlite3.connect(self.db) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_registry (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                role TEXT,
                domain TEXT,
                system_prompt TEXT,
                tools TEXT DEFAULT '[]',
                created TEXT,
                task_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS agent_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                task TEXT,
                output TEXT,
                success INTEGER,
                turns_used INTEGER,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS multi_agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT,
                agents_used TEXT,
                final_output TEXT,
                timestamp TEXT
            );
            """)

    def _load_built_in_agents(self):
        """Built-in agents load ਕਰੋ"""
        self.agents["Khoj"]   = ResearchAgent("Khoj")
        self.agents["Nirman"] = CodeAgent("Nirman")
        self.agents["Vivek"]  = CriticAgent("Vivek")
        self.agents["Sangam"] = SynthesisAgent("Sangam")

        # ── DualBrainEngine v3 ਲਈ ਨਵੇਂ specialist agents ──
        # ਇਹ BaseAgent ਹਨ (single-turn) — execute(prompt).output ਵਾਪਸ ਕਰਦੇ ਹਨ।
        self.agents["Planner"] = BaseAgent(AgentConfig(
            name="Planner",
            role="Generates step-by-step technical blueprints before code generation",
            personality="Analytical, structured, preemptive",
            domain="coding",
            system_prompt=(
                "You are Planner. Break a programming request into clear logic "
                "steps BEFORE any code is written. Respond ONLY with valid JSON "
                '(no markdown): {"entry_point": "main_function_name", '
                '"steps": ["step 1", "step 2"], "constraints": ["constraint 1"]}'),
            max_turns=2,
        ))

        self.agents["Verifier"] = BaseAgent(AgentConfig(
            name="Verifier",
            role="Formal verification and property-based correctness checking",
            personality="Rigorous, skeptical, precise",
            domain="critic",
            system_prompt=(
                "You are Verifier. Report ONLY real, code-grounded issues "
                "(at most 3, or none). Never invent problems. If the code is "
                "correct, report zero issues. Respond ONLY with valid JSON "
                '(no markdown): {"no_issues": true/false, "confidence": 0.0-1.0, '
                '"issues": [{"location": "symbol", "reason": "...", "fix": "..."}]}'),
            max_turns=2,
        ))

        self.agents["TestWriter"] = BaseAgent(AgentConfig(
            name="TestWriter",
            role="Writes hidden unit tests and property-based tests from a spec",
            personality="Adversarial, thorough, edge-case-seeking",
            domain="critic",
            system_prompt=(
                "You are TestWriter. Given a task spec and an entry-point "
                "function name, write Python assert-based hidden tests and "
                "property tests. NEVER write the implementation itself. "
                "Cover normal cases, edge cases, and invalid input. Respond ONLY "
                'with valid JSON (no markdown): {"hidden": ["assert ..."], '
                '"property": ["for _i in range(...):\\n    assert ..."]}'),
            max_turns=2,
        ))

    # ─────────────────────────────────────────────
    # CREATE CUSTOM AGENT
    # ─────────────────────────────────────────────

    def create_agent(self, name: str, purpose: str,
                     domain: str = "custom") -> BaseAgent:
        """
        ਕਿਸੇ ਵੀ purpose ਲਈ ਨਵਾਂ agent LLM ਤੋਂ design ਕਰੋ
        """
        print(f"\n🤖 Creating agent: {name} — {purpose[:50]}")

        # LLM ਤੋਂ agent design ਲਵੋ
        design_prompt = f"""Design an AI agent with:
Name: {name}
Purpose: {purpose}
Domain: {domain}

Generate in this format:
ROLE: [one sentence role]
PERSONALITY: [3 adjectives]
SYSTEM_PROMPT: [2-3 sentence system prompt]
TOOLS: [comma-separated tool names from: web_search, code_gen, memory_read, file_write, math_compute]"""

        design = self.llm.ask(design_prompt)

        # Parse design
        role = ""
        personality = ""
        system_prompt = f"You are {name}. {purpose}"
        tools = []

        for line in design.split('\n'):
            if line.startswith("ROLE:"):
                role = line[5:].strip()
            elif line.startswith("PERSONALITY:"):
                personality = line[12:].strip()
            elif line.startswith("SYSTEM_PROMPT:"):
                system_prompt = line[14:].strip()
            elif line.startswith("TOOLS:"):
                tools = [t.strip() for t in line[6:].split(',')]

        config = AgentConfig(
            name=name,
            role=role or purpose,
            personality=personality or "focused, capable",
            domain=domain,
            system_prompt=system_prompt,
            tools=tools,
            max_turns=5
        )

        agent = BaseAgent(config)
        self.agents[name] = agent

        # DB ਵਿੱਚ save
        agent_id = hashlib.md5(name.encode()).hexdigest()[:8]
        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT OR REPLACE INTO agent_registry
                (id, name, role, domain, system_prompt, tools, created)
                VALUES (?,?,?,?,?,?,?)
            """, (agent_id, name, role, domain, system_prompt,
                  json.dumps(tools), datetime.now().isoformat()))

        print(f"  ✅ Agent '{name}' created!")
        print(f"  Role: {role[:60]}")
        return agent

    # ─────────────────────────────────────────────
    # RUN SINGLE AGENT
    # ─────────────────────────────────────────────

    def run(self, agent_name: str, task: str) -> AgentResult:
        """ਇੱਕ agent ਚਲਾਓ"""
        if agent_name not in self.agents:
            return AgentResult(
                agent_name=agent_name,
                task=task,
                output=f"Agent '{agent_name}' not found",
                confidence=0.0,
                turns_used=0,
                success=False
            )

        agent = self.agents[agent_name]
        result = agent.execute(task)

        # Log
        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO agent_results
                (agent_name, task, output, success, turns_used, timestamp)
                VALUES (?,?,?,?,?,?)
            """, (agent_name, task[:200], result.output[:500],
                  1 if result.success else 0, result.turns_used,
                  datetime.now().isoformat()))
            c.execute("""
                UPDATE agent_registry SET
                    task_count = task_count + 1,
                    success_count = success_count + ?
                WHERE name = ?
            """, (1 if result.success else 0, agent_name))

        return result

    # ─────────────────────────────────────────────
    # MULTI-AGENT PIPELINE
    # ─────────────────────────────────────────────

    def run_pipeline(self, task: str,
                     pipeline: List[str] = None) -> Dict:
        """
        ਕਈ agents ਨੂੰ ਕ੍ਰਮਵਾਰ ਚਲਾਓ।
        ਹਰ agent ਪਿਛਲੇ ਦਾ output ਵਰਤਦਾ ਹੈ।

        Default pipeline: Research → Code → Critique → Synthesis
        """
        if pipeline is None:
            pipeline = ["Khoj", "Nirman", "Vivek", "Sangam"]

        print(f"\n🔄 MULTI-AGENT PIPELINE: {' → '.join(pipeline)}")
        print(f"   Task: {task[:60]}")
        print("─"*60)

        results = {}
        current_context = task

        for agent_name in pipeline:
            if agent_name not in self.agents:
                print(f"  ⚠️  Agent '{agent_name}' not found — skipping")
                continue

            print(f"\n▶ {agent_name}")

            # SynthesisAgent ਲਈ ਸਾਰੇ previous results ਦਿਓ
            if agent_name == "Sangam" and len(results) > 1:
                items = [r.output for r in results.values()]
                agent = self.agents["Sangam"]
                result = agent.synthesize(items)
            else:
                enhanced_task = (
                    f"Original task: {task}\n\n"
                    f"Context from previous agent:\n{current_context[:400]}"
                    if results else task
                )
                result = self.run(agent_name, enhanced_task)

            results[agent_name] = result
            current_context = result.output
            print(f"  ✅ {result.turns_used} turns, confidence: {result.confidence:.2f}")

        # Final synthesis
        final = current_context

        # Log
        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO multi_agent_runs
                (task, agents_used, final_output, timestamp)
                VALUES (?,?,?,?)
            """, (task[:200], json.dumps(pipeline),
                  final[:500], datetime.now().isoformat()))

        print("\n" + "─"*60)
        print("✨ PIPELINE COMPLETE")
        return {
            "task": task,
            "pipeline": pipeline,
            "results": {k: {"output": v.output[:300], "confidence": v.confidence}
                        for k, v in results.items()},
            "final_output": final
        }

    # ─────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────

    def list_agents(self) -> List[Dict]:
        """ਸਾਰੇ agents ਦੀ ਸੂਚੀ"""
        agents_info = []
        for name, agent in self.agents.items():
            agents_info.append({
                "name": name,
                "role": agent.config.role[:60],
                "domain": agent.config.domain,
                "tasks": agent.task_count,
                "success_rate": f"{agent.success_rate*100:.0f}%"
            })
        return agents_info

    def print_status(self):
        print("\n🤖 AGENT REGISTRY")
        print("─"*60)
        for a in self.list_agents():
            print(f"  [{a['domain']:12}] {a['name']:12} — {a['role'][:40]}")
            print(f"                   Tasks: {a['tasks']} | "
                  f"Success: {a['success_rate']}")


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    builder = AgentBuilder()

    # Built-in agents ਦੇਖੋ
    builder.print_status()

    # Custom agent ਬਣਾਓ
    punjabi_agent = builder.create_agent(
        "Boli",
        "Punjabi language specialist — translates, explains, and writes in Punjabi",
        domain="language"
    )

    # Single agent run
    print("\n─"*60)
    result = builder.run("Khoj", "What is quantum consciousness?")
    print(f"\nResult preview: {result.output[:200]}...")

    # Multi-agent pipeline
    print("\n" + "─"*60)
    pipeline_result = builder.run_pipeline(
        "Research and implement a simple web scraper in Python",
        pipeline=["Khoj", "Nirman", "Vivek"]
    )

    print("\n✨ Final output preview:")
    print(pipeline_result["final_output"][:300])
