"""
☬ AmritMoERouter — Mixture of Experts Router
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenMythos MoE ਤੋਂ ਪ੍ਰੇਰਿਤ — ਹਰ ਸਵਾਲ ਲਈ ਸਹੀ ਮਾਹਰ ਚੁਣੋ।

ਅਸਲ installed models (ollama list):
  deepseek-coder-v2:16b-lite-instruct-q4_K_M  (10 GB)
  nomic-embed-text:latest                     (274 MB)

ਜਦੋਂ ਨਵੇਂ models install ਹੋਣ, ਸਿਰਫ਼ EXPERTS dict ਅੱਪਡੇਟ ਕਰੋ।
ਬਾਕੀ routing logic ਉਹੀ ਰਹੇਗਾ।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from logger import setup_logger

logger = setup_logger("AmritMoERouter")

# ── ਅਸਲ installed models ─────────────────────────────────────────
_DEEPSEEK = "deepseek-coder-v2:16b-lite-instruct-q4_K_M"
_EMBED = "nomic-embed-text:latest"

# ── Expert registry ───────────────────────────────────────────────
# ਜਦੋਂ ਕੋਈ ਨਵਾਂ model install ਹੋਵੇ, ਇੱਥੇ ਬਦਲੋ:
#   "fast":      "gemma3:4b"            (ਅਜੇ install ਨਹੀਂ)
#   "reasoning": "qwen3:8b"             (ਅਜੇ install ਨਹੀਂ)
#   "vision":    "llava:7b"             (ਅਜੇ install ਨਹੀਂ)
#   "heavy":     "deepseek-r1:32b"      (ਅਜੇ install ਨਹੀਂ)
EXPERTS = {
    "fast":      _DEEPSEEK,   # TODO: gemma3:4b ਜਾਂ qwen3:4b
    "coding":    _DEEPSEEK,   # TODO: qwen3:8b / deepseek-coder:7b
    "reasoning": _DEEPSEEK,   # TODO: qwen3:8b
    "vision":    _DEEPSEEK,   # TODO: llava:7b (ਤਸਵੀਰਾਂ ਲਈ)
    "heavy":     _DEEPSEEK,   # TODO: deepseek-r1:32b
    "cloud":     _DEEPSEEK,   # TODO: groq/claude — ਹੁਣ local fallback
    "embed":     _EMBED,      # embedding ਲਈ
}

# ── Keyword sets ──────────────────────────────────────────────────
_CODE_KW = {
    "code", "function", "class", "def ", "import ", "fix", "debug",
    "refactor", "implement", "write", "test", "error", "bug", "syntax",
    "compile", "python", "javascript", "html", "css", "api", "endpoint",
    "ਕੋਡ", "ਫੰਕਸ਼ਨ", "ਲਿਖੋ", "ਠੀਕ", "ਡੀਬੱਗ",
}

_VISION_KW = {"image", "photo", "picture", "ਤਸਵੀਰ", "screenshot", "visual"}


class AmritMoERouter:
    """
    Mixture-of-Experts router for AMRIT GodMode.

    Routes each task to the best available expert (model) based on:
    - has_image: ਤਸਵੀਰ ਵਾਲੇ ਸਵਾਲ → vision expert
    - complexity (0.0–1.0): ਸੌਖਾ/ਔਖਾ
    - task_type: "code", "reasoning", "general", "embed"
    - agent name: agent-specific routing

    ਜਦੋਂ ਨਵੇਂ models install ਹੋਣ — EXPERTS dict ਵਿੱਚ ਬਦਲੋ।
    """

    def route(
        self,
        task_type: str = "general",
        complexity: float = 0.5,
        has_image: bool = False,
        prompt: str = "",
        agent: str = "",
    ) -> str:
        """ਸਹੀ ਮਾਹਰ (model name) ਵਾਪਸ ਕਰੋ।"""

        # ── Vision override ──
        if has_image or any(kw in prompt.lower() for kw in _VISION_KW):
            model = EXPERTS["vision"]
            logger.debug(f"MoE → vision: {model}")
            return model

        # ── Embedding ──
        if task_type == "embed":
            return EXPERTS["embed"]

        # ── Code task ──
        if task_type in ("code", "coding", "debug", "refactor") or \
                any(kw in prompt.lower() for kw in _CODE_KW):
            model = EXPERTS["coding"]
            logger.debug(f"MoE → coding: {model}")
            return model

        # ── Complexity-based routing ──
        if complexity < 0.3:
            model = EXPERTS["fast"]
        elif complexity < 0.7:
            model = EXPERTS["reasoning"]
        elif complexity < 0.9:
            model = EXPERTS["heavy"]
        else:
            model = EXPERTS["cloud"]

        logger.debug(f"MoE → complexity={complexity:.2f} agent={agent or '-'}: {model}")
        return model

    def route_by_agent(self, agent: str, prompt: str = "") -> str:
        """Agent name ਤੋਂ model ਚੁਣੋ।"""
        _AGENT_MAP = {
            "coder":      "coding",
            "tester":     "coding",
            "debugger":   "coding",
            "planner":    "reasoning",
            "researcher": "reasoning",
            "monitor":    "fast",
            "memory":     "fast",
            "tool":       "fast",
            "vision":     "vision",
            "upgrade":    "reasoning",
            "dataset":    "reasoning",
            "simulation": "reasoning",
        }
        expert_key = _AGENT_MAP.get(agent, "reasoning")
        return EXPERTS[expert_key]

    @staticmethod
    def complexity_from_text(prompt: str) -> float:
        """
        Prompt ਤੋਂ complexity score (0.0–1.0) ਅੰਦਾਜ਼ਾ ਲਗਾਓ।
        ReasoningEngine.estimate_complexity() ਦਾ float version।
        """
        p = prompt.lower()
        high_signals = [
            "compiler", "interpreter", "parser", "neural network", "transformer",
            "database", "encrypt", "distributed", "implement from scratch",
            "formal proof", "theorem", "kernel",
        ]
        medium_signals = [
            "api", "server", "algorithm", "sort", "graph", "class", "design pattern",
            "analyze", "refactor", "optimize", "test",
        ]
        if any(s in p for s in high_signals) or len(prompt) > 1500:
            return 0.85
        if any(s in p for s in medium_signals) or len(prompt) > 500:
            return 0.55
        return 0.2
