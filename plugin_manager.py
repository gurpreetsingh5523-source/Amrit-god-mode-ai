"""
AMRIT GODMODE — Plugin System
==============================
Allows external developers to create and register custom agents.
Plugins are Python files in amrit_plugins/ with a simple contract.

Google lightweight principle: no pip install, no registry server,
just drop a .py file and it auto-loads.

Plugin Contract:
    1. File in amrit_plugins/ directory
    2. Has a class inheriting from BaseAgent
    3. Has PLUGIN_INFO dict with metadata
    4. Has register(event_bus, state) function

Example plugin (amrit_plugins/my_agent.py):
    from base_agent import BaseAgent
    
    PLUGIN_INFO = {
        "name": "my_agent",
        "version": "1.0",
        "description": "My custom agent",
        "author": "YourName",
    }
    
    class MyAgent(BaseAgent):
        async def execute(self, task):
            result = await self.ask_llm(task.get("name", ""))
            return self.ok(output=result)
    
    def register(event_bus, state):
        return MyAgent("my_agent", event_bus, state)
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Optional
from logger import setup_logger

logger = setup_logger("plugins")

PLUGINS_DIR = "amrit_plugins"
REQUIRED_KEYS = {"name", "version", "description"}


class PluginManager:
    """
    Lightweight plugin loader — scans amrit_plugins/ dir,
    validates, and registers custom agents into orchestrator.
    """

    def __init__(self):
        self.plugins: dict[str, dict] = {}   # name → {info, module, agent}
        self.errors: list[str] = []

    def discover(self, plugins_dir: str = PLUGINS_DIR) -> list[dict]:
        """Scan plugins directory and return plugin info list."""
        plugins_path = Path(plugins_dir)
        if not plugins_path.exists():
            plugins_path.mkdir(parents=True, exist_ok=True)
            self._create_example_plugin(plugins_path)
            logger.info(f"📦 Created {PLUGINS_DIR}/ with example plugin")

        found = []
        for py_file in sorted(plugins_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            info = self._inspect_plugin(py_file)
            if info:
                found.append(info)

        logger.info(f"📦 Discovered {len(found)} plugins in {PLUGINS_DIR}/")
        return found

    def load_all(self, event_bus, state, plugins_dir: str = PLUGINS_DIR) -> dict:
        """Load and register all valid plugins. Returns name → agent dict."""
        agents = {}
        discovered = self.discover(plugins_dir)

        for info in discovered:
            try:
                agent = self._load_plugin(info, event_bus, state)
                if agent:
                    agents[info["name"]] = agent
                    self.plugins[info["name"]] = {
                        "info": info,
                        "agent": agent,
                    }
                    logger.info(f"   ✅ {info['name']} v{info['version']} — {info['description']}")
            except Exception as e:
                error_msg = f"Plugin {info.get('name', info['file'])}: {e}"
                self.errors.append(error_msg)
                logger.warning(f"   ❌ {error_msg}")

        return agents

    def _inspect_plugin(self, path: Path) -> Optional[dict]:
        """Validate plugin file has required PLUGIN_INFO."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"amrit_plugin_{path.stem}", str(path)
            )
            module = importlib.util.module_from_spec(spec)

            # Read PLUGIN_INFO without executing full module
            source = path.read_text(encoding="utf-8")

            # Basic safety: block dangerous imports
            dangerous = ["subprocess.call(", "os.system(", "exec(", "eval(", "__import__"]
            for d in dangerous:
                if d in source:
                    self.errors.append(f"{path.name}: blocked dangerous pattern '{d}'")
                    logger.warning(f"   🛡️ {path.name}: blocked (contains '{d}')")
                    return None

            # Load and check
            spec.loader.exec_module(module)

            info = getattr(module, "PLUGIN_INFO", None)
            if not info or not isinstance(info, dict):
                return None

            missing = REQUIRED_KEYS - set(info.keys())
            if missing:
                self.errors.append(f"{path.name}: missing fields {missing}")
                return None

            register_fn = getattr(module, "register", None)
            if not callable(register_fn):
                self.errors.append(f"{path.name}: no register() function")
                return None

            info["file"] = str(path)
            info["module"] = module
            return info

        except Exception as e:
            self.errors.append(f"{path.name}: {e}")
            return None

    def _load_plugin(self, info: dict, event_bus, state):
        """Call plugin's register() to get agent instance."""
        module = info.get("module")
        if not module:
            return None

        register_fn = getattr(module, "register")
        agent = register_fn(event_bus, state)

        # Verify it's a valid agent (has execute method)
        if not hasattr(agent, "execute") or not callable(agent.execute):
            raise ValueError(f"register() returned object without execute() method")

        return agent

    def get_plugin(self, name: str) -> Optional[dict]:
        return self.plugins.get(name)

    def list_plugins(self) -> list[dict]:
        return [
            {"name": n, **p["info"]}
            for n, p in self.plugins.items()
        ]

    def unload(self, name: str) -> bool:
        """Unload a plugin (remove from registry)."""
        if name in self.plugins:
            del self.plugins[name]
            logger.info(f"📦 Unloaded plugin: {name}")
            return True
        return False

    def _create_example_plugin(self, plugins_path: Path):
        """Create an example plugin for reference."""
        example = '''"""
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

        prompt = f"Translate the following to {target_lang}:\\n\\n{text}"
        if source_lang != "auto":
            prompt = f"Translate from {source_lang} to {target_lang}:\\n\\n{text}"

        result = await self.ask_llm(prompt, max_tokens=500)
        return self.ok(translation=result, source=source_lang, target=target_lang)


def register(event_bus, state):
    return TranslatorAgent("translator", event_bus, state)
'''
        (plugins_path / "example_translator.py").write_text(example, encoding="utf-8")
