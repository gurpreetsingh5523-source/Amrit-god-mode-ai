"""
Example AMRIT GODMODE Plugin — Translator Agent
Translates text between languages using local LLM.
"""

from base_agent import BaseAgent

PLUGIN_INFO = {
    "name": "translator",
    "version": "1.0",
    "description": "Translates text between languages via local LLM",
    "author": "AMRIT Community",
}


class TranslatorAgent(BaseAgent):
    async def execute(self, task: dict) -> dict:
        text = task.get("text", task.get("name", ""))
        source_lang = task.get("from", "auto")
        target_lang = task.get("to", "Punjabi")

        prompt = f"Translate the following to {target_lang}:\n\n{text}"
        if source_lang != "auto":
            prompt = f"Translate from {source_lang} to {target_lang}:\n\n{text}"

        result = await self.ask_llm(prompt, max_tokens=500)
        return self.ok(translation=result, source=source_lang, target=target_lang)


def register(event_bus, state):
    return TranslatorAgent("translator", event_bus, state)
