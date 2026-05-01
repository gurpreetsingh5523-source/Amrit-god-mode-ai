"""
LLM Router — Local-First Smart Brain
═══════════════════════════════════════
ਇਹ ਸਿਸਟਮ ਲੋਕਲ LLM ਤੇ ਚੱਲਦਾ ਹੈ, ਕਲਾਊਡ ਤੇ ਨਿਰਭਰ ਨਹੀਂ।
- deepseek coder 2   → ਮੁੱਖ ਦਿਮਾਗ (thinking, planning, chat, analysis)
- deepseek coder 2 → ਕੋਡ ਲਿਖਣਾ, ਡੀਬੱਗ, ਰਿਫੈਕਟਰ
- deepseek coder 2     → ਤੇਜ਼ ਛੋਟੇ ਕੰਮ (summaries, quick checks)
- deepseek coder 2    → ਸਿਰਫ਼ fallback (ਜੇ ਲੋਕਲ ਫੇਲ੍ਹ ਹੋਵੇ)
"""

import asyncio
import os
import json
import hashlib
import re
import urllib.request
from pathlib import Path
from logger import setup_logger
from config_loader import ConfigLoader

logger = setup_logger("LLMRouter")

# ── Model Registry ────────────────────────────────────────────
# ਹੁਣ ਸਾਰੇ ਕੰਮ ਲਈ ਸਿਰਫ਼ DeepSeek (Ollama) ਦੀ ਵਰਤੋਂ ਹੋਵੇਗੀ
MODEL_REGISTRY = {
    "brain": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",  # ਸੋਚ, ਯੋਜਨਾ ਅਤੇ ਵਿਸ਼ਲੇਸ਼ਣ ਲਈ
    "coder": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",  # ਕੋਡ ਲਿਖਣ ਅਤੇ ਡੀਬੱਗਿੰਗ ਲਈ
    "coding": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",  # alias for coder
    "fast": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",  # ਤੇਜ਼ ਜਵਾਬਾਂ ਲਈ
    "reasoning": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",  # ਡੂੰਘੀ ਸੋਚ
    "creative": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",  # ਰਚਨਾਤਮਕ ਕੰਮ
    "deep": "deepseek-r1:32b",  # ਬਹੁਤ ਡੂੰਘਾ ਵਿਸ਼ਲੇਸ਼ਣ (32B)
    "embed": "nomic-embed-text:latest",  # ਐਮਬੈਡਿੰਗ (ਇਹ ਪਹਿਲਾਂ ਵਾਲਾ ਹੀ ਹੈ)
}

# Provider Registry (ਇਹ ਵੀ ਚੈੱਕ ਕਰ ਲਵੋ)
PROVIDER_REGISTRY = {
    "brain": "ollama",
    "coder": "ollama",
    "fast": "ollama",
    "embed": "ollama",
}

# ── Agent → Model Mapping ────────────────────────────────────
AGENT_MODEL_MAP = {
    "coder": "coder",
    "tester": "coder",
    "debugger": "coder",
    "planner": "brain",
    "researcher": "brain",
    "memory": "fast",
    "monitor": "fast",
    "tool": "fast",
    "upgrade": "brain",
    "vision": "brain",
    "internet": "brain",
    "dataset": "brain",
    "simulation": "brain",
    "voice": "brain",
}

# ── Coding keywords ──────────────────────────────────────────
CODE_KEYWORDS = {
    "code",
    "function",
    "class",
    "def ",
    "import ",
    "fix",
    "debug",
    "refactor",
    "implement",
    "write",
    "test",
    "error",
    "bug",
    "syntax",
    "compile",
    "python",
    "javascript",
    "html",
    "css",
    "api",
    "endpoint",
    "database",
    "ਕੋਡ",
    "ਫੰਕਸ਼ਨ",
    "ਲਿਖੋ",
    "ਠੀਕ",
    "ਡੀਬੱਗ",
}


class LLMRouter:
    def __init__(self):
        self.cfg = ConfigLoader()
        self._response_cache = {}
        self._load_response_cache()
        self._call_stats = {
            "total": 0,
            "cache_hits": 0,
            "errors": 0,
            "local_calls": 0,
            "cloud_calls": 0,
        }

    def _load_response_cache(self):
        cache_path = Path("workspace/llm_cache.json")
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                # Load last 1000 entries (was 300 — 3× more memory-efficient hits)
                self._response_cache = dict(list(data.items())[-1000:])
            except Exception:
                self._response_cache = {}
        self._cache_write_counter = 0

    def _save_response_cache(self, force: bool = False):
        """ਹਰ 10 ਕਾਲ ਤੇ ਸੇਵ ਕਰੋ (I/O waste ਘੱਟ ਕਰੋ)"""
        self._cache_write_counter = getattr(self, "_cache_write_counter", 0) + 1
        if not force and self._cache_write_counter % 10 != 0:
            return
        cache_path = Path("workspace/llm_cache.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cache_path.write_text(json.dumps(self._response_cache, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Cache save failed: {e}")

    # ── Cache normalization patterns ─────────────────────────
    _RE_UUID      = re.compile(r'[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}', re.I)
    _RE_TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?')
    _RE_ABSPATH   = re.compile(r'/(?:Users|home|tmp|var|etc)/[^\s"\']+')
    _RE_HEX40     = re.compile(r'\b[0-9a-f]{20,64}\b', re.I)  # git sha, task ids
    _RE_DIGITS    = re.compile(r'\b\d{5,}\b')                 # long numbers

    def _normalize_for_cache(self, text: str) -> str:
        """Dynamic parts ਹਟਾਓ ਤਾਂ ਕਿ cache hits ਵਧਣ।"""
        t = self._RE_UUID.sub('<UUID>', text)
        t = self._RE_TIMESTAMP.sub('<TS>', t)
        t = self._RE_ABSPATH.sub('<PATH>', t)
        t = self._RE_HEX40.sub('<HEX>', t)
        t = self._RE_DIGITS.sub('<N>', t)
        # code block ਨੂੰ fingerprint ਨਾਲ replace ਕਰੋ (content changes, structure same)
        t = re.sub(r'```[\s\S]{200,}?```', '<CODE_BLOCK>', t)
        return t.strip()

    def _cache_key(self, prompt: str, system: str, model: str) -> str:
        """Normalized cache key — dynamic content ਹਟਾ ਕੇ hash ਕਰੋ"""
        norm_prompt = self._normalize_for_cache(prompt)
        norm_system = self._normalize_for_cache(system or "")
        raw = f"{model}|{norm_system}|{norm_prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get_stats(self) -> dict:
        """AutonomyLoop / MetaCognition ਨੂੰ ਲੋੜੀਂਦੇ ਅੰਕੜੇ"""
        stats = dict(self._call_stats)
        total = stats.get("total", 0)
        hits = stats.get("cache_hits", 0)
        stats["cache_hit_rate"] = round(hits / total, 4) if total > 0 else 0.0
        stats["cache_size"] = len(self._response_cache)
        return stats

    def _pick_model_for_category(self, category: str) -> str:
        """Self-Evolution ਲਈ ਮਾਡਲ ਚੁਣਨਾ"""
        return MODEL_REGISTRY.get(category, MODEL_REGISTRY["brain"])

    def _smart_route(self, prompt: str, agent: str = None) -> str:
        """ਸਮਾਰਟ ਰਾਊਟਿੰਗ — ਏਜੰਟ ਜਾਂ ਪ੍ਰੌਂਪਟ ਦੇ ਹਿਸਾਬ ਨਾਲ ਮਾਡਲ ਚੁਣੋ"""
        # 1. Agent-based routing
        if agent and agent in AGENT_MODEL_MAP:
            category = AGENT_MODEL_MAP[agent]
            return MODEL_REGISTRY[category]

        # 2. Content-based routing
        prompt_lower = prompt.lower()[:500]
        if any(kw in prompt_lower for kw in CODE_KEYWORDS):
            return MODEL_REGISTRY["coder"]

        # 3. Short prompts → fast model
        if len(prompt) < 200:
            return MODEL_REGISTRY["fast"]

        # 4. Default → brain
        return MODEL_REGISTRY["brain"]

    async def complete(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        max_tokens: int = 2000,
        agent: str = None,
    ) -> str:
        self._call_stats["total"] += 1

        # ── Smart Model Selection ──
        if model and model in MODEL_REGISTRY.values():
            chosen = model
        elif model and "claude" in model.lower():
            chosen = self._smart_route(prompt, agent)
        else:
            chosen = self._smart_route(prompt, agent)

        # ── Prompt trimming — context window ਤੋਂ ਵੱਧ ਨਾ ਜਾਵੇ ──
        MAX_PROMPT_CHARS = 6000  # ~1500 tokens — Ollama context safe limit
        if len(prompt) > MAX_PROMPT_CHARS:
            trimmed_chars = len(prompt) - MAX_PROMPT_CHARS
            prompt = prompt[:MAX_PROMPT_CHARS] + f"\n... [{trimmed_chars} chars trimmed]"
            logger.debug(f"Prompt trimmed by {trimmed_chars} chars")

        # ── Adaptive max_tokens ──
        if max_tokens == 2000:  # caller used default
            if len(prompt) < 300:
                max_tokens = 400   # short query → short reply
            elif agent in ("monitor", "memory", "tool"):
                max_tokens = 600   # infra agents need less
            elif agent in ("coder", "tester", "debugger"):
                max_tokens = 1200  # code needs more
            else:
                max_tokens = 800   # default brain response

        # ── Cache Check (normalized key — dynamic content stripped) ──
        ckey = self._cache_key(prompt, system or "", chosen)
        if ckey in self._response_cache:
            self._call_stats["cache_hits"] += 1
            logger.info(f"Cache HIT [{ckey[:10]}...] ਕੁੱਲ hits={self._call_stats['cache_hits']}")
            return self._response_cache[ckey]

        # ── Local First → Cloud Fallback ──
        result = await self._call_local(prompt, system, chosen, max_tokens)

        if result and not result.startswith("[ERROR]"):
            self._response_cache[ckey] = result
            self._save_response_cache()
            return result

        # Fallback to Anthropic if local fails
        logger.warning(f"Local failed ({chosen}), trying Anthropic fallback...")
        cloud_result = await self._call_anthropic(prompt, system, max_tokens)
        if cloud_result and not cloud_result.startswith("[ERROR]"):
            self._response_cache[ckey] = cloud_result
            self._save_response_cache()
            return cloud_result

        return result or "[ERROR] All models failed"

    async def _call_local(self, prompt, system, model, max_tokens):
        """Ollama Local Call — Non-blocking, ਮੁੱਖ ਰਸਤਾ"""
        logger.info(f"🧠 Local: {model}")
        self._call_stats["local_calls"] += 1

        # qwen3 ਲਈ thinking token management
        actual_prompt = prompt
        actual_max = max_tokens
        if "qwen3" in model:
            # ਹਮੇਸ਼ਾ ਵਾਧੂ tokens ਦਿਓ thinking ਲਈ
            actual_max = max_tokens + 2048
            # ਛੋਟੇ ਕੰਮਾਂ ਲਈ thinking ਬੰਦ ਕਰੋ (ਤੇਜ਼ ਜਵਾਬ)
            if max_tokens <= 300:
                actual_prompt = f"/no_think {prompt}"
                actual_max = max_tokens

        url = "http://127.0.0.1:11434/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": actual_prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": actual_max},
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        def _sync_call():
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode())

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, _sync_call)
            text = resp.get("message", {}).get("content", "")

            # Strip thinking tags from qwen3
            if "נקוד" in text:
                end = text.find("נקוד")
                if end > 0:
                    text = text[end + 8 :].strip()

            return text if text else "[ERROR] Empty response"
        except Exception as e:
            logger.error(f"Local Call Failed ({model}): {e}")
            self._call_stats["errors"] += 1
            return f"[ERROR] Local: {e}"

    async def _call_anthropic(self, prompt, system, max_tokens):
        """Anthropic API — ਸਿਰਫ਼ fallback"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("$") or len(api_key) < 20:
            return "[ERROR] No valid Anthropic API key"

        self._call_stats["cloud_calls"] += 1
        model = "claude-3-5-sonnet-20241022"
        logger.info(f"☁️ Cloud fallback: {model}")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key.strip(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        def _sync_call():
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, _sync_call)
            return resp["content"][0]["text"]
        except Exception as e:
            logger.error(f"Anthropic Failed: {e}")
            self._call_stats["errors"] += 1
            return f"[ERROR] Cloud: {e}"
