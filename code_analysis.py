"""Code Analysis — AST-based static analysis, complexity metrics, issue detection."""
import ast
import re
import sys
from pathlib import Path


class CodeAnalyzer:
 """Static code analyser for Python source files and strings."""

 # ------------------------------------------------------------------ #
 # Public API               #
 # ------------------------------------------------------------------ #

 def analyze(self, code: str) -> dict:
  """Full analysis: metrics + issues."""
  metrics = self.metrics(code)
  issues = self._detect_issues(code, metrics)
  return {
   "metrics": metrics,
   "issues": issues,
   "summary": {
    "functions": metrics["functions"],
    "classes": metrics["classes"],
    "lines": metrics["lines"],
    "issue_count": len(issues),
   },
  }

 def syntax_check(self, code: str) -> dict:
  """Check Python syntax. Returns {valid, error, line}."""
  if not code or not code.strip():
   return {"valid": False, "error": "Empty code", "line": 0}
  try:
   ast.parse(code)
   return {"valid": True, "error": None, "line": None}
  except SyntaxError as e:
   return {"valid": False, "error": e.msg, "line": e.lineno or 0}

 def metrics(self, code: str) -> dict:
  """Extract structural metrics from Python source."""
  lines = code.split("\n")
  blank = sum(1 for ln in lines if not ln.strip())
  comments = sum(1 for ln in lines if ln.strip().startswith("#"))

  try:
   tree = ast.parse(code)
  except SyntaxError:
   return {
    "lines": len(lines), "blank": blank, "comments": comments,
    "functions": 0, "classes": 0, "imports": 0,
    "max_depth": 0, "complexity": 0,
   }

  funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
  classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
  imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

  return {
   "lines": len(lines),
   "blank": blank,
   "comments": comments,
   "functions": len(funcs),
   "classes": len(classes),
   "imports": len(imports),
   "max_depth": self._max_nesting(tree),
   "complexity": self._cyclomatic(tree),
  }

 def analyze_file(self, path: str) -> dict:
  """Analyze a Python file by path."""
  p = Path(path)
  if not p.exists():
   return {"error": f"File not found: {path}"}
  code = p.read_text(errors="replace")
  result = self.analyze(code)
  result["file"] = str(p)
  return result

 def list_functions(self, code: str) -> list[dict]:
  """List all functions/methods with line numbers and arg counts."""
  try:
   tree = ast.parse(code)
  except SyntaxError:
   return []
  result = []
  for node in ast.walk(tree):
   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
    result.append({
     "name": node.name,
     "line": node.lineno,
     "args": len(node.args.args),
     "is_async": isinstance(node, ast.AsyncFunctionDef),
     "decorators": [self._decorator_name(d) for d in node.decorator_list],
     "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
    })
  return result

 def list_classes(self, code: str) -> list[dict]:
  """List all classes with line numbers and method counts."""
  try:
   tree = ast.parse(code)
  except SyntaxError:
   return []
  result = []
  for node in ast.walk(tree):
   if isinstance(node, ast.ClassDef):
    methods = [n for n in ast.iter_child_nodes(node)
       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    bases = [self._name_of(b) for b in node.bases]
    result.append({
     "name": node.name,
     "line": node.lineno,
     "methods": len(methods),
     "bases": bases,
    })
  return result

 def dependency_list(self, code: str) -> list[str]:
  """Extract imported module names."""
  try:
   tree = ast.parse(code)
  except SyntaxError:
   return []
  deps = set()
  for node in ast.walk(tree):
   if isinstance(node, ast.Import):
    for alias in node.names:
     deps.add(alias.name.split(".")[0])
   elif isinstance(node, ast.ImportFrom) and node.module:
    deps.add(node.module.split(".")[0])
  return sorted(deps)

 # ------------------------------------------------------------------ #
 # Issue detection              #
 # ------------------------------------------------------------------ #

 def _detect_issues(self, code: str, metrics: dict) -> list[dict]:
  issues = []

  # Long functions (> 50 lines)
  try:
   tree = ast.parse(code)
  except SyntaxError:
   issues.append({"type": "syntax_error", "severity": "high", "msg": "Code has syntax errors"})
   return issues

  for node in ast.walk(tree):
   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
    length = (node.end_lineno or node.lineno) - node.lineno + 1
    if length > 50:
     issues.append({
      "type": "long_function", "severity": "medium",
      "msg": f"Function '{node.name}' is {length} lines (>50)",
      "line": node.lineno,
     })
    # Too many args (> 6)
    if len(node.args.args) > 6:
     issues.append({
      "type": "too_many_args", "severity": "low",
      "msg": f"Function '{node.name}' has {len(node.args.args)} args (>6)",
      "line": node.lineno,
     })

  # Deep nesting
  if metrics.get("max_depth", 0) > 5:
   issues.append({
    "type": "deep_nesting", "severity": "medium",
    "msg": f"Max nesting depth is {metrics['max_depth']} (>5)",
   })

  # High cyclomatic complexity
  if metrics.get("complexity", 0) > 20:
   issues.append({
    "type": "high_complexity", "severity": "medium",
    "msg": f"Cyclomatic complexity is {metrics['complexity']} (>20)",
   })

  # Bare except
  for node in ast.walk(tree):
   if isinstance(node, ast.ExceptHandler) and node.type is None:
    issues.append({
     "type": "bare_except", "severity": "high",
     "msg": f"Bare 'except:' at line {node.lineno} — catches all exceptions",
     "line": node.lineno,
    })

  # Global statements
  for node in ast.walk(tree):
   if isinstance(node, ast.Global):
    issues.append({
     "type": "global_usage", "severity": "low",
     "msg": f"'global' statement at line {node.lineno}",
     "line": node.lineno,
    })

  # TODO/FIXME/HACK comments
  for i, line in enumerate(code.split("\n"), 1):
   stripped = line.strip()
   if stripped.startswith("#"):
    upper = stripped.upper()
    for tag in ("TODO", "FIXME", "HACK", "XXX"):
     if tag in upper:
      issues.append({
       "type": "todo_comment", "severity": "info",
       "msg": f"{tag} comment at line {i}",
       "line": i,
      })
      break

  return issues

 # ------------------------------------------------------------------ #
 # Complexity helpers             #
 # ------------------------------------------------------------------ #

 @staticmethod
 def _cyclomatic(tree: ast.AST) -> int:
  """Approximate cyclomatic complexity (branches + 1)."""
  branches = 0
  for node in ast.walk(tree):
   if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor,
         ast.ExceptHandler, ast.With, ast.AsyncWith)):
    branches += 1
   elif isinstance(node, ast.BoolOp):
    branches += len(node.values) - 1
  return branches + 1

 @staticmethod
 def _max_nesting(tree: ast.AST) -> int:
  """Calculate maximum nesting depth."""
  def _depth(node, level=0):
   max_d = level
   for child in ast.iter_child_nodes(node):
    if isinstance(child, (ast.If, ast.For, ast.While, ast.AsyncFor,
          ast.With, ast.AsyncWith, ast.Try,
          ast.FunctionDef, ast.AsyncFunctionDef,
          ast.ClassDef)):
     max_d = max(max_d, _depth(child, level + 1))
    else:
     max_d = max(max_d, _depth(child, level))
   return max_d
  return _depth(tree)

 @staticmethod
 def _decorator_name(node: ast.expr) -> str:
  if isinstance(node, ast.Name):
   return node.id
  if isinstance(node, ast.Attribute):
   return node.attr
  return "?"

 @staticmethod
 def _name_of(node: ast.expr) -> str:
  if isinstance(node, ast.Name):
   return node.id
  if isinstance(node, ast.Attribute):
   return node.attr
  return "?"


# Keep backward compat with existing test
def greet(name: str) -> str:
 return f"Hello, {name}!"