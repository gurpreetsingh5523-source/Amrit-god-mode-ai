import json
from pathlib import Path

class ToolBoxPersistence:
    """Handles saving and loading dynamically created tools for ToolBox."""
    def __init__(self, persist_path="workspace/dynamic_tools.json"):
        self.persist_path = Path(persist_path)
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

    def save_tools(self, tools: dict):
        # Only save tool names and descriptions for recreate
        data = {name: getattr(func, "_toolbox_description", "") for name, func in tools.items()}
        self.persist_path.write_text(json.dumps(data, indent=2))

    def load_tools(self):
        if not self.persist_path.exists():
            return {}
        data = json.loads(self.persist_path.read_text())
        return data
