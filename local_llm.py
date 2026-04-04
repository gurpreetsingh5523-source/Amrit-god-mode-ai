"""Local LLM — Ollama inference backend."""
import json, urllib.request
from logger import setup_logger
logger = setup_logger("LocalLLM")

class LocalLLM:
    def __init__(self, model="llama3:latest", url="http://127.0.0.1:11434/v1"):
        self.model = model
        self.url = url

    async def complete(self, prompt: str, system: str = None, max_tokens: int = 2000) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        data = json.dumps({"model": self.model, "prompt": full, "stream": False,
                           "options": {"num_predict": max_tokens}}).encode()
        req = urllib.request.Request(f"{self.url}/chat/completions", data=data,
                                     method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read()).get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"LocalLLM error: {e}"); raise

    async def list_models(self) -> list:
        try:
            with urllib.request.urlopen(f"{self.url}/models", timeout=5) as r:
                return [m["id"] for m in json.loads(r.read()).get("data",[])]
        except: return []

    async def is_available(self) -> bool:
        return len(await self.list_models()) > 0
