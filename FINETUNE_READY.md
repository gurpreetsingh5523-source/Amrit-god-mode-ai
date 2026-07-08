# 🧠 Amrit Fine-Tune — READY (do NOT run on low battery)

> Method = **NEW** (NOT the OpenMythos from-scratch method). We specialise a
> proven, already-intelligent multimodal base with LoRA on CLEAN VERIFIED data.

## OpenMythos (OLD method) — why it failed, do NOT repeat
- Trained a **4.1M-param** custom transformer **from scratch** → far too small for intelligence.
- Trained on **garbage data** (a weak model's self-scored, garbled, off-topic answers).
- Result: "intelligence ruk gayi" — it could memorise, never reason.

## NEW method — the "best model" path
1. **Base model:** **Qwen3.5 9B** (already installed) — native multimodal
   (vision + coding + chat = the "bahupakhi shakhsiat"). Billions of params of
   existing intelligence; we don't rebuild it, we specialise it.
2. **Data:** `workspace/finetune_data.jsonl` — 72 examples, **every one VERIFIED**
   (coding solutions exec-tested; knowledge from real repos). Split ready in
   `workspace/finetune_data/` (train.jsonl=65, valid.jsonl=7).
3. **Adapter:** **LoRA** (tiny adapters, ~0.2% params) — fits 16GB, ~1hr.
4. **Framework:** **MLX-LM** (Apple Silicon native).

## Run later (plugged in + RAM freed)
```bash
# 1. install (one-time)
pip install mlx-lm

# 2. fine-tune (LoRA) — uses workspace/finetune_data/{train,valid}.jsonl
python -m mlx_lm.lora \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --train --data workspace/finetune_data \
  --batch-size 1 --iters 300 --lora-layers 8

# 3. test the adapter
python -m mlx_lm.generate \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --adapter-path adapters --prompt "Write a function to merge two sorted lists"
```

## Important reality (honest)
- LoRA tunes STYLE + domain knowledge, **not raw IQ**. The "best model" for Amrit =
  proven base + this LoRA + Amrit's orchestration/memory/safety layers around it.
- Grow the dataset first (`python training_data_pipeline.py`, +~12 verified/run) toward
  100-300 before fine-tuning for a stronger result.
- ⚠️ Fine-tune is GPU/RAM heavy → only run on AC power with apps closed.
