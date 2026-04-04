# ⚡ AMRIT GODMODE v2.0
### Autonomous AI Platform — 93 Files | Production Ready

## Modules
- **core/** — Orchestrator, TaskGraph (DAG), EventBus, WorkflowEngine
- **agents/** — 14 specialized agents (Planner, Coder, Voice, Vision, Internet...)
- **planning/** — Goal parser, Dependency resolver, Priority engine
- **models/** — LLM Router (5 providers: OpenAI/Anthropic/Groq/Gemini/Ollama)
- **memory/** — Context, Vector, Long-term, Episodic, Semantic memory
- **skills/** — File, Terminal, Git, Browser, Web scraper, API client
- **security/** — Ethical guard, RBAC, Sandbox, Code safety
- **autonomy/** — Self-upgrade, Module installer, Auto-refactor
- **internet/** — Search engine, Crawler, Information extractor
- **learning/** — Self-learning, Error analyzer, Reward engine, Trainer
- **voice/** — STT (Whisper), TTS (pyttsx3/ElevenLabs), Emotion voice
- **vision/** — Image reader, Video reader, Object detector

## Quick Start
```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...      # Free + fast!
python main.py                   # Interactive mode
python main.py --goal "Build a web scraper"
python main.py --mode godmode    # Full autonomous mode
python main.py --mode voice      # Voice control
```

## Modes
- `interactive` — Chat-based control
- `autonomous`  — Goal-driven execution
- `godmode`     — Fully autonomous, monitors + self-upgrades
- `voice`       — Voice-controlled
- `vision`      — Image/video analysis mode
- `internet`    — Deep web research mode

# ⚡ AMRIT GODMODE v2.0
### Autonomous AI Platform — 93 Files | Production Ready

## Modules
- **core/** — Orchestrator, TaskGraph (DAG), EventBus, WorkflowEngine
- **agents/** — 14 specialized agents (Planner, Coder, Voice, Vision, Internet...)
- **planning/** — Goal parser, Dependency resolver, Priority engine
- **models/** — LLM Router (5 providers: OpenAI/Anthropic/Groq/Gemini/Ollama)
- **memory/** — Context, Vector, Long-term, Episodic, Semantic memory
- **skills/** — File, Terminal, Git, Browser, Web scraper, API client
- **security/** — Ethical guard, RBAC, Sandbox, Code safety
- **autonomy/** — Self-upgrade, Module installer, Auto-refactor
- **internet/** — Search engine, Crawler, Information extractor
- **learning/** — Self-learning, Error analyzer, Reward engine, Trainer
- **voice/** — STT (Whisper), TTS (pyttsx3/ElevenLabs), Emotion voice
- **vision/** — Image reader, Video reader, Object detector

## Quick Start
```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...      # Free + fast!
python main.py                   # Interactive mode
python main.py --goal "Build a web scraper"
python main.py --mode godmode    # Full autonomous mode
python main.py --mode voice      # Voice control
```

## Modes
- `interactive` — Chat-based control
- `autonomous`  — Goal-driven execution
- `godmode`     — Fully autonomous, monitors + self-upgrades
- `voice`       — Voice-controlled
- `vision`      — Image/video analysis mode
- `internet`    — Deep web research mode

## Prompt summarization & automatic fallbacks
To keep prompts within the context limits of local/remote LLMs we implement automatic prompt trimming and iterative summarization prior to sending very large prompts. This helps avoid "context size exceeded" errors and keeps downstream Planner/Coder agents responsive.

Key configuration options (in `config.yaml`):
- `llm.max_context_chars` — If a prompt exceeds this many characters, it will be chunked and summarized before being sent to the model.
- `llm.summary_target_chars` — The summarizer will compress combined chunk summaries to approximately this size.
- `llm.request_timeout` — HTTP/LLM request timeout (seconds).
- `autonomy.task_timeout` — Default task timeout (seconds) — increased to 300s for longer-running tasks.

Automatic fallback for stock/price prompts:
- The router will attempt to get a price from the configured LLM. If the response is empty or unusable and the prompt appears to be a stock/price request, the router will automatically run the fallback script located at `workspace/stock_analysis/fetch_price.py` using the same Python interpreter. If that script writes `workspace/stock_analysis/price.txt`, the router will return its contents as the LLM result, preserving autonomy without manual intervention.

Notes:
- The summarization is lightweight and LLM-driven: the system chunks long prompts, asks the LLM to summarize each chunk, then compresses the summaries to the target size before the main call. You can improve summary quality later by wiring a dedicated summarizer or semantic memory module.

## Telegram integration (scaffold)
This repository now includes a minimal Telegram agent scaffold `telegram_agent.py` that can poll a bot token for messages and forward user messages starting with `/goal` to your orchestrator.

How it works (basic):
- Set `TELEGRAM_BOT_TOKEN` in your environment to a bot token from @BotFather.
- Run `python telegram_agent.py` (or import `TelegramAgent` into your app). The scaffold uses the Telegram `getUpdates`/`sendMessage` endpoints and does simple long-polling.
- Send a message like `/goal Build a simple CSV downloader` to the bot. The agent will invoke a `goal_callback` if provided (the scaffold prints the goal by default).

Security / production notes:
- The scaffold is intentionally minimal. For production use prefer a webhook (Flask/FastAPI) or use `python-telegram-bot` for robust polling/webhook management.
- Add access control: restrict allowed chat IDs or require a pre-shared secret before enqueuing goals. The scaffold demonstrates where to add such checks.

Example usage with the orchestrator:
1. Create a small adapter function in your app that accepts a goal string and calls `main.py` or the orchestrator API to enqueue/run the goal.
2. Pass that function into `TelegramAgent(..., goal_callback=your_adapter)` and start polling.

Files of interest
- `workspace/stock_analysis/fetch_price.py` — fallback script that writes `workspace/stock_analysis/price.txt` when invoked.
- `llm_router.py` — prompt trimming and automatic fallback logic lives here.
- `base_agent.py` — iterative summarization before LLM calls.

## ZIP Contents
- **ZIP 1** — Core + Agents + Planning + Models + Config
- **ZIP 2** — Memory + Skills + Security + Autonomy + Internet
- **ZIP 3** — Learning + Voice + Vision + Tests + Docker
