"""
"brain": "gemma3:12b",  # ਸੋਚ, ਯੋਜਨਾ ਅਤੇ ਵਿਸ਼ਲੇਸ਼ਣ ਲਈ
    "coder": "gemma3:12b",  # ਕੋਡ ਲਿਖਣ ਅਤੇ ਡੀਬੱਗਿੰਗ ਲਈ
    "coding": "gemma3:12b",  # alias for coder
    "fast": "gemma3:12b",  # ਤੇਜ਼ ਜਵਾਬਾਂ ਲਈ
    "reasoning": "gemma3:12b",  # ਡੂੰਘੀ ਸੋਚ
    "creative": "gemma3:12b",  # ਰਚਨਾਤਮਕ ਕੰਮ
    "deep": "gemma3:12b",  # 32B ਵਾਲਾ ਹੈਂਗ ਕਰੇਗਾ, ਇਸ ਲਈ ਇਸਨੂੰ ਵੀ ਜੈਮਾ 'ਤੇ ਸੈੱਟ ਕਰ ਦਿੱਤਾ
"""

import asyncio
import os
import json
import hashlib
import urllib.request
from pathlib import Path
from logger import setup_logger
from config_loader import ConfigLoader

logger = setup_logger("LLMRouter")

# ── Model Registry v3.1 ────────────────────────────────────────
# DeepSeek V4 cloud (API) = PRIMARY for all text/code tasks
# gemma3:12b (local Ollama) = fallback when no internet/API quota
# gemma4:e4b (local Ollama) = vision/screen only
MODEL_REGISTRY = {
    "brain":     "deepseek-chat",      # DeepSeek V4 cloud — best intelligence
    "coder":     "deepseek-chat",      # DeepSeek V4 — top coding model
    "coding":    "deepseek-chat",
    "fast":      "deepseek-chat",      # Fast + smart via API
    "reasoning": "deepseek-reasoner",  # DeepSeek R1 — deep reasoning
    "creative":  "gemma3:12b",
    "deep":      "gemma3:12b",
    "creative":  "deepseek-chat",
    "deep":      "deepseek-reasoner",  # R1 for deep analysis
    # gemma4:e4b = vision only (local, 5GB RAM, multimodal)
    "vision":    "gemma4:e4b",
    "multimodal":"gemma4:e4b",
    "embed":     "nomic-embed-text:latest",
    # Local fallbacks (no API needed)
    "_local":    "gemma3:12b",
    "_qwen35":   "qwen3.5:9b",
    "_fallback": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",
}

PROVIDER_REGISTRY = {
    "brain": "deepseek", "coder": "deepseek", "fast": "deepseek",
    "reasoning": "deepseek", "creative": "deepseek", "deep": "deepseek",
    "vision": "ollama", "multimodal": "ollama", "embed": "ollama",
}

# ── Agent → Model Mapping ────────────────────────────────────
AGENT_MODEL_MAP = {
    "coder":      "coder",
    "tester":     "coder",
    "debugger":   "coder",
    "planner":    "brain",
    "researcher": "brain",
    "memory":     "fast",
    "monitor":    "fast",
    "tool":       "fast",
    "upgrade":    "brain",
    "vision":     "vision",       # → gemma4:e4b
    "internet":   "brain",
    "dataset":    "brain",
    "simulation": "brain",
    "voice":      "fast",         # voice needs fast response
    "screen":     "vision",       # screen control → gemma4:e4b
    "fullstack":  "coder",        # React/Next.js → qwen3.5:9b
    "ui":         "creative",     # UI design → qwen3.5:9b
    "swift":      "coder",        # iOS/macOS → qwen3.5:9b
    "db":         "coder",        # database → qwen3.5:9b
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
        try:
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
        except ConfigLoader.ConfigError as e:
            logger.error(f"Failed to load config in __init__: {e}")
            raise
        except (IOError, OSError) as e:
            logger.error(f"IO/OS error in __init__: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in __init__: {e}")
            raise

    def _load_response_cache(self):
        cache_path = Path("workspace/llm_cache.json")
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                self._response_cache = dict(list(data.items())[-300:])
            except Exception:
                self._response_cache = {}

    def _save_response_cache(self):
        cache_path = Path("workspace/llm_cache.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cache_path.write_text(json.dumps(self._response_cache, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Cache save failed: {e}")

    def _cache_key(self, prompt: str, system: str, model: str) -> str:
        """Cache lookup key ਬਣਾਓ"""
        import hashlib
        raw = f"{model}|{system}|{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get_stats(self) -> dict:
        """AutonomyLoop / MetaCognition ਨੂੰ ਲੋੜੀਂਦੇ ਅੰਕੜੇ"""
        try:
            stats = dict(self._call_stats)
            total = stats.get("total", 0)
            hits = stats.get("cache_hits", 0)
            stats["cache_hit_rate"] = round(hits / total, 4) if total > 0 else 0.0
            stats["cache_size"] = len(self._response_cache)
            return stats
        except (TypeError, ValueError, AttributeError, KeyError, ZeroDivisionError) as e:
            logger.error(f"Error computing stats: {e}")
            return {"total": 0, "cache_hits": 0, "cache_hit_rate": 0.0, "cache_size": 0}

    def _available_models(self) -> set:
        """Return set of model names currently pulled in Ollama."""
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read())
            return {m["name"] for m in data.get("models", [])}
        except Exception:
            return set()

    # keywords that signal a genuinely hard / reasoning-heavy task
    _COMPLEX_HINTS = (
        "architecture", "design a", "debug", "why does", "why is", "root cause",
        "step by step", "step-by-step", "plan the", "decompose", "trade-off",
        "tradeoff", "optimize", "refactor", "prove", "algorithm for", "complex",
        "multi-step", "reason through", "analyze deeply",
    )

    def _is_complex(self, prompt: str) -> bool:
        """Heuristic: is this task hard enough to deserve the reasoning model?
        Conservative — long prompts or explicit reasoning keywords only, so we
        don't slow down routine generation."""
        if not prompt:
            return False
        p = prompt.lower()
        if len(prompt) > 4000:               # large context → likely complex
            return True
        return sum(1 for k in self._COMPLEX_HINTS if k in p) >= 2

    def _resolve_model(self, model_name: str) -> str:
        """Return model_name if available, else fallback to what's installed.
        Cloud models (deepseek-*, gpt-*, claude-*) are never resolved to local."""
        # Cloud model names — don't try to match against Ollama
        if model_name.startswith(("deepseek-", "gpt-", "claude-", "gemini-")):
            return model_name
        available = self._available_models()
        if not available:
            return model_name
        if model_name in available:
            return model_name
        # Try prefix match (e.g. "qwen3.5:9b" matches "qwen3.5:9b-q4_K_M")
        for m in available:
            if m.startswith(model_name.split(":")[0]):
                return m
        # Hard fallback chain
        for fallback in [MODEL_REGISTRY["_fallback"], "gemma3:12b", list(available)[0]]:
            if fallback in available:
                logger.warning(f"Model {model_name!r} not found → using {fallback!r}")
                return fallback
        return model_name

    def _pick_model_for_category(self, category: str) -> str:
        """Self-Evolution ਲਈ ਮਾਡਲ ਚੁਣਨਾ"""
        chosen = MODEL_REGISTRY.get(category, MODEL_REGISTRY["brain"])
        return self._resolve_model(chosen)

    def _smart_route(self, prompt: str, agent: str = None) -> str:
        """ਸਮਾਰਟ ਰਾਊਟਿੰਗ — ਏਜੰਟ ਜਾਂ ਪ੍ਰੌਂਪਟ ਦੇ ਹਿਸਾਬ ਨਾਲ ਮਾਡਲ ਚੁਣੋ"""
        import os
        # Voice mode always uses the fast model for low latency
        if os.environ.get("AMRIT_VOICE_MODE") == "1":
            return MODEL_REGISTRY["fast"]

        # 1. Agent-based routing
        if agent and agent in AGENT_MODEL_MAP:
            category = AGENT_MODEL_MAP[agent]
            return self._resolve_model(MODEL_REGISTRY[category])

        # 2. Vision/image content → gemma4:e4b (only explicit vision tasks)
        prompt_lower = prompt.lower()[:500]
        if any(kw in prompt_lower for kw in ("screenshot", "analyze image", "describe image",
                                              "look at image", "what is in the image")):
            return self._resolve_model(MODEL_REGISTRY["vision"])

        # 3. Coding content → qwen3.5:9b
        if any(kw in prompt_lower for kw in CODE_KEYWORDS):
            return self._resolve_model(MODEL_REGISTRY["coder"])

        # 4. Short prompts → fast model
        if len(prompt) < 200:
            return self._resolve_model(MODEL_REGISTRY["fast"])

        # 5. Default → brain
        return self._resolve_model(MODEL_REGISTRY["brain"])

    async def complete(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        max_tokens: int = 2000,
        agent: str = None,
    ) -> str:
        try:
            self._call_stats["total"] += 1

            # ── Amrit's OWN fine-tuned coding brain (MLX + LoRA on verified data) ──
            if model in ("amrit-coder", "finetuned", "amrit"):
                try:
                    import amrit_finetuned, asyncio as _aio
                    if amrit_finetuned.is_available():
                        logger.info("🧠 routing to Amrit's fine-tuned model")
                        return await _aio.to_thread(amrit_finetuned.complete, prompt, system, max_tokens)
                    logger.warning("amrit-coder requested but adapter/MLX missing → falling back")
                except ImportError as e:
                    logger.error(f"amrit fine-tuned import failed ({e}) → falling back")
                except Exception as e:
                    logger.error(f"amrit fine-tuned failed ({e}) → falling back")

            # ── Smart Model Selection ──
            if model in ("reasoning", "deep"):
                # Explicit request for the deep-reasoning model (DeepSeek R1).
                chosen = MODEL_REGISTRY.get("reasoning", "deepseek-reasoner")
            elif model and model in MODEL_REGISTRY.values():
                chosen = model
            elif model and "claude" in model.lower():
                # Explicit cloud request → try local first, fallback to cloud
                chosen = self._smart_route(prompt, agent)
            else:
                chosen = self._smart_route(prompt, agent)
                # AUTO-ESCALATE clearly-hard tasks to the reasoning model (Phase 3).
                if chosen.startswith("deepseek-") and self._is_complex(prompt):
                    chosen = MODEL_REGISTRY.get("reasoning", "deepseek-reasoner")
                    logger.info("🧠 escalated to reasoning model (deep task)")

            # ── Cache Check ──
            ckey = hashlib.sha256(f"{chosen}{system}{prompt}".encode()).hexdigest()[:20]
            if ckey in self._response_cache:
                self._call_stats["cache_hits"] += 1
                logger.info(f"Cache HIT: {ckey}")
                return self._response_cache[ckey]

            # ── Route: DeepSeek API → Local Ollama → Anthropic ──
            provider = PROVIDER_REGISTRY.get(
                AGENT_MODEL_MAP.get(agent, "brain"), "deepseek"
            )
            is_deepseek_model = chosen.startswith("deepseek-")
            is_vision = chosen in ("gemma4:e4b", "llava:7b")

            if is_vision:
                # Vision always runs local
                result = await self._call_local(prompt, system, chosen, max_tokens)
            elif is_deepseek_model:
                # Try DeepSeek API first
                result = await self._call_deepseek(prompt, system, chosen, max_tokens)
                if not result or result.startswith("[ERROR]"):
                    logger.warning(f"DeepSeek API failed → local fallback (gemma3:12b)")
                    result = await self._call_local(prompt, system, "gemma3:12b", max_tokens)
            else:
                # Local model (gemma3, qwen3.5 etc)
                result = await self._call_local(prompt, system, chosen, max_tokens)
                if not result or result.startswith("[ERROR]"):
                    logger.warning(f"Local failed ({chosen}) → DeepSeek fallback")
                    result = await self._call_deepseek(prompt, system, "deepseek-chat", max_tokens)

            if result and not result.startswith("[ERROR]"):
                self._response_cache[ckey] = result
                self._save_response_cache()
                return result

            # Last resort: Anthropic
            logger.warning(f"All primary failed → Anthropic last resort")
            cloud_result = await self._call_anthropic(prompt, system, max_tokens)
            if cloud_result and not cloud_result.startswith("[ERROR]"):
                self._response_cache[ckey] = cloud_result
                self._save_response_cache()
                return cloud_result

            return result or "[ERROR] All models failed"
        except KeyError as e:
            logger.error(f"Key error in complete(): {e}")
            return "[ERROR] Internal error"
        except ValueError as e:
            logger.error(f"Value error in complete(): {e}")
            return "[ERROR] Invalid input"
        except Exception as e:
            logger.error(f"Unexpected error in complete(): {e}")
            return "[ERROR] Unexpected error"

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

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": actual_prompt})

        is_qwen3 = "qwen3" in model.lower()
        options = {"num_predict": max(actual_max, 2000) if is_qwen3 else actual_max}

        def _sync_call_ollama():
            """Use ollama Python library — correctly separates thinking from content."""
            import ollama as _ollama
            resp = _ollama.chat(
                model=model,
                messages=messages,
                options=options
            )
            # ollama library gives us resp.message.content (actual answer)
            # and resp.message.thinking (internal reasoning) separately
            text = (resp.message.content or "").strip()
            import re as _re
            text = _re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
            return text

        def _sync_call_http():
            """Fallback: raw HTTP if ollama library unavailable."""
            url = "http://127.0.0.1:11434/api/chat"
            payload = {"model": model, "messages": messages,
                       "stream": False, "options": options}
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read().decode())
            return (d.get("message", {}).get("content") or "").strip()

        # qwen3.5 thinking needs ~200s; other models 120s
        call_timeout = 250 if is_qwen3 else 120

        try:
            loop = asyncio.get_event_loop()
            try:
                text = await asyncio.wait_for(
                    loop.run_in_executor(None, _sync_call_ollama),
                    timeout=call_timeout
                )
            except (asyncio.TimeoutError, Exception):
                text = await asyncio.wait_for(
                    loop.run_in_executor(None, _sync_call_http),
                    timeout=call_timeout
                )

            return text if text else "[ERROR] Empty response"
        except asyncio.TimeoutError:
            logger.error(f"Timeout ({call_timeout}s) for {model}")
            self._call_stats["errors"] += 1
            return f"[ERROR] Timeout after {call_timeout}s"
        except Exception as e:
            logger.error(f"Local Call Failed ({model}): {e}")
            self._call_stats["errors"] += 1
            return f"[ERROR] Local: {e}"

    async def _call_deepseek(self, prompt, system, model, max_tokens):
        """DeepSeek API — Primary cloud LLM (OpenAI-compatible)."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        if not api_key or len(api_key) < 10:
            return "[ERROR] No DEEPSEEK_API_KEY in .env"

        logger.info(f"🌐 DeepSeek: {model}")
        self._call_stats["cloud_calls"] += 1

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": False,
        }

        def _sync_call():
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())

        try:
            loop = asyncio.get_event_loop()
            resp = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_call), timeout=120
            )
            text = resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if text:
                usage = resp.get("usage", {})
                logger.info(f"   DeepSeek tokens: {usage.get('prompt_tokens',0)}→{usage.get('completion_tokens',0)}")
            return text if text else "[ERROR] DeepSeek empty response"
        except asyncio.TimeoutError:
            return "[ERROR] DeepSeek timeout"
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            return f"[ERROR] DeepSeek: {e}"

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