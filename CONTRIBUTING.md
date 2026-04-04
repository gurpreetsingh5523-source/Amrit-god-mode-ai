# Contributing to AMRIT GODMODE

☬ ਵਾਹਿਗੁਰੂ ਜੀ ਕਾ ਖ਼ਾਲਸਾ ॥ Thank you for contributing!

## Development Setup

```bash
# Clone
git clone https://github.com/gurpreetsingh5523-source/Amrit-god-mode-ai.git
cd Amrit-god-mode-ai

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Ollama + model
# https://ollama.com
ollama pull gemma3:4b
```

## Running

```bash
python main.py                          # Interactive mode
python main.py --mode selffix           # Self-fix mode
python main.py --mode evolve            # Self-evolution
python main.py --goal "your task"       # Goal execution
```

## Code Style
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Keep modules under 200 lines when possible
- All modules are flat (no package subdirectories) — import directly: `from event_bus import EventBus`
- Use async/await for agent methods

## Testing

```bash
# Run all tests (must be 23/23 passing)
python -m pytest test_godmode.py -v

# Run selffix (automated test + fix cycle)
python main.py --mode selffix
```

Before submitting a PR:
1. All 23 tests must pass
2. `python main.py --mode selffix` must complete without errors
3. No hardcoded API keys or personal paths

## Pull Request Process

1. Fork the repo and branch from `main`
2. Make changes — keep them focused and minimal
3. Add tests for new features in `test_godmode.py`
4. Run `python -m pytest test_godmode.py -v` — all must pass
5. Submit PR with clear description

## What to Contribute

- **New agents** — Add specialized agents (e.g., database agent, API testing agent)
- **Memory improvements** — Better vector search, smarter context management
- **Model support** — Add new LLM providers to `llm_router.py`
- **Security** — Improve sandboxing, add more safety checks
- **Tests** — More test coverage is always welcome
- **Punjabi NLP** — Improve Punjabi language support

## Architecture Notes

- `orchestrator.py` is the central brain — all agents register here
- `llm_router.py` handles model selection (8 categories: coding, reasoning, deep, etc.)
- `self_evolution.py` has 7 phases — be careful modifying the phase pipeline
- `config.yaml` controls all settings — don't hardcode values in Python files