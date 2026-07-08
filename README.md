<div align="center">

# ☬ AMRIT GODMODE v3.1 ☬

### ਆਟੋਨੋਮਸ AI ਪਲੇਟਫਾਰਮ — Self-Evolving, Self-Fixing, Self-Learning
**Clean Architecture · 19 Specialized Agents · 121 Unit & Integration Tests Passing · Punjabi NLP**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-121%2F121%20passing-brightgreen.svg?style=for-the-badge&logo=pytest)](https://pytest.org)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20Local-orange.svg?style=for-the-badge&logo=ollama)](https://ollama.com)

</div>

---

## 🚀 Overview

**AMRIT GODMODE v3.1** is a state-of-the-art, fully autonomous AI agent platform designed to run locally with metal-accelerated performance on Apple Silicon. Following a major architectural modularization, the system features a robust **Dual-Brain Cognitive Loop**, a **7-Phase Self-Evolution Pipeline**, and a network of **19 specialized autonomous agents** communicating over a unified asynchronous event bus.

With **121/121 unit and integration tests passing**, AMRIT has a verified self-evolution feedback loop that lets it write, test, debug, and upgrade its own code safely within a secure runtime sandbox.

---

## 🧱 Architecture

```
                      ┌────────────────────────────────────────┐
                      │             main.py (Entry)            │
                      └───────────────────┬────────────────────┘
                                          │
                      ┌───────────────────▼────────────────────┐
                      │        core/orchestrator.py (Brain)    │
                      │      Coordinates 19 agents & events    │
                      └──────┬──────────────────────────┬──────┘
                             │                          │
           ┌─────────────────▼─────────┐      ┌─────────▼─────────────────┐
           │        core/event_bus.py  │      │      core/task_graph.py   │
           │  Asynchronous Event Hub   │      │   DAG Dependency Resolver │
           └───────────────────────────┘      └───────────────────────────┘
                             │                          │
  ┌──────────────────────────┼──────────────────────────┼──────────────────────────┐
  │                          │                          │                          │
┌─▼─────────────┐          ┌─▼─────────────┐          ┌─▼─────────────┐          ┌─▼─────────────┐
│ agents/       │          │ memory/       │          │ learning/     │          │ failure/      │
│ 19 Agents     │          │ Context, FAISS│          │ Self-Evolution│          │ Error DNA &   │
│ (Planner,     │          │ Episodic,     │          │ Crystallizer, │          │ Recovery      │
│ Coder, Tester)│          │ Semantic      │          │ Mutation Lab  │          │ Recipes       │
└───────────────┘          └───────────────┘          └───────────────┘          └───────────────┘
```

---

## 🛠️ Folder Structure

The project directory is structured cleanly into functional modular layers:

*   [**`core/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/core) — The orchestration engine: [Orchestrator](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/core/orchestrator.py), [EventBus](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/core/event_bus.py), [TaskGraph](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/core/task_graph.py), and [AutonomyLoop](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/core/autonomy_loop.py).
*   [**`agents/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/agents) — 19 specialized worker agents including the [CoderAgent](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/agents/coder_agent.py), [PlannerAgent](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/agents/planner_agent.py), and [TesterAgent](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/agents/tester_agent.py).
*   [**`memory/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/memory) — Hybrid multi-layer memory storage: [ContextBuffer](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/memory/context_buffer.py), [VectorStore](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/memory/vector_store.py), [EpisodicMemory](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/memory/episodic_memory.py), and [SemanticMemory](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/memory/semantic_memory.py).
*   [**`learning/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/learning) — The cognitive self-improvement pipeline: [SelfEvolution](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/learning/self_evolution.py), [LearningLayer](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/learning/learning_layer.py), [SkillCrystallizer](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/learning/skill_crystallizer.py), and [MutationLab](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/learning/mutation_lab.py).
*   [**`failure/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/failure) — Diagnostics and healing layers: [ErrorAnalyzer](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/failure/error_analyzer.py) and [RecoveryRecipes](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/failure/recovery_recipes.py).
*   [**`os_ops/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/os_ops) — OS-level tool bindings: [TerminalOps](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/os_ops/terminal_ops.py), [FileOps](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/os_ops/file_ops.py), [GitOps](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/os_ops/git_ops.py), and [BrowserOps](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/os_ops/browser_ops.py).
*   [**`punjabi/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/punjabi) — Local Gurmukhi NLP: [PunjabiTrainer](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/punjabi/punjabi_trainer.py) and [NaamFilter](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/punjabi/naam_filter.py) ethical guard.
*   [**`voice/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/voice) — Audio processing pipeline: Whisper STT, TTS, and cached playback.
*   [**`dashboard/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/dashboard) — Local telemetry dashboard and MCP (Model Context Protocol) API.
*   [**`tests/`**](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/tests) — Clean, comprehensive test suite backed by a global [conftest.py](file:///Users/gurpreetdhillon/Amrit-god-mode-ai/tests/conftest.py).

---

## ⚡ Quick Start

### Prerequisites

1.  **Python 3.12+**
2.  **Ollama** installed ([ollama.com](https://ollama.com)) with your models running locally:
    ```bash
    ollama pull gemma3:4b
    ollama pull mistral:7b-instruct-q4_K_M
    ```

### Installation

```bash
# Clone the repository
git clone https://github.com/gurpreetsingh5523-source/Amrit-god-mode-ai.git
cd Amrit-god-mode-ai

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Execution Modes

AMRIT can be launched in several specialized operating modes:

```bash
# 1. Interactive Chat Mode (Default)
python main.py

# 2. Autonomous Goal Mode (Resolves, codes, and verifies automatically!)
python main.py --goal "Create a text file in the workspace directory named success.txt containing 'Done'"

# 3. Godmode (Monitors, self-upgrades, and self-heals in the background)
python main.py --mode godmode

# 4. Selffix Mode (Scans modules, locates import/syntax issues, runs tests and self-repairs)
python main.py --mode selffix

# 5. Evolve Mode (Executes a multi-cycle self-evolution training loop)
python main.py --mode evolve

# 6. Deep Research Mode (Aggregates information from DuckDuckGo, arXiv, and PubMed)
python main.py --mode research --goal "quantum computing applications in 2026"

# 7. Swarm Mode (Launches a cooperative multi-agent swarm to achieve a complex goal)
python main.py --mode swarm --goal "Build a REST API for managing tasks"
```

---

## 🤖 Network of 19 Specialized Agents

AMRIT orchestrates 19 specialized agents, each dynamically mapped to specific task signatures:

| Agent | Module | Core Functionality |
| :--- | :--- | :--- |
| **Planner** | `planner_agent.py` | Decomposes high-level natural language goals into topological DAG task graphs. |
| **Coder** | `coder_agent.py` | Writes, reviews, and refactors clean python code based on spec and syntax checks. |
| **Debugger** | `debugger_agent.py` | Analyzes execution stacks, tracks logs, and generates code patch fixes. |
| **Tester** | `tester_agent.py` | Auto-generates pytest scripts and validates running logic locally. |
| **Tool** | `tool_agent.py` | Manages file operations, executes shell commands, and automates browser flows. |
| **Upgrade** | `upgrade_agent.py` | Modifies, patches, and safely applies code upgrades to active engine modules. |
| **Monitor** | `monitor_agent.py` | Tracks system health, memory consumption, and checks agent liveness. |
| **Internet** | `internet_agent.py` | Performs web lookups, fetches papers from arXiv, and scrapes API docs. |
| **Voice** | `voice_agent.py` | Whisper-based speech-to-text and natural voice output generation. |
| **Vision** | `vision_agent.py` | Image description, object detection, and visual system checks. |
| **Dataset** | `dataset_agent.py` | Builds, formats, and manages fine-tuning data pipelines for self-learning. |
| **Simulation** | `simulation_agent.py` | Evaluates hypothetical scenarios and tests model variance prior to execution. |
| **Fullstack** | `fullstack_agent.py` | Creates web layouts, configures databases, and wires up API endpoints. |
| **UI Design** | `ui_design_agent.py` | Designs visual interfaces, layouts, and reviews user interface components. |
| **Swift** | `swift_agent.py` | Generates native swift, Xcode assets, and compiles macOS/iOS system scripts. |
| **DB** | `db_agent.py` | Manages database schemas, executes SQL queries, and optimizes SQLite connections. |
| **Translator** | `example_translator.py` | Translates documents and inputs across languages using local context. |
| **Memory** | `memory_agent.py` | Manages read/write pipelines across the hybrid memory stack. |

---

## 🧬 Self-Evolution Cycle

The core capability of AMRIT is its **7-Phase Self-Evolution Pipeline**. Running `--mode evolve` triggers a full cognitive improvement loop:

```
[Phase 1] ANALYZE  ──→ Scans all python files, scoring code quality metrics.
[Phase 2] TEST     ──→ Runs all 121 unit & integration tests to gather metrics.
[Phase 3] FIX      ──→ Detects syntax/import errors and resolves them immediately.
[Phase 4] REFACTOR ──→ Regenerates weak modules to improve structural scoring.
[Phase 5] OPTIMIZE ──→ Speeds up slow-running operations.
[Phase 6] LEARN    ──→ Evaluates the differences and commits successful runs.
[Phase 7] TRAIN    ──→ Pipelines training metrics to prep local weights fine-tuning.
```

> [!TIP]
> **Autonomy Loop Stability**: AMRIT automatically tracks task execution indices and resolves depends_on mapping dynamically, ensuring that multi-step plans execute sequentially without locking up.

---

## 🔒 Security & Guardrails

AMRIT takes local execution security seriously with three layers of safety enforcement:
1.  **Ethical Guardrail (`ethical_guard.py`)** — Inspects inputs and code blocks to filter out dangerous requests.
2.  **Sandbox Execution (`sandbox.py`)** — Python scripts and test codes are run in an isolated subprocess sandbox.
3.  **Naam Filter Gurmukhi Guard (`naam_filter.py`)** — Implements core ethical constraints derived from Gurmukhi principles (*Dharam, Sach, Daya*) to reject destructive commands in both English and Punjabi.

---

## 🧪 Testing

The entire codebase is verified by 121 unit and integration tests. Run tests locally using:

```bash
# Execute pytest across the suite
python -m pytest -v
```

---

<div align="center">

**☬ ਵਾਹਿਗੁਰੂ ਜੀ ਕਾ ਖ਼ਾਲਸਾ ॥ ਵਾਹਿਗੁਰੂ ਜੀ ਕੀ ਫ਼ਤਹਿ ॥**  
*Built with ❤️, Local LLM orchestration, and Punjabi Spirit*

</div>
