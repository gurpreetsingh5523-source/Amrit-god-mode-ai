"""Model Selector — Chooses best model for each task type."""
from logger import setup_logger
logger = setup_logger("ModelSelector")

# All mapped to fast models only (mistral ~2s, gemma3 ~2.3s)
TASK_MODELS = {
    "code":       {"local": "gemma3:4b"},
    "research":   {"local": "mistral:7b-instruct-q4_K_M"},
    "analysis":   {"local": "gemma3:4b"},
    "creative":   {"local": "mistral:7b-instruct-q4_K_M"},
    "quick":      {"local": "gemma3:4b"},
    "default":    {"local": "mistral:7b-instruct-q4_K_M"},
}


class ModelSelector:
    def select(self, task_type: str, provider: str = "local") -> str:
        models = TASK_MODELS.get(task_type, TASK_MODELS["default"])
        chosen = models.get("local", list(models.values())[0])
        logger.debug(f"Selected {chosen} for {task_type}/local")
        return chosen

    def classify_task(self, task_name: str) -> str:
        n = task_name.lower()
        if any(w in n for w in ["code","write","build","program","script"]):
            return "code"
        if any(w in n for w in ["research","search","find","investigate"]):
            return "research"
        if any(w in n for w in ["analyze","analyse","examine","evaluate"]):
            return "analysis"
        if any(w in n for w in ["quick","check","status","list"]):
            return "quick"
        return "default"
