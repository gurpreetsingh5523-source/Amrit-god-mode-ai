"""Code Safety — Pre-execution safety analysis for generated code."""
import re
import ast
from logger import setup_logger
logger = setup_logger("CodeSafety")

DANGEROUS_IMPORTS = ["os","subprocess","sys","shutil","socket","ctypes","importlib"]
DANGEROUS_CALLS   = ["eval","exec","__import__","open","os.system","subprocess.run"]

class CodeSafety:
    def analyze(self, code: str) -> dict:
        issues = []
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return {"safe":False,"issues":[{"type":"syntax","msg":str(e)}]}
        # Check dangerous imports
        imports = re.findall(r"^(?:import|from)\s+(\w+)", code, re.M)
        for imp in imports:
            if imp in DANGEROUS_IMPORTS:
                issues.append({"type":"dangerous_import","module":imp,"severity":"warning"})
        # Check dangerous calls
        for call in DANGEROUS_CALLS:
            if call+"(" in code:
                issues.append({"type":"dangerous_call","call":call,"severity":"warning"})
        # Check for hardcoded secrets
        if re.search(r'(password|api_key|secret)\s*=\s*["\'][^"\']{{8,}}', code, re.I):
            issues.append({"type":"hardcoded_secret","severity":"critical"})

        critical = [i for i in issues if i.get("severity")=="critical"]
        return {"safe":len(critical)==0,"issues":issues,"critical_count":len(critical)}

    def sanitize(self, code: str) -> str:
        """Remove or comment out the most dangerous lines."""
        lines = code.splitlines()
        safe_lines = []
        for line in lines:
            if any(d+"(" in line for d in ["eval","exec"]):
                safe_lines.append(f"# REMOVED (unsafe): {line}")
            else:
                safe_lines.append(line)
        return "\n".join(safe_lines)
