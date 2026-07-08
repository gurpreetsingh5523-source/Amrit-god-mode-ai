"""
FullStack Agent — React/Next.js, FastAPI, full-stack project builder.

Capabilities:
  - Scaffold complete Next.js / React projects with proper file structure
  - Generate FastAPI backends with models, routes, auth
  - Wire frontend ↔ backend (API calls, types shared)
  - TailwindCSS + shadcn/ui components
  - Docker + deployment configs
  - Multi-file project awareness (uses 262K context of qwen3.5:9b)
"""
import asyncio
import json
from pathlib import Path
from base_agent import BaseAgent


# shadcn/ui + Tailwind design system knowledge
DESIGN_SYSTEM_PROMPT = """
You are an expert full-stack engineer. Use these conventions always:
- Frontend: Next.js 14+ App Router, TypeScript, TailwindCSS, shadcn/ui components
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0, async/await
- State: Zustand for client state, React Query for server state
- Styling: Tailwind utility classes, shadcn/ui for components (Button, Card, Input, etc.)
- File structure: feature-based, not layer-based
- Always generate: types/interfaces, error boundaries, loading states
- API: RESTful with proper HTTP status codes, typed responses
"""

NEXTJS_TEMPLATE = {
    "structure": [
        "app/",
        "app/layout.tsx",
        "app/page.tsx",
        "app/globals.css",
        "components/ui/",
        "lib/utils.ts",
        "lib/api.ts",
        "types/index.ts",
        "public/",
        "package.json",
        "tailwind.config.ts",
        "tsconfig.json",
        "next.config.ts",
    ],
    "package_json": {
        "dependencies": {
            "next": "^14.0.0",
            "react": "^18.0.0",
            "react-dom": "^18.0.0",
            "@radix-ui/react-slot": "^1.0.0",
            "class-variance-authority": "^0.7.0",
            "clsx": "^2.0.0",
            "tailwind-merge": "^2.0.0",
            "lucide-react": "^0.300.0",
            "zustand": "^4.4.0",
            "@tanstack/react-query": "^5.0.0",
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "tailwindcss": "^3.3.0",
            "autoprefixer": "^10.0.0",
            "postcss": "^8.0.0",
            "@types/node": "^20.0.0",
            "@types/react": "^18.0.0",
        }
    }
}


class FullStackAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("FullStackAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "scaffold")

        if action == "scaffold":
            return await self._scaffold_project(
                d.get("name", "my-app"),
                d.get("description", ""),
                d.get("type", "nextjs"),     # nextjs | fastapi | fullstack
                d.get("features", [])
            )
        if action == "component":
            return await self._generate_component(
                d.get("name", ""),
                d.get("description", ""),
                d.get("props", {})
            )
        if action == "api_route":
            return await self._generate_api_route(
                d.get("resource", ""),
                d.get("operations", ["list", "create", "get", "update", "delete"])
            )
        if action == "page":
            return await self._generate_page(
                d.get("name", ""),
                d.get("description", "")
            )
        if action == "fullstack":
            return await self._build_fullstack(
                d.get("spec", task.get("name", ""))
            )
        return await self._build_fullstack(task.get("name", ""))

    async def _scaffold_project(self, name: str, description: str,
                                 project_type: str, features: list) -> dict:
        """Generate complete project scaffold with all files."""
        await self.report(f"Scaffolding {project_type} project: {name!r}")

        out_dir = Path(f"workspace/{name}")
        out_dir.mkdir(parents=True, exist_ok=True)

        prompt = f"""{DESIGN_SYSTEM_PROMPT}

Generate a complete {project_type} project called "{name}".
Description: {description}
Features needed: {', '.join(features) if features else 'standard CRUD app'}

Output a JSON object with this structure:
{{
  "files": {{
    "filename": "file content as string",
    ...
  }},
  "setup_commands": ["npm install", "npm run dev"],
  "description": "what was built"
}}

Generate REAL, working code. Include:
- Complete package.json
- app/layout.tsx with Tailwind + font setup
- app/page.tsx with a proper landing page using shadcn/ui
- components/ui/button.tsx (shadcn Button component)
- lib/utils.ts (cn helper)
- tailwind.config.ts
- tsconfig.json
- README.md with setup instructions

Make it production-ready and beautiful."""

        response = await self.ask_llm(prompt, max_tokens=4000)

        # Parse JSON from response
        files_written = []
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                files = data.get("files", {})
                for filename, content in files.items():
                    filepath = out_dir / filename
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath.write_text(str(content))
                    files_written.append(str(filepath))
        except Exception:
            # Fallback: save raw response
            (out_dir / "generated_code.txt").write_text(response)
            files_written = [str(out_dir / "generated_code.txt")]

        # Always write package.json if missing
        pkg_path = out_dir / "package.json"
        if not pkg_path.exists():
            pkg = dict(NEXTJS_TEMPLATE["package_json"])
            pkg["name"] = name
            pkg["version"] = "0.1.0"
            pkg["scripts"] = {"dev": "next dev", "build": "next build", "start": "next start"}
            pkg_path.write_text(json.dumps(pkg, indent=2))
            files_written.append(str(pkg_path))

        return self.ok(
            project=name,
            type=project_type,
            output_dir=str(out_dir),
            files_written=len(files_written),
            files=files_written[:10],
            next_steps=[f"cd workspace/{name}", "npm install", "npm run dev"]
        )

    async def _generate_component(self, name: str, description: str, props: dict) -> dict:
        """Generate a single React component."""
        prompt = f"""{DESIGN_SYSTEM_PROMPT}

Generate a TypeScript React component called "{name}".
Description: {description}
Props: {json.dumps(props) if props else 'infer from description'}

Requirements:
- Use shadcn/ui primitives where appropriate
- TailwindCSS for styling
- TypeScript with proper prop types
- Export default + named export
- Include usage example in a comment

Return ONLY the TypeScript code, no explanation."""

        code = await self.ask_llm(prompt, max_tokens=2000)
        out_path = Path(f"workspace/components/{name}.tsx")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(code)
        return self.ok(component=name, path=str(out_path), code=code[:500])

    async def _generate_api_route(self, resource: str, operations: list) -> dict:
        """Generate FastAPI route for a resource."""
        prompt = f"""{DESIGN_SYSTEM_PROMPT}

Generate a complete FastAPI router for the "{resource}" resource.
Operations needed: {', '.join(operations)}

Include:
- Pydantic v2 models (Create, Update, Response schemas)
- SQLAlchemy 2.0 async ORM model
- Full CRUD endpoints with proper HTTP codes
- Input validation
- Type hints throughout
- Dependency injection for DB session

Return ONLY Python code."""

        code = await self.ask_llm(prompt, max_tokens=2500)
        out_path = Path(f"workspace/api/routes/{resource.lower()}.py")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(code)
        return self.ok(resource=resource, path=str(out_path))

    async def _generate_page(self, name: str, description: str) -> dict:
        """Generate a Next.js page with full UI."""
        prompt = f"""{DESIGN_SYSTEM_PROMPT}

Generate a Next.js 14 App Router page for: "{description}"
Page name/route: {name}

Requirements:
- TypeScript
- Server component by default, 'use client' only where needed
- shadcn/ui components for all UI elements
- TailwindCSS styling — make it visually beautiful
- Loading and error states
- Responsive design (mobile-first)
- Realistic, production-quality content

Return ONLY the TypeScript/TSX code."""

        code = await self.ask_llm(prompt, max_tokens=2500)
        out_path = Path(f"workspace/pages/{name}.tsx")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(code)
        return self.ok(page=name, path=str(out_path))

    async def _build_fullstack(self, spec: str) -> dict:
        """Build a complete fullstack app from a natural language spec."""
        await self.report(f"Building fullstack app: {spec[:60]!r}")

        # Step 1: Plan the architecture
        plan_prompt = f"""You are a senior full-stack architect.

Project spec: "{spec}"

Create a detailed technical plan as JSON:
{{
  "project_name": "kebab-case-name",
  "description": "what this builds",
  "frontend": {{
    "framework": "Next.js 14",
    "pages": ["page1: description", "page2: description"],
    "key_components": ["component descriptions"]
  }},
  "backend": {{
    "framework": "FastAPI",
    "models": ["model: fields"],
    "endpoints": ["METHOD /path: description"]
  }},
  "features": ["feature list"]
}}"""

        plan_response = await self.ask_llm(plan_prompt, max_tokens=1500)

        try:
            import re
            match = re.search(r'\{[\s\S]*\}', plan_response)
            plan = json.loads(match.group()) if match else {}
        except Exception:
            plan = {"project_name": "generated-app", "description": spec}

        project_name = plan.get("project_name", "generated-app")
        features = plan.get("features", [])

        # Step 2: Scaffold the project
        result = await self._scaffold_project(
            project_name, spec, "fullstack", features
        )

        return self.ok(
            spec=spec,
            plan=plan,
            project=project_name,
            output_dir=result.get("output_dir"),
            files_written=result.get("files_written", 0)
        )
