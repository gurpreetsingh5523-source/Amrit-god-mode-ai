"""Task Decomposer — Recursive LLM task breakdown."""
import re
import json
from logger import setup_logger
logger = setup_logger("TaskDecomposer")

class TaskDecomposer:
    def __init__(self, max_depth=3): self.max_depth = max_depth

    async def decompose(self, task: dict, depth=0) -> list:
        if depth >= self.max_depth or self._atomic(task):
            return [task]
        try:
            from llm_router import LLMRouter
            r = await LLMRouter().complete(
                f"Break into 2-4 subtasks: {task.get('name')}"
                "\nJSON: [{\"name\":\"...\",\"agent\":\"...\",\"priority\":1}]",
                max_tokens=600)
            subtasks = self._parse(r)
            return subtasks if subtasks else [task]
        except Exception:
            return [task]

    def _atomic(self, t): return len(t.get("name","").split()) <= 4

    def _parse(self, text):
        m = re.search(r'\[.*?\]', re.sub(r"```(?:json)?|```","",text), re.DOTALL)
        return json.loads(m.group()) if m else []
