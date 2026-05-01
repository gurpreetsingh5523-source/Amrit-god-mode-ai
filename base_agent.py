"""Base Agent — Foundation for all 14 GODMODE agents."""
from abc import ABC, abstractmethod
from typing import Any
from event_bus import EventBus
from state_manager import StateManager
from logger import setup_logger


class BaseAgent(ABC):
    def __init__(self, name: str, event_bus: EventBus, state: StateManager):
        self.name       = name
        self.event_bus  = event_bus
        self.state      = state
        self.logger     = setup_logger(name)
        self._calls     = 0

    @abstractmethod
    async def execute(self, task: dict) -> dict:
        pass

    async def emit(self, event: str, data: Any = None):
        await self.event_bus.publish(event, data=data, source=self.name)

    async def report(self, msg: str, level: str = "info"):
        getattr(self.logger, level)(msg)
        await self.emit(f"{self.name}.log", {"message": msg})

    async def set_state(self, key: str, value: Any):
        await self.state.set(key, value, ns=self.name)

    def get_state(self, key: str, default=None):
        return self.state.get(key, default, ns=self.name)

    async def ask_llm(self, prompt: str, system: str = None,
                      model: str = None, max_tokens: int = 2000) -> str:
        self._calls += 1
        from llm_router import LLMRouter
        from config_loader import ConfigLoader
        cfg = ConfigLoader()

        # Read summarization config
        try:
            max_ctx = int(cfg.get("llm", "max_context_chars", default=4000))
        except Exception:
            max_ctx = 4000
        try:
            target_chars = int(cfg.get("llm", "summary_target_chars", default=800))
        except Exception:
            target_chars = 800

        router = LLMRouter()

        async def _summarize_text(text: str, goal_chars: int) -> str:
            # If text already small, return as-is
            if not isinstance(text, str):
                return ""
            if len(text) <= goal_chars:
                return text

            # Chunk the text into manageable pieces and summarize each
            chunks = [text[i:i+max_ctx] for i in range(0, len(text), max_ctx)]
            summaries = []
            for c in chunks:
                sys_prompt = (
                    "You are a concise summarizer. Extract the key facts and produce a short, "
                    f"plain-text summary no longer than {goal_chars} characters. Do not add analysis."
                )
                s = await router.complete(c, system=sys_prompt, model=model, max_tokens=max_tokens//4)
                if not isinstance(s, str):
                    s = str(s)
                summaries.append(s.strip())

            combined = "\n".join(summaries)
            # If combined still too long, recursively summarize
            if len(combined) > goal_chars:
                return await _summarize_text(combined, goal_chars)
            return combined

        # If prompt is too large, summarize older/long content first
        if isinstance(prompt, str) and len(prompt) > max_ctx:
            # produce a concise summary of the prompt to keep context
            reduced = await _summarize_text(prompt, target_chars)
            # Provide a small header so the model knows older context was summarized
            prompt = f"[SUMMARY OF PRIOR CONTEXT]\n{reduced}\n[END SUMMARY]\n{prompt[-max_ctx:]}"

        return await router.complete(prompt, system=system,
                                     model=model, max_tokens=max_tokens)

    async def ask_llm_cot(self, prompt: str, system: str = None,
                          model: str = None, max_tokens: int = 2000) -> str:
        """Chain-of-Thought via Reasoning Engine — ਅਸਲੀ ਡੂੰਘੀ ਸੋਚ."""
        try:
            from reasoning_engine import ReasoningEngine
            engine = ReasoningEngine()
            result = await engine.think(prompt, domain=self.name)
            return result.get("answer", "")
        except Exception:
            # Fallback to simple CoT if reasoning engine unavailable
            cot_prompt = f"{prompt}\n\nThink step by step:"
            return await self.ask_llm(cot_prompt, system=system,
                                      model=model, max_tokens=max_tokens)

    def ok(self, **kwargs) -> dict:
        return {"agent": self.name, "status": "ok", **kwargs}

    def err(self, error: str) -> dict:
        return {"agent": self.name, "status": "error", "error": error}
