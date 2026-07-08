#!/usr/bin/env python3
"""Test all AMRIT GODMODE brain upgrades — standalone (no LLM needed for most)."""
import traceback
import ast
import sys
import json
from pathlib import Path

PASS = 0
FAIL = 0

def _test_runner(name, func):
    global PASS, FAIL
    try:
        result = func()
        if result:
            print(f"  ✅ {name}")
            PASS += 1
        else:
            print(f"  ❌ {name} — returned False")
            FAIL += 1
    except Exception as e:
        print(f"  ❌ {name} — {e}")
        traceback.print_exc()
        FAIL += 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=== 1. Reasoning Engine ===")

def test_complexity_estimator():
    from reasoning_engine import estimate_complexity
    assert estimate_complexity("print hello") == "low"
    assert estimate_complexity("write a poem") == "low"
    assert estimate_complexity("implement a compiler from scratch with parser and tokenizer") == "high"
    assert estimate_complexity("build an API server with routes") == "medium"

def test_cache():
    from reasoning_engine import _cache_key, _CACHE
    k1 = _cache_key("hello world")
    k2 = _cache_key("hello world")
    k3 = _cache_key("different prompt")
    assert k1 == k2, "Same prompt should give same key"
    assert k1 != k3, "Different prompts should give different keys"

def test_strategies():
    from reasoning_engine import STRATEGIES
    assert len(STRATEGIES) >= 4, f"Only {len(STRATEGIES)} strategies"
    assert "direct" in STRATEGIES
    assert "decompose" in STRATEGIES

def test_reasoning_engine_init():
    from reasoning_engine import ReasoningEngine
    engine = ReasoningEngine()
    stats = engine.stats()
    assert "total" in stats
    assert "cache_hits" in stats
    assert "lessons_learned" in stats

_test_runner("Complexity estimator", test_complexity_estimator)
_test_runner("Cache key generation", test_cache)
_test_runner("Reasoning strategies", test_strategies)
_test_runner("ReasoningEngine init", test_reasoning_engine_init)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n=== 2. Debugger Agent (AST Analysis) ===")

def test_error_patterns():
    from debugger_agent import DebuggerAgent
    # We need a mock agent to test pattern matching
    class MockEB:
        async def start(self): pass
        async def stop(self): pass
        def subscribe(self, *a, **k): pass
        async def publish(self, *a, **k): pass
    class MockState:
        async def set(self, *a, **k): pass
        def get(self, *a, **k): return None
    d = DebuggerAgent(MockEB(), MockState())
    # Test pattern matching
    fix = d._match_error_pattern("NameError: name 'xyz' is not defined")
    assert "xyz" in fix, f"Expected 'xyz' in fix: {fix}"
    fix2 = d._match_error_pattern("ImportError: No module named 'requests'")
    assert "requests" in fix2
    fix3 = d._match_error_pattern("ZeroDivisionError: division by zero")
    assert "zero" in fix3.lower()

def test_ast_analysis():
    from debugger_agent import DebuggerAgent
    class MockEB:
        async def start(self): pass
        async def stop(self): pass
        def subscribe(self, *a, **k): pass
        async def publish(self, *a, **k): pass
    class MockState:
        async def set(self, *a, **k): pass
        def get(self, *a, **k): return None
    d = DebuggerAgent(MockEB(), MockState())
    code = '''
import os
import json

class MyClass:
    def long_method(self):
        x = 1
        y = 2
        z = 3
        for i in range(10):
            for j in range(10):
                pass
'''
    report = d._ast_analyze(code)
    assert "functions" in report
    assert "classes" in report
    assert "imports" in report
    assert len(report["imports"]) >= 2
    assert len(report["classes"]) >= 1

def test_syntax_validation():
    from debugger_agent import DebuggerAgent
    class MockEB:
        async def start(self): pass
        async def stop(self): pass
        def subscribe(self, *a, **k): pass
        async def publish(self, *a, **k): pass
    class MockState:
        async def set(self, *a, **k): pass
        def get(self, *a, **k): return None
    d = DebuggerAgent(MockEB(), MockState())
    assert d._validate_syntax("x = 1")["valid"]
    assert not d._validate_syntax("def f(:")["valid"]

_test_runner("Error pattern matching", test_error_patterns)
_test_runner("AST code analysis", test_ast_analysis)
_test_runner("Syntax validation", test_syntax_validation)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n=== 3. Memory Agent (Failure Patterns) ===")

def test_failure_db():
    from memory_agent import FailurePatternDB
    db = FailurePatternDB()
    db.record_failure(
        error="NameError: name 'test_var_xyz' is not defined",
        agent="coder",
        task="test task",
        fix="import test_var_xyz",
        worked=True,
    )
    fix = db.find_fix("NameError: name 'test_var_xyz' is not defined in test")
    assert "KNOWN" in fix, f"Expected KNOWN in fix: {fix}"
    stats = db.stats()
    assert stats["total_patterns"] > 0

_test_runner("Failure pattern DB", test_failure_db)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n=== 4. LLM Router (Caching + Stats) ===")

def test_llm_router_cache():
    from llm_router import LLMRouter
    r = LLMRouter()
    k1 = r._cache_key("test prompt", "system", "model")
    k2 = r._cache_key("test prompt", "system", "model")
    k3 = r._cache_key("different", "system", "model")
    assert k1 == k2
    assert k1 != k3

def test_llm_router_stats():
    from llm_router import LLMRouter
    r = LLMRouter()
    stats = r.get_stats()
    assert "total" in stats
    assert "cache_hits" in stats
    assert "cache_hit_rate" in stats
    assert "cache_size" in stats

_test_runner("LLM Router cache keys", test_llm_router_cache)
_test_runner("LLM Router stats", test_llm_router_stats)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n=== 5. Self-Evolution (Lessons) ===")

def test_self_evolution_lessons():
    from self_evolution import LESSONS_FILE
    # Just verify the constant exists
    assert isinstance(LESSONS_FILE, Path)

_test_runner("Self-evolution lessons file", test_self_evolution_lessons)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n=== 6. Goal Parser (New Patterns) ===")

def test_think_pattern():
    import asyncio
    from goal_parser import GoalParser
    gp = GoalParser()
    gp._use_llm = False
    tasks = asyncio.run(gp.parse("think about quantum computing"))
    assert len(tasks) >= 1
    assert tasks[0].get("agent") == "researcher"

def test_optimize_pattern():
    import asyncio
    from goal_parser import GoalParser
    gp = GoalParser()
    gp._use_llm = False
    tasks = asyncio.run(gp.parse("optimize main.py"))
    assert len(tasks) >= 1
    assert tasks[0].get("agent") == "debugger"

_test_runner("Think pattern", test_think_pattern)
_test_runner("Optimize pattern", test_optimize_pattern)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'='*50}")
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("ALL GOOD!" if FAIL == 0 else f"!!! {FAIL} FAILURES !!!")
print(f"{'='*50}")
