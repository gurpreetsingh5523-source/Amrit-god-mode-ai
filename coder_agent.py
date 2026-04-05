"""Coder Agent — Multi-language code generation, fixing, refactoring."""
import re
from pathlib import Path
from base_agent import BaseAgent

class CoderAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("CoderAgent", eb, state)
        Path("workspace").mkdir(exist_ok=True)

    async def execute(self, task: dict) -> dict:
        d      = task.get("data", {})
        action = d.get("action", "generate")
        await self.report(f"Coder [{action}]")
        if action == "generate": return await self._gen(d)
        if action == "fix":      return await self._fix(d)
        if action == "refactor": return await self._refactor(d)
        if action == "explain":  return await self._explain(d)
        if action == "review":   return await self._review(d)
        return await self._gen(d)

    async def _gen(self, d: dict) -> dict:
        lang = d.get("language", "python")
        spec = d.get("spec") or d.get("goal") or d.get("name", "")
        goal = d.get("goal", spec)
        fn   = d.get("filename", "")
        # Try to extract target filename from spec/goal (e.g. "sandman_face.py")
        if not fn:
            m = re.search(r'(\w+\.py)\b', spec)
            if m:
                fn = m.group(1)
        # If target file already exists, read it and extend/improve
        existing_code = ""
        if fn:
            existing_path = Path("workspace") / fn
            if existing_path.exists():
                existing_code = existing_path.read_text()
        if existing_code:
            prompt = (
                f"You are building: {goal}\n"
                f"Current task: {spec}\n\n"
                f"Here is the EXISTING code in {fn}:\n```{lang}\n{existing_code}\n```\n\n"
                f"Extend and improve this code to fulfill the task. "
                f"Return the COMPLETE updated file with ALL existing functionality preserved plus the new features. "
                f"Return ONLY code, no explanations."
            )
        else:
            prompt = (
                f"You are building: {goal}\n"
                f"Current task: {spec}\n\n"
                f"Write a COMPLETE, working {lang} file that implements this.\n"
                f"Requirements:\n"
                f"- The code must be runnable as-is with `python3 {fn or 'app.py'}`\n"
                f"- Include all imports at the top\n"
                f"- Include a main() function and if __name__ == '__main__': main()\n"
                f"- Handle errors gracefully\n"
                f"- Return ONLY code, no explanations."
            )
        code = await self.ask_llm(prompt)
        code = self._strip(code, lang)
        # Determine output file
        if not fn and spec:
            safe = re.sub(r'[^a-zA-Z0-9_]', '_', spec.lower())[:40].strip('_')
            fn = f"{safe}.py" if lang == "python" else f"{safe}.{lang}"
        if fn:
            p = Path("workspace") / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code)
            await self.report(f"Saved: workspace/{fn} ({len(code.splitlines())} lines)")
        return self.ok(code=code, language=lang, filename=fn, lines=len(code.splitlines()))

    async def _fix(self, d: dict) -> dict:
        code, err = d.get("code",""), d.get("error","")
        fixed = await self.ask_llm(f"Fix this code (error: {err}):\n{code}\nReturn only fixed code.")
        return self.ok(code=self._strip(fixed), fixed_error=err)

    async def _refactor(self, d: dict) -> dict:
        goal = d.get("goal", "improve readability")
        instructions = d.get("error", "")  # self_evolution passes instructions via 'error'
        category = d.get("category", "refactor")
        # Use qwen2.5-coder for refactoring if available, else fall back
        from llm_router import LLMRouter
        router = LLMRouter()
        model = router._pick_model_for_category(category)  # picks from MODEL_REGISTRY["refactor"]
        prompt = (
            f"{instructions}\n\nCode to refactor:\n```python\n{d.get('code', '')}\n```\n"
            "Return ONLY valid Python code inside a single ```python code block. "
            "No explanations, no markdown outside the code block."
        ) if instructions else (
            f"Refactor to {goal}:\n```python\n{d.get('code', '')}\n```\n"
            "Return only valid Python code in a ```python block."
        )
        # Call router.complete() directly — bypasses ask_llm summarization which destroys code
        code = await router.complete(
            prompt,
            system="You are a Python refactoring expert. Output ONLY valid Python code. Never include explanations outside code blocks.",
            model=model, max_tokens=4000,
        )
        return self.ok(code=self._strip(code))

    async def _explain(self, d: dict) -> dict:
        exp = await self.ask_llm(f"Explain this code simply:\n{d.get('code','')}")
        return self.ok(explanation=exp)

    async def _review(self, d: dict) -> dict:
        review = await self.ask_llm(
            f"Code review — find bugs, security issues, improvements:\n{d.get('code','')}")
        return self.ok(review=review)

    def _strip(self, text: str, lang: str = "") -> str:
        if not isinstance(text, str):
            return ""
        # Match ```python\n...``` or ```\n...``` — discard language identifier
        m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        code = m.group(1).strip() if m else text.strip()
        # If there are multiple fenced blocks, join them all
        if not m:
            blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
            if blocks:
                code = "\n\n".join(b.strip() for b in blocks)
        # Strip leading prose lines before first def/class/import/from/#
        lines = code.split("\n")
        start = 0
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped and (stripped[0] in ('#',) or
                            stripped.startswith(('def ', 'async def ', 'class ',
                                                 'import ', 'from ', '@'))):
                start = i
                break
        if start > 0:
            code = "\n".join(lines[start:])
        return code
