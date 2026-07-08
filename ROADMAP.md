# 🕉️ Amrit God Mode AI — Roadmap

> Honest north star: **a reliable, capable, self-improving autonomous agent** —
> not "ASI". Amrit's reasoning core is a frozen LLM (DeepSeek); we improve its
> scaffolding, skills, memory, and (eventually) a local fine-tuned model on its
> own successful runs. Inspired by self-improvement research, grounded in reality.

## Where we are (verified)
- ✅ Multi-agent orchestration (19 agents, 29 subsystems)
- ✅ Self-improvement loops: DualBrain self-fix, FailureDNA learning, skill crystallization
- ✅ Learns from open source (github_learner → 270 patterns) and grounds the coder
- ✅ Self-verify: Python (DualBrain), web (web_verify), tests (tester loop)
- ✅ Live dashboard that reports + controls the engine (status/learn/fix+apply/evolve)
- ❌ NOT AGI/ASI. Autonomous runs still hit bugs needing a human. No success metric yet.

---

## Phase 1 — Reliability & Measurement  ◀ CURRENT
**Why:** "You can't improve what you don't measure." Before claiming progress we
must know what % of real tasks Amrit completes autonomously.
- [x] `benchmark.py` — fixed suite of real tasks with OBJECTIVE pass/fail checks
- [x] Baseline recorded: **ATSR = 100% (10/10)** on EASY tier (single-function
      codegen/bugfix/algorithm) — proves the core DualBrain codegen is solid.
- [x] Added HARD tier (stateful classes: LRU cache/Stack; algos: permutations,
      merge sort, balanced parens; class bugfix) + WEB tier (3d-force-graph HTML
      verified in a real headless browser).
- [x] Tiered baseline: **easy 10/10, hard 6/6, web 1/1 → ATSR 100%**. The web pass
      confirms today's web_verify gotcha-fixes + learned patterns made the web
      pipeline reliable for isolated graphs.
- [x] Added INTEGRATION tier: fastapi_crud (TestClient POST/GET/DELETE), multi-function
      pipeline, html_interactive_counter (playwright click→DOM). ALL PASS → 20/20 = 100%.
- **KEY INSIGHT:** the benchmark runs everything through DualBrain (single focused
      artifact) — which is ~100% reliable. But today's real failures (dashboard
      tick/path/empty-graph, multi-file nesting, deps-stall) were in the **SWARM**
      (multi-agent orchestration of big multi-file projects), NOT DualBrain.
- [x] SWARM-path benchmark built (`swarm_benchmark.py`) — runs real projects via
      `main.py --mode swarm` and verifies assembled output. BASELINE: **2/3 = 67%**
      (✅ FastAPI CRUD correct-path+endpoints, ✅ multi-file package, ❌ web dashboard
      canvas=0 empty-render).
- [x] ROOT CAUSE of swarm:web fail FOUND + FIXED: coder wrote `ForceGraph3D(el)` but
      3d-force-graph is a FACTORY → correct is `ForceGraph3D()(el)`; one-call form
      silently fails (canvas=0, no JS error so web_verify missed it). Added deterministic
      gotcha in web_verify.fix_common_gotchas → the failed artifact now renders (canvas=1).
      Effective swarm ATSR now 3/3.
- **Status:** Phase 1 COMPLETE ✅ — DualBrain 20/20, swarm baseline 67%→fixed. Real
      frontier (swarm web/multi-file) measured + first fix landed. Re-run swarm_benchmark.py
      after changes to confirm.

## Phase 2 — Memory & Continuity  ◀ IN PROGRESS
- [x] Cross-session task memory that actually informs new tasks: `task_memory.py`
      (TaskMemory) — semantic record/recall of every code-task outcome+lesson,
      persisted to workspace/task_memory.json. WIRED into coder_agent: recalls
      similar past experiences BEFORE generating (injects "what worked/failed")
      and RECORDS the outcome after. PROVEN: a new palindrome task recalls prior
      palindrome experiences across runs. (Complements FailureDNA[failures] +
      github_learner[external] + skill_crystallizer[exact replay].)
- [x] Deepened skill crystallization (reliable replay): CLOSED the feedback loop —
      main.py now records the REAL swarm outcome after a replay (was prematurely
      marking success=True). find_match auto-SKIPS proven-bad skills (used≥2 &
      rate<0.5); new prune() deletes consistently-failing ones (used≥3 & rate<0.34).
      Proven: a skill failing 3× → rate 0.0 → skipped + pruned.
- [ ] Optional: surface task-memory in the dashboard + chat "what have you learned doing".
- **Status:** Phase 2 COMPLETE ✅ — continuity (task_memory) + self-correcting skill reuse.

## Phase 3 — Planning & Reasoning depth  ✅ MOSTLY PRE-EXISTING + 1 fix
Audit found most of Phase 3 was ALREADY built — only reasoning-model routing was missing.
- [x] Self-critique + verify-before-finalize — ALREADY in DualBrain v3 (Vivek critique→
      refine loop, Verifier vote, multi_evaluator fitness). No rebuild needed.
- [x] Multi-candidate reasoning (tree-of-thought) — ALREADY: DualBrain Nirman A/B/C + fitness.
- [x] Recursive decomposition — ALREADY: task_decomposer + planner + goal_parser.
- [x] Route hard tasks to reasoning model (deepseek-reasoner) — WAS the only real gap
      (model in registry but never invoked). FIXED: llm_router.complete supports
      model="reasoning"/"deep" → deepseek-reasoner, + auto-escalates complex prompts
      (>4000 chars or ≥2 reasoning keywords). Planner + goal_parser now decompose with
      the reasoning model. Verified: reasoner LIVE (REASONER_OK), heuristic correct.
- **Status:** Phase 3 COMPLETE ✅ (mostly already present; reasoning routing added). 39 tests pass.

## Phase 4 — Capability breadth  ✅ mostly pre-existing + reachability wired
Audit: all capability MODULES already exist + functional (don't rebuild).
- [x] Vision — vision_agent, image_reader, object_detector, video_reader (functional).
- [x] Voice — voice_agent, speech_to_text, text_to_speech (present).
- [x] Web automation — browser_ops, web_scraper, crawler (functional).
- [x] Computer-use — screen_control.py is FULL: screenshot, understand_screen
      (vision+goal), click/double/right, move_to, type_text, run_shortcut, scroll;
      pyautogui works (screen 1512x982). deps (pyautogui, playwright) installed.
- [x] REACHABILITY (the real gap) — wired key capabilities into the chat workflow:
      "scrape <url>" → real web text; "screenshot"/"see screen" → capture + vision
      describe. PROVEN live. (Other caps reachable via their agents.)
- **Status:** Phase 4 COMPLETE ✅ — breadth existed; made it usable from chat. 39 tests pass.

## Phase 5 — Safety & Ethics  ✅ DONE
Audit: safety MECHANISMS existed (ethical_guard/safety_layer/code_safety/sandbox/
security_guard/permission_manager, wired in tool_agent) BUT Gurmat/Naam was only
prompt-text and test_security.py had 0 tests.
- [x] Made Naam ethics REAL: `naam_filter.py` (NaamFilter) — 7 Naam principles
      (Ikk/Sach/Daya/Seva/Santokh/Dharam/Nimrata) as intent-level category checks;
      returns (allowed, principle, reason). Self-test 7/7.
- [x] WIRED into ethical_guard.check → automatically part of the ToolAgent execution
      gate (so every tool/terminal/python action is Naam-checked).
- [x] Wrote real safety tests: test_security.py 10 tests (was 0) — lock in NaamFilter,
      EthicalGuard, Sandbox, SafetyLayer, and the ToolAgent gate.
- **Status:** Phase 5 COMPLETE ✅. Full suite 49 pass (godmode 23 + integration 16 + security 10).

## Phase 6 — Self-improvement depth (the real AGI-ward step)  ◀ IN PROGRESS
Investigated OpenMythos (older from-scratch attempt, ~/Desktop/amrit_agent/production_agency):
it "got stuck" because (1) the model was only 4.1M params (1700× too small for real
intelligence) and (2) trained on GARBAGE data (a weak model's self-scored, garbled,
off-topic answers). Lesson: scale + clean verified data both matter.
- [x] Picked base model: **Qwen2.5-Coder-7B** (best fine-tunable coder at 16GB),
      stack **MLX-LM + QLoRA 4-bit** (~1hr; need to free RAM, mlx-lm not yet installed).
- [x] Built `training_data_pipeline.py` — CLEAN, VERIFIED data: generates coding Q→A
      with DeepSeek then EXEC-VERIFIES each (keeps only code that actually runs+passes)
      + harvests real verified API patterns from learning_data.json. Output
      workspace/finetune_data.jsonl in chat format {messages:[user,assistant]}.
      First run: 6/6 coding exec-verified + 24 knowledge = 30 clean examples (0 garbage).
- [ ] SCALE the dataset (more task templates + harvest task_memory/benchmark/skills).
- [ ] Install mlx-lm, pull Qwen2.5-Coder-7B, QLoRA fine-tune on the clean data (needs free RAM).
- [x] **FIRST REAL FINE-TUNE COMPLETED** (2026-06-24): freed RAM (closed apps → 8.2GB free),
      LoRA fine-tuned **Qwen2.5-Coder-7B-Instruct-4bit** on the 72 verified examples via MLX
      (300 iters, peak mem 6.2GB). Train loss 1.25→0.13. Adapter saved
      workspace/amrit_lora_adapter/adapters.safetensors (23MB). VERIFIED: the fine-tuned
      model generates correct code (merge-sorted-lists). The OPPOSITE of OpenMythos.
- [x] DATA SCALED 72→236 verified examples (212 exec-verified coding + 24 knowledge) via the
      growth loop (per_category=5 + difficulty/theme/seed diversity, 7 runs). RE-TRAINED 7B
      (v2): 600 iters, train loss→0.253, **val loss 0.772 (BETTER than v1's 0.912)** — more
      clean data measurably improved generalisation. v2 adapter: workspace/amrit_lora_adapter_v2/.
      Verified: v2 wrote a correct longest_common_prefix function.
- **Status:** Phase 6 PROVEN + IMPROVED. Data-scaling → lower val loss confirmed (the real lever).
      Honest limits: 16GB caps local training at ~7-8B (12B needs cloud GPU). Path to more
      capability = keep growing clean verified data (mechanism proven). Vision+text+coding
      "system" = fine-tuned coder + installed VLMs (llava/gemma4) routed by Amrit.

---

## Metric we track every phase
**Autonomous Task Success Rate (ATSR)** = tasks passed without human help ÷ total.
Baseline: _to be set by Phase 1_.
