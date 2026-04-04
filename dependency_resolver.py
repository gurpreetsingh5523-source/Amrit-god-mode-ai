"""Dependency Resolver — Detects and resolves task dependency chains."""
from collections import defaultdict, deque
from logger import setup_logger
logger = setup_logger("DependencyResolver")

class DependencyResolver:
    def topological_sort(self, tasks: list) -> list:
        in_deg = defaultdict(int)
        name_map = {t["name"]: t for t in tasks}
        for t in tasks:
            for dep in t.get("depends_on", []):
                in_deg[t["name"]] += 1
        queue = deque([t for t in tasks if in_deg[t["name"]] == 0])
        result = []
        while queue:
            t = queue.popleft(); result.append(t)
            for other in tasks:
                if t["name"] in other.get("depends_on", []):
                    in_deg[other["name"]] -= 1
                    if in_deg[other["name"]] == 0: queue.append(other)
        return result if len(result) == len(tasks) else tasks

    def detect_cycles(self, tasks: list) -> list:
        visited, cycles = set(), []
        def dfs(name, path):
            if name in path: cycles.append(list(path) + [name]); return
            if name in visited: return
            visited.add(name); path.add(name)
            for t in tasks:
                if t["name"] == name:
                    for dep in t.get("depends_on", []): dfs(dep, path)
            path.discard(name)
        for t in tasks: dfs(t["name"], set())
        return cycles

    def resolve(self, tasks: list) -> list:
        cycles = self.detect_cycles(tasks)
        if cycles:
            logger.warning(f"Cycles found: {cycles}")
            for t in tasks:
                t["depends_on"] = [d for d in t.get("depends_on",[]) if not any(d in c for c in cycles)]
        return self.topological_sort(tasks)
