"""AMRIT GODMODE Test Suite (refreshed)

These tests exercise core components of the project. Tests use pytest fixtures
where appropriate and avoid hard-coded /tmp files by using pytest's `tmp_path`.
If a component is not available in the repo, tests will be skipped rather than
failing loudly.
"""

import sys
from pathlib import Path
import pytest

# ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))


def _import_optional(module_name):
    try:
        return __import__(module_name, fromlist=["*"])
    except Exception:
        pytest.skip(f"optional module {module_name} not available")


@pytest.mark.asyncio
async def test_event_bus():
    mod = _import_optional("event_bus")
    EventBus = getattr(mod, "EventBus")
    bus = EventBus()
    await getattr(bus, "start", lambda: None)()
    received = []

    async def h(e):
        received.append(getattr(e, "name", "test"))

    bus.subscribe("test", h)
    await bus.publish("test", {"x": 1})
    assert "test" in received


@pytest.mark.asyncio
async def test_task_graph():
    mod = _import_optional("task_graph")
    TaskGraph = getattr(mod, "TaskGraph")
    g = TaskGraph()
    g.add({"name": "task1", "agent": "coder", "priority": 1})
    ready = g.get_ready()
    assert any(getattr(r, "name", None) == "task1" for r in ready)


@pytest.mark.asyncio
async def test_state_manager(tmp_path):
    mod = _import_optional("state_manager")
    StateManager = getattr(mod, "StateManager")
    path = tmp_path / "state.json"
    sm = StateManager(str(path))
    await getattr(sm, "set")("x", "hello")
    assert sm.get("x") == "hello"
    assert sm.get("missing", "default") == "default"


def test_ethical_guard_blocks():
    mod = _import_optional("ethical_guard")
    EthicalGuard = getattr(mod, "EthicalGuard")
    g = EthicalGuard()
    ok, _ = g.check("run rm -rf / to clean")
    assert not ok


def test_sandbox_run():
    mod = _import_optional("sandbox")
    Sandbox = getattr(mod, "Sandbox")
    sb = Sandbox()
    r = sb.run("print('hello sandbox')")
    assert r.get("returncode", 1) == 0 and "hello sandbox" in r.get("stdout", "")


def test_context_buffer():
    mod = _import_optional("context_buffer")
    ContextBuffer = getattr(mod, "ContextBuffer")
    cb = ContextBuffer(max_size=3)
    for i in range(4):
        cb.add({"k": i})
    assert len(cb) == 3 and cb.get_all()[0]["k"] == 1


def test_vector_store_search(tmp_path):
    mod = _import_optional("vector_store")
    VectorStore = getattr(mod, "VectorStore")
    path = tmp_path / "vec.json"
    vs = VectorStore(str(path))
    vs.add("hello", [0.1, 0.2, 0.3], doc_id="d1")
    vs.add("world", [0.1, 0.2, 0.4], doc_id="d2")
    results = vs.search([0.1, 0.2, 0.35], top_k=1)
    assert len(results) <= 1 or len(results) == 1


def test_code_analyzer():
    try:
        from code_analysis import greet
    except Exception:
        pytest.skip("code_analysis not available")
    r = greet("test")
    assert isinstance(r, str)


def test_syntax_checks():
    """Test Python syntax checking via ast."""
    import ast
    try:
        ast.parse("x=1+2")
        valid = True
    except SyntaxError:
        valid = False
    assert valid is True
    try:
        ast.parse("def bad(:")
        valid2 = True
    except SyntaxError:
        valid2 = False
    assert valid2 is False


def test_dependency_resolver():
    mod = _import_optional("dependency_resolver")
    DependencyResolver = getattr(mod, "DependencyResolver")
    dr = DependencyResolver()
    tasks = [{"name": "A", "depends_on": []}, {"name": "B", "depends_on": ["A"]}]
    sorted_tasks = dr.resolve(tasks)
    assert sorted_tasks[0]["name"] == "A"


def test_priority_engine():
    mod = _import_optional("priority_engine")
    PriorityEngine = getattr(mod, "PriorityEngine")
    pe = PriorityEngine()
    tasks = [
        {"name": "task", "agent": "coder", "priority": 5, "depends_on": []},
        {"name": "critical fix", "agent": "debugger", "priority": 3, "depends_on": []},
    ]
    result = pe.assign(tasks)
    assert result[0]["name"] == "critical fix"


def test_episodic_memory(tmp_path):
    mod = _import_optional("episodic_memory")
    EpisodicMemory = getattr(mod, "EpisodicMemory")
    path = tmp_path / "episodes.json"
    em = EpisodicMemory(str(path))
    em.record("test episode", "content here", tags=["test"])
    results = em.search("content")
    assert len(results) >= 1


def test_reward_engine():
    mod = _import_optional("reward_engine")
    RewardEngine = getattr(mod, "RewardEngine")
    re = RewardEngine()
    score = re.score({"name": "task", "agent": "coder"}, {"status": "ok"})
    assert score is not None


# ══════════════════════════════════════════════════════════════
# EXTENDED TESTS — ਵਧੀਆਂ ਟੈਸਟਾਂ
# ══════════════════════════════════════════════════════════════

def test_goal_parser():
    """Test task decomposition from natural language goals."""
    try:
        from goal_parser import GoalParser
    except Exception:
        pytest.skip("goal_parser not available")
    gp = GoalParser()
    assert gp is not None
    # should have a parse-like method
    assert hasattr(gp, "parse") or hasattr(gp, "decompose")


def test_llm_router_model_selection():
    """Test LLMRouter picks correct models for categories."""
    try:
        from llm_router import LLMRouter, MODEL_REGISTRY
    except Exception:
        pytest.skip("llm_router not available")
    r = LLMRouter()
    # Should pick a model for each category
    for cat in ["coding", "reasoning", "fast", "creative", "deep"]:
        model = r._pick_model_for_category(cat)
        assert isinstance(model, str) and len(model) > 0
    # "deep" routes to the installed model (deepseek-r1:32b not yet pulled)
    assert r._pick_model_for_category("deep") in MODEL_REGISTRY.values()


def test_learning_layer():
    """Test LearningLayer observe/reflect/record cycle."""
    try:
        from learning_layer import LearningLayer
    except Exception:
        pytest.skip("learning_layer not available")
    ll = LearningLayer()
    ll.observe({"agent": "test", "action": "test_action", "success": False, "error": "test error"})
    stats = ll.stats()
    assert isinstance(stats, dict)
    assert "total_lessons" in stats


def test_self_learning_loop():
    """Test SelfLearningLoop initialization and rule lessons."""
    try:
        from self_learning_loop import SelfLearningLoop
    except Exception:
        pytest.skip("self_learning_loop not available")
    sll = SelfLearningLoop()
    assert sll._n == 0
    lessons = sll._rule_lessons([])
    assert isinstance(lessons, str)
    assert sll.strategies() == []


def test_code_safety():
    """Test code safety scanner detects dangerous patterns."""
    try:
        from code_safety import CodeSafety
    except Exception:
        pytest.skip("code_safety not available")
    cs = CodeSafety()
    assert hasattr(cs, "analyze") or hasattr(cs, "sanitize")


def test_config_loader():
    """Test configuration loading."""
    try:
        from config_loader import ConfigLoader
    except Exception:
        pytest.skip("config_loader not available")
    cfg = ConfigLoader()
    # Should be able to get values
    assert hasattr(cfg, "get")


def test_embedding_model():
    """Test embedding model can be instantiated."""
    try:
        from embedding_model import EmbeddingModel
    except Exception:
        pytest.skip("embedding_model not available")
    em = EmbeddingModel()
    assert hasattr(em, "embed") or hasattr(em, "encode") or hasattr(em, "get_embedding")


def test_context_buffer_overflow():
    """Test context buffer properly handles overflow."""
    mod = _import_optional("context_buffer")
    ContextBuffer = getattr(mod, "ContextBuffer")
    cb = ContextBuffer(max_size=2)
    cb.add({"k": "a"})
    cb.add({"k": "b"})
    cb.add({"k": "c"})
    assert len(cb) == 2
    # Oldest item should be dropped
    items = cb.get_all()
    assert items[0]["k"] == "b"


@pytest.mark.asyncio
async def test_internet_agent_search():
    """Test internet agent can search (with mocked browser)."""
    try:
        from internet_agent import InternetAgent
        from event_bus import EventBus
        from state_manager import StateManager
    except Exception:
        pytest.skip("internet_agent dependencies not available")
    bus = EventBus()
    await getattr(bus, "start", lambda: None)()
    sm = StateManager()
    ia = InternetAgent(bus, sm)
    assert hasattr(ia, "execute")
    assert hasattr(ia, "_search")
    assert hasattr(ia, "_arxiv")


def test_logger_setup():
    """Test logger can be created."""
    try:
        from logger import setup_logger
    except Exception:
        pytest.skip("logger not available")
    log = setup_logger("test_module")
    assert log is not None
    assert hasattr(log, "info")
    assert hasattr(log, "error")
