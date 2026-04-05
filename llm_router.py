"""
LLM Router — Smart model selection + response caching + complexity-aware routing.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UPGRADED:
  - Response caching (same prompt = no LLM call)
  - Complexity-aware routing (hard tasks → big model)
  - Call statistics (track usage, latency, cache hits)
  - Smart fallback chain
"""
import os
import re
import json
import hashlib
import time
from pathlib import Path
from logger import setup_logger
from config_loader import ConfigLoader
logger = setup_logger("LLMRouter")

# ── BitNet b1.58 Config ──────────────────────────────────────────
import subprocess
import shutil
BITNET_DIR = Path.home() / "BitNet"
BITNET_MODEL = BITNET_DIR / "models" / "Falcon3-10B-Instruct-1.58bit" / "ggml-model-i2_s.gguf"
BITNET_SCRIPT = BITNET_DIR / "run_inference.py"

# BitNet PRIMARY disabled — llama-server doesn't apply custom i2_s kernels correctly.
# BitNet subprocess (42s) is correct but too slow for interactive use.
# Ollama (mistral ~2s) is fastest + correct → use as primary.
# BitNet subprocess kept as OFFLINE fallback only (Ollama completely down).
BITNET_PRIMARY = False
BITNET_SERVER_URL = "http://127.0.0.1:8080"

def _bitnet_available() -> bool:
    """Check if BitNet model and script exist."""
    return BITNET_SCRIPT.exists() and BITNET_MODEL.exists()

def _bitnet_server_alive() -> bool:
    """Check if the BitNet llama-server HTTP endpoint is up."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BITNET_SERVER_URL}/health", timeout=2) as r:
            return json.loads(r.read()).get("status") == "ok"
    except Exception:
        return False

def _bitnet_server_complete(prompt: str, system: str = None, n_predict: int = 400) -> str:
    """Query the running BitNet llama-server via HTTP (fast — model already loaded)."""
    import urllib.request
    sys_text = system or "You are a helpful AI assistant."
    # Use OpenAI-compatible chat completions endpoint (handles template automatically)
    messages = [
        {"role": "system", "content": sys_text},
        {"role": "user", "content": prompt},
    ]
    payload = json.dumps({
        "messages": messages,
        "n_predict": n_predict,
        "temperature": 0.7,
        "stream": False,
        "stop": ["<|user|>", "<|system|>"],
    }).encode()
    req = urllib.request.Request(
        f"{BITNET_SERVER_URL}/v1/chat/completions",
        data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
    return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

def _bitnet_complete(prompt: str, system: str = None, n_predict: int = 500, threads: int = 4) -> str:
    """Run inference via bitnet.cpp subprocess using Falcon3 instruct format."""
    sys_text = system or "You are a helpful AI assistant."
    # Falcon3 / llama instruct chat template
    formatted = (
        f"<|system|>\n{sys_text}\n"
        f"<|user|>\n{prompt}\n"
        f"<|assistant|>\n"
    )
    cmd = [
        "python3", str(BITNET_SCRIPT),
        "-m", str(BITNET_MODEL),
        "-p", formatted,
        "-n", str(n_predict),
        "-t", str(threads),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=300, cwd=str(BITNET_DIR)
    )
    output = result.stdout
    # Extract assistant reply after the last <|assistant|> marker
    if "<|assistant|>" in output:
        output = output.rsplit("<|assistant|>", 1)[-1].strip()
    if "[end of text]" in output:
        output = output.replace("[end of text]", "").strip()
    return output or "[BitNet: empty response]"

# ── Model Registry ────────────────────────────────────────────────
# Ranked by speed: mistral ~2s, gemma3 ~2.3s, llama3/qwen slow
MODEL_REGISTRY = {
    "coding":    ["amrit-coder-v2:latest", "gemma3:4b", "mistral:7b-instruct-q4_K_M"],
    "reasoning": ["gemma3:4b", "mistral:7b-instruct-q4_K_M"],
    "fast":      ["gemma3:4b", "mistral:7b-instruct-q4_K_M"],
    "creative":  ["mistral:7b-instruct-q4_K_M", "gemma3:4b"],
    "punjabi":   ["amrit-coder-v2:latest", "mistral:7b-instruct-q4_K_M", "gemma3:4b"],
    "general":   ["amrit-coder-v2:latest", "mistral:7b-instruct-q4_K_M", "gemma3:4b"],
    # Heavy refactoring — uses larger model if available
    "refactor":  ["amrit-coder-v2:latest", "qwen2.5-coder:7b", "gemma3:4b"],
    # Deep thinking — Qwen3-32B via AirLLM (~22s/tok, use for high-value queries)
    "deep":      ["qwen3-32b-airllm"],
}

# Keywords that trigger smart model selection
_CODE_WORDS = {"code", "fix", "debug", "refactor", "function", "class",
               "python", "javascript", "html", "css", "api", "ਕੋਡ"}
_REASON_WORDS = {"analyze", "explain", "why", "how", "plan", "decompose",
                  "ਸਮਝਾਓ", "ਵਿਸ਼ਲੇਸ਼ਣ", "ਕਿਉਂ", "ਕਿਵੇਂ"}
_CREATIVE_WORDS = {"poem", "story", "essay", "song", "lyrics", "letter",
                   "ਕਵਿਤਾ", "ਗੀਤ", "ਕਹਾਣੀ", "ਲੇਖ", "ਚਿੱਠੀ",
                   "shayari", "ਸ਼ਾਇਰੀ", "joke", "ਚੁਟਕਲਾ"}
_DEEP_WORDS = {"deep", "qwen3", "airllm", "32b", "ਡੂੰਘਾ", "ਡੂੰਘੀ"}

class LLMRouter:
    _airllm_model = None  # Singleton — keep loaded across calls

    def __init__(self):
        self.cfg = ConfigLoader()
        self._available_cache = None
        self._response_cache = {}
        self._load_response_cache()
        self._call_stats = {"total": 0, "cache_hits": 0, "errors": 0,
                            "total_latency": 0.0, "by_model": {}}

    def _load_response_cache(self):
        """Load response cache from disk for persistence across restarts."""
        cache_path = Path("workspace/llm_cache.json")
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                # Only load last 300 entries
                if isinstance(data, dict):
                    items = list(data.items())[-300:]
                    self._response_cache = dict(items)
            except Exception:
                self._response_cache = {}

    def _save_response_cache(self):
        """Persist cache to disk."""
        cache_path = Path("workspace/llm_cache.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        trimmed = dict(list(self._response_cache.items())[-300:])
        cache_path.write_text(json.dumps(trimmed, ensure_ascii=False, default=str))

    @staticmethod
    def _cache_key(prompt: str, system: str = "", model: str = "") -> str:
        raw = f"{model}||{system}||{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    async def _get_available_models(self) -> list:
        """Check which models Ollama actually has loaded."""
        if self._available_cache is not None:
            return self._available_cache
        try:
            import urllib.request
            import json
            with urllib.request.urlopen("http://127.0.0.1:11434/v1/models", timeout=3) as r:
                models = [m["id"] for m in json.loads(r.read()).get("data", [])]
                self._available_cache = models
                return models
        except Exception:
            self._available_cache = []
            return []

    def _pick_model(self, prompt: str, model: str = None) -> str:
        """Pick the best model based on prompt content + complexity."""
        if model:
            return model
        low = prompt.lower()
        # Use word-boundary extraction so "coder" doesn't match "code"
        words = set(re.findall(r'[a-z0-9]+|[\u0A00-\u0A7F]+', low))
        # Check creative BEFORE code (poem/song/story should never go to coder)
        if words & _CREATIVE_WORDS:
            return self._first_available("creative")
        # Explicit "deep" request → Qwen3-32B via AirLLM
        if words & _DEEP_WORDS:
            return "qwen3-32b-airllm"
        if words & _CODE_WORDS:
            return self._first_available("coding")
        if words & _REASON_WORDS:
            return self._first_available("reasoning")

        # Complexity-aware routing: long/complex prompts get bigger models
        from reasoning_engine import estimate_complexity
        complexity = estimate_complexity(prompt)
        if complexity == "high":
            return self._first_available("reasoning")
        if complexity == "low" and len(prompt) < 200:
            return self._first_available("fast")

        return self._first_available("general")

    def _first_available(self, category: str) -> str:
        """Return first available model from category, fallback to default."""
        candidates = MODEL_REGISTRY.get(category, MODEL_REGISTRY["general"])
        available = self._available_cache or []
        for m in candidates:
            if m in available:
                return m
        return candidates[-1]  # fallback to last

    def _pick_model_for_category(self, category: str) -> str:
        """Category-aware model pick — used by agents. Does a quick sync Ollama list if cache not yet warm."""
        if self._available_cache is None:
            try:
                import urllib.request as _ur
                import json as _j
                with _ur.urlopen("http://127.0.0.1:11434/v1/models", timeout=2) as _r:
                    self._available_cache = [m["id"] for m in _j.loads(_r.read()).get("data", [])]
            except Exception:
                self._available_cache = []
        return self._first_available(category)

    async def complete(self, prompt: str, system: str = None,
                       model: str = None, max_tokens: int = 2000) -> str:
        self._call_stats["total"] += 1

        # ── BitNet PRIMARY path ──
        if BITNET_PRIMARY and not model:
            result = await self._try_bitnet(prompt, system, max_tokens)
            if result:
                return result

        # ── Pick model ──
        if self._available_cache is None:
            await self._get_available_models()
        chosen = self._pick_model(prompt, model)

        # ── AirLLM deep path (Qwen3-32B) ──
        if chosen == "qwen3-32b-airllm":
            result = await self._try_airllm(prompt, system, max_tokens)
            if result:
                return result

        # ── Ollama path ──
        return await self._try_ollama(prompt, system, chosen, max_tokens)

    async def _try_bitnet(self, prompt: str, system: str, max_tokens: int) -> str:
        """Try BitNet (server or subprocess). Returns result or empty string."""
        use_server = _bitnet_server_alive()
        use_subprocess = (not use_server) and _bitnet_available()
        if not (use_server or use_subprocess):
            return ""

        cache_key = self._cache_key(prompt, system or "", "bitnet")
        if cache_key in self._response_cache:
            self._call_stats["cache_hits"] += 1
            logger.info("Cache HIT [BitNet]")
            return self._response_cache[cache_key]

        backend = "server" if use_server else "subprocess"
        logger.info(f"Model: BitNet Falcon3-10B b1.58 [{backend}]")
        try:
            import asyncio
            n_tok = min(max_tokens, 400)
            fn = (lambda: _bitnet_server_complete(prompt, system, n_tok)) if use_server \
                 else (lambda: _bitnet_complete(prompt, system, n_tok))
            result = await asyncio.get_event_loop().run_in_executor(None, fn)
            self._record_latency("bitnet", time.time())
            if result and not result.startswith("[BitNet"):
                self._cache_result(cache_key, result)
                return result
            logger.warning("BitNet empty/bad response, falling back to Ollama")
        except Exception as be:
            logger.warning(f"BitNet failed ({be}), falling back to Ollama")
        return ""

    async def _try_airllm(self, prompt: str, system: str, max_tokens: int) -> str:
        """Try Qwen3-32B via AirLLM. Returns result or empty string."""
        cache_key = self._cache_key(prompt, system or "", "qwen3-32b-airllm")
        if cache_key in self._response_cache:
            self._call_stats["cache_hits"] += 1
            logger.info("Cache HIT [Qwen3-32B AirLLM]")
            return self._response_cache[cache_key]

        logger.info("Model: Qwen3-32B via AirLLM (deep mode, ~22s/tok)")
        try:
            import asyncio
            n_tok = min(max_tokens, 150)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            start = time.time()
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._airllm_complete(full_prompt, n_tok)
            )
            self._record_latency("qwen3-32b-airllm", start)
            if result and not result.startswith("[ERROR"):
                self._cache_result(cache_key, result, save_now=True)
                return result
            logger.warning("AirLLM empty response, falling back to Ollama")
        except Exception as ae:
            logger.warning(f"AirLLM failed ({ae}), falling back to Ollama")
        return ""

    async def _try_ollama(self, prompt: str, system: str,
                          chosen: str, max_tokens: int) -> str:
        """Try Ollama with fallback chain: chosen → config default → BitNet."""
        cache_key = self._cache_key(prompt, system or "", chosen)
        if cache_key in self._response_cache:
            self._call_stats["cache_hits"] += 1
            logger.info(f"Cache HIT [{chosen}] (saved 1 LLM call)")
            return self._response_cache[cache_key]

        logger.info(f"Model: {chosen} [Ollama fallback]")
        try:
            start = time.time()
            result = await self._local(prompt, system, chosen, max_tokens)
            self._record_latency(chosen, start)
            if not result.startswith("[ERROR]"):
                self._cache_result(cache_key, result)
            return result
        except Exception as e:
            self._call_stats["errors"] += 1
            # Fallback 1: config default model
            fallback = self.cfg.get("llm", "model", "llama3:latest")
            if chosen != fallback:
                logger.warning(f"{chosen} failed, trying {fallback}: {e}")
                try:
                    return await self._local(prompt, system, fallback, max_tokens)
                except Exception as e2:
                    logger.warning(f"Ollama fallback also failed: {e2}")
            # Fallback 2: BitNet offline
            if _bitnet_available():
                logger.warning("Ollama unavailable — falling back to BitNet b1.58 (local)")
                try:
                    import asyncio
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: _bitnet_complete(prompt, system, max_tokens)
                    )
                except Exception as be:
                    logger.error(f"BitNet fallback failed: {be}")
            return f"[ERROR] LLM unavailable: {e}"

    def _record_latency(self, model_name: str, start_time: float):
        """Record latency stats for a model call."""
        latency = time.time() - start_time
        self._call_stats["total_latency"] += latency
        stats = self._call_stats["by_model"].setdefault(model_name, {"calls": 0, "latency": 0})
        stats["calls"] += 1
        stats["latency"] += latency

    def _cache_result(self, cache_key: str, result: str, save_now: bool = False):
        """Cache an LLM response, optionally flushing to disk."""
        self._response_cache[cache_key] = result
        if save_now or len(self._response_cache) % 20 == 0:
            self._save_response_cache()

    def get_stats(self) -> dict:
        """Return call statistics for monitoring."""
        total = self._call_stats["total"]
        hits = self._call_stats["cache_hits"]
        return {
            **self._call_stats,
            "cache_hit_rate": round(hits / max(total, 1), 2),
            "avg_latency": round(
                self._call_stats["total_latency"] / max(total - hits, 1), 2
            ),
            "cache_size": len(self._response_cache),
        }

    async def _local(self, prompt, system, model, max_tokens):
        import urllib.request
        import json
        import time
        base_url = "http://127.0.0.1:11434/v1"
        mn = model or "llama3:latest"
        # Compose OpenAI-compatible messages list
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": mn,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False
        }
        # Debug logging disabled for speed
        # print("[LLM DEBUG] Payload sent to LLM:", json.dumps(payload, ensure_ascii=False, indent=2))
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{base_url}/chat/completions", data=data,
                                     method="POST", headers={"Content-Type": "application/json"})
        try:
            timeout_secs = int(self.cfg.get("llm", "request_timeout", default=120))
        except Exception:
            timeout_secs = 120
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout_secs) as r:
                resp = r.read()
                elapsed = time.time() - start
                if elapsed > 30:
                    print(f"[LLM WARNING] LLM response took {elapsed:.1f} seconds.")
                return json.loads(resp).get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"[LLM ERROR] LLM request failed: {e}")
            return f"[ERROR] LLM request failed or timed out: {e}"

    def _airllm_complete(self, prompt: str, max_new_tokens: int = 100) -> str:
        """Run Qwen3-32B via AirLLM layer-by-layer inference (~22s/tok, MLX backend)."""
        try:
            from airllm import AutoModel
        except ImportError:
            return "[ERROR] airllm not installed — pip install airllm"
        if LLMRouter._airllm_model is None:
            logger.info("Loading Qwen3-32B via AirLLM (first call — model init)...")
            LLMRouter._airllm_model = AutoModel.from_pretrained("Qwen/Qwen3-32B")
        model = LLMRouter._airllm_model
        input_ids = model.tokenizer(prompt, return_tensors="pt").input_ids
        result = model.generate(input_ids, max_new_tokens=max_new_tokens)
        return result.strip() if result else ""
