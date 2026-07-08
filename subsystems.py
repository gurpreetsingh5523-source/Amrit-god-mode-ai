"""
subsystems.py — Central registry that CONNECTS previously-orphaned engines
═══════════════════════════════════════════════════════════════════════════
30% of Amrit's files were dead code: built but imported by nothing. This
registry instantiates the high-value capability engines and exposes them to
the orchestrator + self-evolution loop, so they finally CONTRIBUTE:

  evaluation_engine  reward_engine     error_analyzer    self_graph
  task_decomposer    strategy_builder  priority_engine   model_selector
  dependency_resolver  self_learning_loop  self_upgrade  auto_refactor
  skill_evolver      mutation_lab      dream_engine

Each is loaded defensively (a broken one never takes down the brain).
"""
from logger import setup_logger

# EXPLICIT imports so these engines are statically reachable from the brain
# (orchestrator → subsystems → here), not just dynamically loaded.
from self_graph import SelfGraph
from evaluation_engine import EvaluationEngine
from reward_engine import RewardEngine
from error_analyzer import ErrorAnalyzer
from task_decomposer import TaskDecomposer
from strategy_builder import StrategyBuilder
from priority_engine import PriorityEngine
from model_selector import ModelSelector
from dependency_resolver import DependencyResolver
from self_learning_loop import SelfLearningLoop
from self_upgrade import SelfUpgrade
from auto_refactor import AutoRefactor
from skill_evolver import SkillEvolver
from mutation_lab import MutationLab
from dream_engine import DreamEngine

logger = setup_logger("Subsystems")

# name -> (ClassName, kwargs-factory)
_SPECS = [
    ("self_graph",          SelfGraph,          lambda orc: {}),
    ("evaluation_engine",   EvaluationEngine,   lambda orc: {}),
    ("reward_engine",       RewardEngine,       lambda orc: {}),
    ("error_analyzer",      ErrorAnalyzer,      lambda orc: {}),
    ("task_decomposer",     TaskDecomposer,     lambda orc: {}),
    ("strategy_builder",    StrategyBuilder,    lambda orc: {}),
    ("priority_engine",     PriorityEngine,     lambda orc: {}),
    ("model_selector",      ModelSelector,      lambda orc: {}),
    ("dependency_resolver", DependencyResolver, lambda orc: {}),
    ("self_learning_loop",  SelfLearningLoop,   lambda orc: {}),
    ("self_upgrade",        SelfUpgrade,        lambda orc: {}),
    ("auto_refactor",       AutoRefactor,       lambda orc: {"orchestrator": orc}),
    ("skill_evolver",       SkillEvolver,       lambda orc: {}),
    ("mutation_lab",        MutationLab,        lambda orc: {}),
    ("dream_engine",        DreamEngine,        lambda orc: {}),
]


# Optional I/O + tool engines — loaded DEFENSIVELY (heavy/optional deps like
# whisper, opencv, transformers may be absent; a missing dep must not break the
# brain). Dynamic import per-item so `import subsystems` never hard-fails.
_IO_SPECS = [
    ("git_ops",              "GitOps",            {}),
    ("module_installer",     "ModuleInstaller",   {}),
    ("web_scraper",          "WebScraper",        {}),
    ("search_engine",        "SearchEngine",      {}),
    ("crawler",              "Crawler",           {}),
    ("information_extractor","InformationExtractor", {}),
    ("local_llm",            "LocalLLM",          {}),
    ("image_reader",         "ImageReader",       {}),
    ("object_detector",      "ObjectDetector",    {}),
    ("video_reader",         "VideoReader",       {}),
    ("speech_to_text",       "SpeechToText",      {}),
    ("text_to_speech",       "TextToSpeech",      {}),
    ("amrit_kv_cache",       "AmritKVCacheManager", {}),
    ("dataset_trainer",      "DatasetTrainer",    {}),
    ("telegram_agent",       "TelegramAgent",     {}),
]


class SubsystemRegistry:
    def __init__(self, orchestrator=None):
        self._orc = orchestrator
        self._subs = {}
        self.loaded, self.failed = [], []
        # Tier 1: core capability engines (statically imported above)
        for name, cls, kw in _SPECS:
            try:
                self._subs[name] = cls(**kw(orchestrator))
                self.loaded.append(name)
            except Exception as e:
                self.failed.append((name, str(e)[:60]))
        # Tier 2: optional I/O / tool engines (dynamic, dep-tolerant)
        self.io_loaded, self.io_failed = [], []
        for mod_name, cls_name, kw in _IO_SPECS:
            try:
                mod = __import__(mod_name)
                self._subs[mod_name] = getattr(mod, cls_name)(**kw)
                self.io_loaded.append(mod_name)
            except Exception as e:
                self.io_failed.append((mod_name, str(e)[:50]))
        logger.info(f"🔌 Subsystems connected: core {len(self.loaded)}/{len(_SPECS)}, "
                    f"io {len(self.io_loaded)}/{len(_IO_SPECS)}"
                    + (f" | io-skipped(deps): {[f[0] for f in self.io_failed]}" if self.io_failed else ""))

    def get(self, name):
        return self._subs.get(name)

    def __getattr__(self, name):
        # allow registry.self_graph etc.
        subs = self.__dict__.get("_subs", {})
        if name in subs:
            return subs[name]
        raise AttributeError(name)

    def status(self) -> dict:
        return {"connected": len(self.loaded), "total": len(_SPECS),
                "loaded": self.loaded, "failed": self.failed}


if __name__ == "__main__":
    r = SubsystemRegistry()
    print("═" * 55)
    print(f"🔌 SubsystemRegistry self-test: {len(r.loaded)}/{len(_SPECS)} connected")
    for n in r.loaded:
        print(f"   ✅ {n}")
    for n, e in r.failed:
        print(f"   ❌ {n}: {e}")
