"""
DB Agent — Safe database migrations, schema design, query optimization.

Capabilities:
  - Design schemas (SQLAlchemy, Prisma, raw SQL)
  - Generate Alembic migrations with rollback
  - Dry-run migrations before applying
  - Query optimization suggestions
  - Seed data generation
  - SQLite / PostgreSQL / MySQL support
"""
import json
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent


class DBAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("DBAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "design")

        if action == "design":
            return await self._design_schema(d.get("description", ""), d.get("db", "sqlite"))
        if action == "migration":
            return await self._generate_migration(d.get("change", ""), d.get("safe", True))
        if action == "seed":
            return await self._generate_seed(d.get("model", ""), d.get("count", 10))
        if action == "optimize":
            return await self._optimize_query(d.get("query", ""))
        if action == "prisma":
            return await self._prisma_schema(d.get("description", ""))
        return await self._design_schema(task.get("name", ""), "sqlite")

    async def _design_schema(self, description: str, db: str) -> dict:
        prompt = f"""You are a database architect. Design a {db} schema for:
"{description}"

Generate:
1. SQLAlchemy 2.0 async models (Python)
2. Alembic migration script
3. Relationships and indexes
4. Sample queries

Rules:
- Always add: id (UUID), created_at, updated_at
- Index foreign keys
- Use proper constraints (NOT NULL, UNIQUE where appropriate)
- Include CASCADE rules for relationships

Return as JSON: {{"models": "python code", "migration": "alembic code", "indexes": []}}"""

        response = await self.ask_llm(prompt, max_tokens=3000)
        out = Path(f"workspace/db/schema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            import re
            m = re.search(r'\{[\s\S]*\}', response)
            data = json.loads(m.group()) if m else {}
            models_code = data.get("models", response)
        except Exception:
            models_code = response

        out.write_text(models_code)
        return self.ok(schema_path=str(out), description=description)

    async def _generate_migration(self, change: str, safe: bool = True) -> dict:
        prompt = f"""Generate a safe Alembic migration for this database change:
"{change}"

SAFETY RULES:
- Never DROP COLUMN without checking if data exists first
- Always provide upgrade() AND downgrade()
- For column additions: use server_default to avoid locking
- For renames: add new col → copy data → drop old (never direct rename)
- Add comments explaining why each change is safe

{'Include a dry-run check at the top that raises if production data would be lost.' if safe else ''}

Return ONLY the Python Alembic migration code."""

        code = await self.ask_llm(prompt, max_tokens=2000)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(f"workspace/db/migrations/{ts}_migration.py")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(migration_path=str(out), change=change, safe=safe)

    async def _generate_seed(self, model: str, count: int) -> dict:
        prompt = f"""Generate realistic seed data for the "{model}" database model.
Create {count} records with varied, realistic values (no Lorem ipsum).
Output as Python code using SQLAlchemy session.
Include: setup, data insertion, session.commit()."""

        code = await self.ask_llm(prompt, max_tokens=1500)
        out = Path(f"workspace/db/seeds/seed_{model.lower()}.py")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(seed_path=str(out), model=model, count=count)

    async def _optimize_query(self, query: str) -> dict:
        prompt = f"""Analyze and optimize this SQL query:
```sql
{query}
```
Provide:
1. Issues found (N+1, missing indexes, full table scans)
2. Optimized version
3. Recommended indexes to add
4. Expected performance improvement"""

        analysis = await self.ask_llm(prompt, max_tokens=1500)
        return self.ok(original=query, analysis=analysis)

    async def _prisma_schema(self, description: str) -> dict:
        prompt = f"""Generate a complete Prisma schema for:
"{description}"

Include:
- All models with proper relations
- @id, @unique, @index decorators
- Enums where appropriate
- @@map for snake_case table names

Return ONLY the schema.prisma file content."""

        schema = await self.ask_llm(prompt, max_tokens=2000)
        out = Path("workspace/db/schema.prisma")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(schema)
        return self.ok(path=str(out))
