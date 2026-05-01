<div align="center">

# ☬ AMRIT GODMODE v3.0

### ਆਟੋਨੋਮਸ AI ਪਲੇਟਫਾਰਮ — Self-Evolving, Self-Fixing, Self-Learning

**97 Python modules · 13,500+ lines · 23 tests passing · Punjabi NLP**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-23%2F23%20passing-brightgreen.svg)]()
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20Local-orange.svg)](https://ollama.com)

</div>

---

## What is AMRIT GODMODE?

AMRIT GODMODE is an **autonomous AI agent platform** that can:

- **Write, test, and fix its own code** — the self-evolution engine scans all 97 modules, finds weaknesses, generates improvements, tests them, and applies only if tests pass
- **Research the internet** — searches arXiv for latest papers and feeds findings into code improvements
- **Talk and listen** — voice control via Whisper STT + TTS
- **See and understand** — vision mode with image/video analysis
- **Learn from mistakes** — LearningLayer tracks what worked and what didn't
- **Run fully autonomously** — godmode monitors, self-upgrades, and self-heals

Built for **Apple Silicon** (M1/M2/M3/M4/M5) with Metal GPU acceleration.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    main.py (Entry)                   │
├─────────────────────────────────────────────────────┤
│              orchestrator.py (Brain)                 │
│         Coordinates 14 specialized agents            │
├──────────┬──────────┬───────────┬───────────────────┤
│  Planner │  Coder   │  Research │  Vision/Voice     │
│  Agent   │  Agent   │  Agent    │  Agents           │
├──────────┴──────────┴───────────┴───────────────────┤
│               llm_router.py (LLM Hub)                │
│   Ollama (7B) ──→ AirLLM (32B) ──→ Cloud APIs       │
├─────────────────────────────────────────────────────┤
│            self_evolution.py (Self-Upgrade)           │
│   Analyze → Test → Fix → Refactor → Learn → Train   │
├─────────────────────────────────────────────────────┤
│  Memory Stack: Context │ Vector │ Episodic │ Semantic│
├─────────────────────────────────────────────────────┤
│  Security: Sandbox │ Ethical Guard │ Code Safety     │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Ollama** installed ([ollama.com](https://ollama.com)) with at least one model:
  ```bash
  ollama pull gemma3:4b           # Fast 4B model (recommended to start)
  ollama pull mistral:7b-instruct-q4_K_M  # General purpose
  ```

### Installation

```bash
# Clone the repo
git clone https://github.com/gurpreetsingh5523-source/Amrit-god-mode-ai.git
cd Amrit-god-mode-ai

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
# Interactive chat mode (default)
python main.py

# Give it a goal
python main.py --goal "Build a web scraper for news headlines"

# Full autonomous mode (self-monitors + self-upgrades)
python main.py --mode godmode

# Self-fix mode (scans all code, fixes issues, runs tests)
python main.py --mode selffix

# Self-evolution (multi-cycle improvement)
python main.py --mode evolve

# Deep research on any topic
python main.py --mode research --goal "quantum computing applications in 2026"

# Voice control
python main.py --mode voice

# Vision mode
python main.py --mode vision
```

---

## Modes

| Mode | Command | What it does |
|------|---------|-------------|
| **Interactive** | `python main.py` | Chat-based control, ask anything |
| **Autonomous** | `python main.py --goal "..."` | Goal-driven execution with task decomposition |
| **Godmode** | `python main.py --mode godmode` | Fully autonomous — monitors, self-upgrades, self-heals |
| **Selffix** | `python main.py --mode selffix` | Scans all 97 modules, fixes bugs, runs tests |
| **Evolve** | `python main.py --mode evolve` | Multi-cycle self-evolution (analyze→test→fix→refactor→learn) |
| **Research** | `python main.py --mode research --goal "..."` | Deep internet/arXiv research |
| **Voice** | `python main.py --mode voice` | Voice-controlled via Whisper + TTS |
| **Vision** | `python main.py --mode vision` | Image/video analysis |
| **Internet** | `python main.py --mode internet` | Web browsing and information extraction |

---

## Modules Overview

### Core (Brain)
| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Central brain — coordinates all agents |
| `event_bus.py` | Pub/sub event system between modules |
| `task_graph.py` | DAG-based task execution with dependencies |
| `workflow_engine.py` | YAML workflow definitions |
| `state_manager.py` | Global state persistence |

### Agents (14 Specialized)
| Agent | Purpose |
|-------|---------|
| `planner_agent.py` | Breaks goals into executable task plans |
| `coder_agent.py` | Writes, reviews, and improves code |
| `debugger_agent.py` | Finds and fixes bugs |
| `tester_agent.py` | Generates and runs tests |
| `research_agent.py` | Deep research with internet access |
| `internet_agent.py` | Web search (DuckDuckGo, arXiv, PubMed) |
| `vision_agent.py` | Image understanding and analysis |
| `voice_agent.py` | Voice interaction (STT + TTS) |
| `memory_agent.py` | Manages all memory types |
| `monitor_agent.py` | System health monitoring |
| `upgrade_agent.py` | Self-upgrade capabilities |
| `dataset_agent.py` | Dataset creation and management |
| `tool_agent.py` | Dynamic tool use |
| `telegram_agent.py` | Telegram bot interface |

### LLM Infrastructure
| Module | Purpose |
|--------|---------|
| `llm_router.py` | Smart routing across models (8 categories) |
| `model_selector.py` | Picks best model for each task |
| `local_llm.py` | Ollama integration |
| `cloud_llm.py` | OpenAI/Anthropic/Groq/Gemini APIs |

### Self-Evolution
| Module | Purpose |
|--------|---------|
| `self_evolution.py` | 7-phase self-improvement engine |
| `self_learning_loop.py` | Learns from successes and failures |
| `learning_layer.py` | Observe → Reflect → Correct cycle |
| `self_upgrade.py` | Scans TODOs, generates upgrades |
| `auto_refactor.py` | Automated code refactoring |
| `skill_evolver.py` | Develops new capabilities |

### Memory Stack
| Module | Purpose |
|--------|---------|
| `context_buffer.py` | Short-term conversation context |
| `vector_store.py` | FAISS vector similarity search |
| `long_term_memory.py` | Persistent memory across sessions |
| `episodic_memory.py` | Records experiences and outcomes |
| `semantic_memory.py` | Knowledge graph storage |
| `planning_memory.py` | Remembers plans and strategies |
| `visual_memory.py` | Stores visual observations |
| `voice_memory.py` | Remembers voice interactions |

### Security
| Module | Purpose |
|--------|---------|
| `sandbox.py` | Isolated code execution |
| `ethical_guard.py` | Blocks harmful requests |
| `code_safety.py` | Detects hardcoded secrets, injection risks |
| `permission_manager.py` | RBAC access controls |

### Skills
| Module | Purpose |
|--------|---------|
| `file_ops.py` | File read/write/edit operations |
| `terminal_ops.py` | Shell command execution |
| `git_ops.py` | Git version control operations |
| `browser_ops.py` | Web browser automation (Playwright) |
| `web_scraper.py` | HTML/page scraping |
| `crawler.py` | Multi-page web crawling |
| `api_client.py` | REST API calls |
| `search_engine.py` | Web search aggregation |

---

## Self-Evolution Engine

The heart of AMRIT. When you run `--mode selffix` or `--mode evolve`, it does:

```
Phase 1: ANALYZE  → Scans all 97 modules, scores quality (0-1)
Phase 2: TEST     → Runs 23 unit tests, identifies failures
Phase 3: FIX      → Fixes import errors, syntax issues, test failures
Phase 4: REFACTOR → Improves weakest-scoring modules
Phase 5: OPTIMIZE → Performance improvements
Phase 6: LEARN    → Applies improvements, runs before/after tests
Phase 7: TRAIN    → Feeds learnings back into the model
```

### 7B → 32B Escalation

When the fast 7B model fails to generate good refactoring code:
1. **Attempt 1-2**: Uses Ollama 7B (fast, ~2s/response)

This works on 16GB RAM — AirLLM loads one layer at a time through Metal GPU.

### arXiv Research Pipeline

During self-evolution, the engine searches arXiv for latest papers on:
- Autonomous AI self-improvement
- Code generation techniques
- Self-healing systems

Paper summaries are injected into the LLM prompt so improvements are informed by latest research.

---

## Configuration

All settings in `config.yaml`:

```yaml
llm:
  model: "mistral:7b-instruct-q4_K_M"    # Default model
  reasoning_model: "gemma3:4b"            # For reasoning tasks
  coding_model: "gemma3:4b"               # For code generation
  fast_model: "gemma3:4b"                 # Quick responses
  openai_base_url: "http://127.0.0.1:11434/v1"  # Ollama endpoint
  request_timeout: 90                     # Seconds

autonomy:
  max_tokens: 400
  task_timeout: 90

memory:
  context_buffer_size: 40
  persist_path: "workspace/state.json"

security:
  sandbox_enabled: true
  ethical_guard: true
```

### Using Cloud LLMs (Optional)

Set API keys as environment variables:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export GEMINI_API_KEY="..."
```

---

## Running Tests

```bash
# Run all tests
python -m pytest test_godmode.py -v

# Expected: 23/23 passing
```

Tests cover: event_bus, sandbox, orchestrator, code_analysis, goal_parser, llm_router, learning_layer, code_safety, config_loader, context_buffer, internet_agent, logger, and more.

---

## Docker

```bash
docker build -t amrit-godmode .
docker run -it amrit-godmode
```

Note: For Ollama models, you'll need to either:
- Mount the Ollama socket: `-v /var/run/ollama:/var/run/ollama`
- Or set cloud LLM API keys via `-e GROQ_API_KEY=...`

---

## Telegram Bot

Control AMRIT via Telegram:

1. Create a bot with [@BotFather](https://t.me/BotFather)
2. Set the token: `export TELEGRAM_BOT_TOKEN="your-token"`
3. Run: `python telegram_agent.py`
4. Send: `/goal Build a CSV downloader` to your bot

---

## LoRA Training (Punjabi)

AMRIT includes a LoRA fine-tuning pipeline for Punjabi language:

```bash
python punjabi_trainer.py train

# Deploy to Ollama
python punjabi_trainer.py deploy
```

Training stats: 45K samples, validation loss 0.536 (65% reduction).

---

## Project Structure

```
Amrit-god-mode-ai/
├── main.py                 # Entry point
├── orchestrator.py         # Central brain
├── config.yaml             # Configuration
├── requirements.txt        # Dependencies
├── Dockerfile              # Docker support
│
├── llm_router.py           # Smart model routing
├── self_evolution.py        # Self-improvement engine
├── learning_layer.py        # Observe/reflect/correct
│
├── *_agent.py              # 14 specialized agents
├── *_memory.py             # 8 memory types
├── *_ops.py                # File/terminal/git/browser ops
│
├── test_godmode.py         # 23 unit tests
├── workspace/              # Runtime workspace
│   ├── evolution_log.json  # Self-evolution history
│   ├── experience.json     # Learning experiences
│   └── tools/              # Self-generated tools
│
└── .gitignore              # Excludes models/videos/venvs
```

---

## Hardware Requirements

| Setup | RAM | What works |
|-------|-----|-----------|
| **Minimum** | 8 GB | Cloud LLMs only (Groq/OpenAI) |
| **Recommended** | 16 GB | Ollama 7B + AirLLM 32B (layer-wise) |
| **Ideal** | 32+ GB | Multiple models simultaneously |

Best on **Apple Silicon** (M1-M5) with Metal GPU acceleration.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repo
2. Create a feature branch
3. Make changes and add tests
4. Run `python -m pytest test_godmode.py -v` (all 23 must pass)
5. Submit a pull request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**☬ ਵਾਹਿਗੁਰੂ ਜੀ ਕਾ ਖ਼ਾਲਸਾ ॥ ਵਾਹਿਗੁਰੂ ਜੀ ਕੀ ਫ਼ਤਹਿ ॥**

*Built with ❤️ and ਪੰਜਾਬੀ ਜਜ਼ਬਾਤ*

</div>

Files of interest
- `workspace/stock_analysis/fetch_price.py` — fallback script that writes `workspace/stock_analysis/price.txt` when invoked.
- `llm_router.py` — prompt trimming and automatic fallback logic lives here.
- `base_agent.py` — iterative summarization before LLM calls.

## ZIP Contents
- **ZIP 1** — Core + Agents + Planning + Models + Config
- **ZIP 2** — Memory + Skills + Security + Autonomy + Internet
- **ZIP 3** — Learning + Voice + Vision + Tests + Docker
