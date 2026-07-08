"""
Swift Agent — iOS/macOS native app development.

Capabilities:
  - Scaffold SwiftUI apps (iOS 17+, macOS 14+)
  - Generate views, models, ViewModels (MVVM)
  - CoreData / SwiftData schemas
  - Xcode project structure
  - Swift Package Manager setup
  - Build via xcodebuild automation
"""
import subprocess
from pathlib import Path
from base_agent import BaseAgent

SWIFT_PROMPT = """You are an expert Swift/SwiftUI developer targeting iOS 17+ and macOS 14+.
Always use:
- SwiftUI for all UI (no UIKit unless specifically needed)
- @Observable macro (Swift 5.9+) instead of ObservableObject
- SwiftData for persistence (not CoreData unless asked)
- async/await for all async operations
- Structured concurrency (TaskGroup, async let)
- Modern Swift patterns: if let shorthand, guard, result builders
"""


class SwiftAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("SwiftAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "scaffold")

        if action == "scaffold":
            return await self._scaffold(d.get("name", "MyApp"), d.get("description", ""))
        if action == "view":
            return await self._view(d.get("name", ""), d.get("description", ""))
        if action == "model":
            return await self._model(d.get("name", ""), d.get("fields", {}))
        if action == "build":
            return await self._build(d.get("project_path", ""))
        return await self._scaffold(task.get("name", "MyApp"), task.get("name", ""))

    async def _scaffold(self, name: str, description: str) -> dict:
        out = Path(f"workspace/{name}")
        out.mkdir(parents=True, exist_ok=True)

        prompt = f"""{SWIFT_PROMPT}

Scaffold a complete SwiftUI app: "{name}"
Description: {description}

Generate these files as JSON:
{{
  "files": {{
    "{name}App.swift": "...",
    "ContentView.swift": "...",
    "Models/{name}Model.swift": "...",
    "Views/HomeView.swift": "...",
    "Package.swift": "..."
  }}
}}

Make a real, working app with navigation, list view, detail view, and data model."""

        response = await self.ask_llm(prompt, max_tokens=3000)
        files_written = []
        try:
            import re, json
            m = re.search(r'\{[\s\S]*\}', response)
            if m:
                data = json.loads(m.group())
                for fname, content in data.get("files", {}).items():
                    fp = out / fname
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(str(content))
                    files_written.append(str(fp))
        except Exception:
            (out / "generated.swift").write_text(response)
            files_written = [str(out / "generated.swift")]

        return self.ok(app=name, path=str(out), files=files_written)

    async def _view(self, name: str, description: str) -> dict:
        prompt = f"""{SWIFT_PROMPT}
Generate a SwiftUI View called {name}View.
Description: {description}
Requirements: proper previews, @Binding/@State where needed, accessibility labels.
Return ONLY Swift code."""
        code = await self.ask_llm(prompt, max_tokens=1500)
        out = Path(f"workspace/swift/Views/{name}View.swift")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(view=name, path=str(out))

    async def _model(self, name: str, fields: dict) -> dict:
        prompt = f"""{SWIFT_PROMPT}
Generate a SwiftData @Model class for: {name}
Fields: {fields}
Include: init, computed properties, static preview data.
Return ONLY Swift code."""
        code = await self.ask_llm(prompt, max_tokens=1000)
        out = Path(f"workspace/swift/Models/{name}.swift")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(model=name, path=str(out))

    async def _build(self, project_path: str) -> dict:
        """Run xcodebuild on a project."""
        try:
            result = subprocess.run(
                ["xcodebuild", "-project", project_path, "-scheme",
                 Path(project_path).stem, "build"],
                capture_output=True, text=True, timeout=120
            )
            return self.ok(
                success=result.returncode == 0,
                output=result.stdout[-1000:],
                errors=result.stderr[-500:]
            )
        except FileNotFoundError:
            return self.err("xcodebuild not found — install Xcode from App Store")
        except Exception as e:
            return self.err(str(e))
