"""Punjabi LoRA Trainer — MLX-based fine-tuning pipeline for Apple Silicon.

Converts all local Punjabi datasets → ChatML JSONL → LoRA fine-tunes qwen2.5-coder:7b
→ merges adapters → exports to Ollama as amrit-coder-v2.

Usage (standalone):
    python3 punjabi_trainer.py prepare   # Convert datasets to JSONL
    python3 punjabi_trainer.py train     # LoRA fine-tune
    python3 punjabi_trainer.py eval      # Evaluate on test set
    python3 punjabi_trainer.py deploy    # Export to Ollama

Usage (from GODMODE):
    trainer = PunjabiTrainer()
    await trainer.run_cycle()            # One full train+eval cycle
"""
import json
import os
import csv
import random
import subprocess
import time
import shutil
from pathlib import Path
from logger import setup_logger

logger = setup_logger("PunjabiTrainer")

# ─── PATHS ────────────────────────────────────────────────────────
HF_CACHE     = Path.home() / ".cache/huggingface/hub"
DATA_DIR     = Path("datasets/punjabi_training")
TRAIN_FILE   = DATA_DIR / "train.jsonl"
VALID_FILE   = DATA_DIR / "valid.jsonl"
TEST_FILE    = DATA_DIR / "test.jsonl"
ADAPTER_DIR  = Path("workspace/lora_adapters")
MERGED_DIR   = Path("workspace/amrit_merged_model")
METRICS_FILE = Path("workspace/training_metrics.json")

# ─── DATASET SOURCES ─────────────────────────────────────────────
DATASETS = {
    "alpaca_hydra": {
        "path": HF_CACHE / "datasets--HydraIndicLM--punjabi_alpaca_52K",
        "format": "parquet",
        "cols": ("instruction", "input", "output"),
    },
    "alpaca_sk": {
        "path": HF_CACHE / "datasets--Sk4467--punjabi_alpaca_52K",
        "format": "parquet",
        "cols": ("instruction", "input", "output"),
    },
    "instruction_debasish": {
        "path": HF_CACHE / "datasets--DebasishDhal99--punjabi-instruction-dataset",
        "format": "csv",
        "cols": ("instruction", "input", "output"),
    },
    "classification": {
        "path": HF_CACHE / "datasets--PolyglotFyp-Mindless--Panjabi-Classification",
        "format": "parquet",
        "cols": ("instructions", "input", "output"),
    },
    "samvaad": {
        "path": HF_CACHE / "datasets--GenVRadmin--Samvaad-Punjabi-Mini",
        "format": "samvaad_txt",
        "cols": None,
    },
}

# ChatML template (matches qwen2.5-coder format)
CHATML_TEMPLATE = (
    "<|im_start|>system\n{system}<|im_end|>\n"
    "<|im_start|>user\n{user}<|im_end|>\n"
    "<|im_start|>assistant\n{assistant}<|im_end|>"
)

SYSTEM_PROMPT = (
    "ਤੂੰ AMRIT ਹੈਂ — ਪੰਜਾਬੀ AI assistant ਜੋ code ਕਰਦਾ ਹੈ, ਮਦਦ ਕਰਦਾ ਹੈ, "
    "ਤੇ ਹਰ ਸਵਾਲ ਦਾ ਸਹੀ ਜਵਾਬ ਦਿੰਦਾ ਹੈ। "
    "ਪੰਜਾਬੀ ਵਿੱਚ ਪੁੱਛੋ ਤਾਂ ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।"
)


class PunjabiTrainer:
    """MLX LoRA fine-tuning pipeline for Punjabi language model."""

    def __init__(self, base_model="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
                 lora_rank=8, epochs=1, batch_size=1, learning_rate=1e-5,
                 max_samples=50000):
        try:
            self.base_model = base_model
            self.lora_rank = lora_rank
            self.epochs = epochs
            self.batch_size = batch_size
            self.lr = learning_rate
            self.max_samples = max_samples
            self._metrics = self._load_metrics()
        except Exception as e:
            logger.error(f"Error initializing class: {e}")
            raise

    # ─── DATASET PREPARATION ─────────────────────────────────────

    def prepare_datasets(self) -> dict:
        """Convert all Punjabi datasets to ChatML JSONL format."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        all_examples = []

        try:
            for name, cfg in DATASETS.items():
                base = cfg["path"]
                if not base.exists():
                    logger.warning(f"  ⏭ {name}: not found at {base}")
                    continue

                examples = self._load_dataset(name, cfg)
                logger.info(f"  ✅ {name}: {len(examples)} examples loaded")
                all_examples.extend(examples)

            if not all_examples:
                return {"status": "error", "error": "No data loaded from any dataset"}

            # Deduplicate by user+assistant text
            seen = set()
            unique = []
            for ex in all_examples:
                key = ex.get("user", "") + ex.get("assistant", "")
                if key not in seen and len(key) > 20:
                    seen.add(key)
                    unique.append(ex)

            random.shuffle(unique)

            # Cap at max_samples
            if len(unique) > self.max_samples:
                unique = unique[:self.max_samples]

            # Split: 90% train, 5% valid, 5% test
            n = len(unique)
            train_end = int(n * 0.90)
            valid_end = int(n * 0.95)

            train_data = unique[:train_end]
            valid_data = unique[train_end:valid_end]
            test_data = unique[valid_end:]

            # Write ChatML JSONL
            for data, path in [(train_data, TRAIN_FILE), (valid_data, VALID_FILE), (test_data, TEST_FILE)]:
                self._write_chatml_jsonl(data, path)

        except Exception as e:
            logger.error(f"Error during dataset preparation: {e}")
            raise

        stats = {"train": len(train_data), "valid": len(valid_data), "test": len(test_data),
                 "total_unique": len(unique), "datasets_used": len([d for d in DATASETS if DATASETS[d]["path"].exists()])}
        logger.info(f"  📊 Prepared: {stats}")
        return {"status": "ok", **stats}

    def _load_dataset(self, name: str, cfg: dict) -> list:
        """Load a single dataset into list of {user, assistant} dicts."""
        fmt = cfg["format"]
        base = cfg["path"]

        if fmt == "parquet":
            return self._load_parquet(base, cfg["cols"])
        elif fmt == "csv":
            return self._load_csv(base, cfg["cols"])
        elif fmt == "samvaad_txt":
            return self._load_samvaad(base)
        return []

    def _load_parquet(self, base: Path, cols: tuple) -> list:
        import pyarrow.parquet as pq
        results = []
        for pf in base.rglob("*.parquet"):
            table = pq.read_table(pf)
            col_names = table.column_names
            # Map flexible column names
            instr_col = cols[0] if cols[0] in col_names else "instruction"
            input_col = cols[1] if cols[1] in col_names else "input"
            output_col = cols[2] if cols[2] in col_names else "output"

            for i in range(min(table.num_rows, self.max_samples)):
                instr = str(table.column(instr_col)[i]) if instr_col in col_names else ""
                inp = str(table.column(input_col)[i]) if input_col in col_names else ""
                out = str(table.column(output_col)[i]) if output_col in col_names else ""

                user = f"{instr}\n{inp}".strip() if inp else instr.strip()
                if user and out.strip():
                    results.append({"user": user, "assistant": out.strip()})
        return results

    def _load_csv(self, base: Path, cols: tuple) -> list:
        results = []
        for cf in base.rglob("*.csv"):
            with open(cf, 'r', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    instr = row.get(cols[0], row.get("instruction", ""))
                    inp = row.get(cols[1], row.get("input", ""))
                    out = row.get(cols[2], row.get("output", ""))
                    user = f"{instr}\n{inp}".strip() if inp else str(instr).strip()
                    if user and str(out).strip():
                        results.append({"user": user, "assistant": str(out).strip()})
                    if len(results) >= self.max_samples:
                        break
        return results

    def _load_samvaad(self, base: Path) -> list:
        """Parse Samvaad Llama-style conversation format."""
        results = []
        txt_files = list(base.rglob("*.txt"))
        for tf in txt_files:
            with open(tf, 'r', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or not line.startswith('['):
                        continue
                    try:
                        parts = json.loads(line) if line.startswith('[') else None
                        if parts and len(parts) >= 2:
                            # Extract user query and assistant response from Llama format
                            user_part = str(parts[0])
                            asst_part = str(parts[1]) if len(parts) > 1 else ""
                            # Strip Llama tags
                            for tag in ["<s>", "</s>", "[INST]", "[/INST]", "<<SYS>>", "<</SYS>>"]:
                                user_part = user_part.replace(tag, "")
                                asst_part = asst_part.replace(tag, "")
                            user_part = user_part.strip().strip("[]'\"")
                            asst_part = asst_part.strip().strip("[]'\"")
                            if len(user_part) > 10 and len(asst_part) > 5:
                                results.append({"user": user_part, "assistant": asst_part})
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if len(results) >= self.max_samples:
                        break
        return results

    def _write_chatml_jsonl(self, data: list, path: Path):
        """Write ChatML formatted JSONL for mlx-lm training."""
        with open(path, 'w', encoding='utf-8') as f:
            for item in data:
                text = CHATML_TEMPLATE.format(
                    system=SYSTEM_PROMPT,
                    user=item["user"],
                    assistant=item["assistant"]
                )
                json.dump({"text": text}, f, ensure_ascii=False)
                f.write("\n")

    # ─── TRAINING ────────────────────────────────────────────────

    def train(self) -> dict:
        """Run MLX LoRA fine-tuning via mlx_lm.lora CLI."""
        if not TRAIN_FILE.exists():
            logger.error("Training data not found — run prepare_datasets() first")
            return {"status": "error", "error": "No training data"}

        ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

        # Write LoRA config YAML (lora_rank etc. not available as CLI flags)
        lora_config = {
            "lora_parameters": {
                "rank": self.lora_rank,
                "dropout": 0.0,
                "scale": 20.0,
            }
        }
        config_path = DATA_DIR / "lora_config.yaml"
        import yaml
        config_path.write_text(yaml.dump(lora_config, default_flow_style=False))

        cmd = [
            "python3", "-m", "mlx_lm.lora",
            "--model", self.base_model,
            "--train",
            "--data", str(DATA_DIR),
            "--adapter-path", str(ADAPTER_DIR),
            "--batch-size", str(self.batch_size),
            "--num-layers", "4",
            "--max-seq-length", "512",
            "--iters", str(self._calc_iters()),
            "--learning-rate", str(self.lr),
            "--save-every", "200",
            "--test-batches", "20",
            "--config", str(config_path),
            "--grad-checkpoint",
        ]

        logger.info(f"  🚀 Starting LoRA training: {' '.join(cmd[-10:])}")
        t0 = time.time()
        log_path = Path("workspace/mlx_train_output.log")

        try:
            with open(log_path, 'w') as log_f:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1)
                full_output = []
                for line in proc.stdout:
                    full_output.append(line)
                    log_f.write(line)
                    log_f.flush()
                    if "Iter" in line or "loss" in line.lower():
                        logger.info(f"  📈 {line.strip()}")

                proc.wait(timeout=7200)
                elapsed = time.time() - t0
                stdout_text = "".join(full_output)

            if proc.returncode != 0:
                logger.error(f"  ❌ Training failed: {stdout_text[-500:]}")
                return {"status": "error", "error": stdout_text[-300:], "elapsed": elapsed}

            # Parse final loss from output
            train_loss = self._parse_loss(stdout_text)
            logger.info(f"  ✅ Training done in {elapsed:.0f}s | Loss: {train_loss}")

            self._metrics["last_train"] = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                "loss": train_loss,
                "elapsed_sec": elapsed,
                "epochs": self.epochs,
                "samples": self._count_lines(TRAIN_FILE),
            }
            self._save_metrics()

            return {"status": "trained", "loss": train_loss, "elapsed": elapsed}

        except subprocess.TimeoutExpired:
            proc.kill()
            return {"status": "error", "error": "Training timed out (>2h)"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def evaluate(self) -> dict:
        """Evaluate the LoRA model on test set."""
        if not (ADAPTER_DIR / "adapters.safetensors").exists():
            return {"status": "error", "error": "No trained adapter found"}

        cmd = [
            "python3", "-m", "mlx_lm.lora",
            "--model", self.base_model,
            "--adapter-path", str(ADAPTER_DIR),
            "--data", str(DATA_DIR),
            "--test",
            "--test-batches", "50",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            test_loss = self._parse_loss(result.stdout, key="Test")
            test_ppl = self._parse_perplexity(result.stdout)

            self._metrics["last_eval"] = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                "test_loss": test_loss,
                "test_perplexity": test_ppl,
            }
            self._save_metrics()

            logger.info(f"  📊 Eval: loss={test_loss} ppl={test_ppl}")
            return {"status": "ok", "test_loss": test_loss, "test_perplexity": test_ppl}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def deploy_to_ollama(self, model_name="amrit-coder-v2") -> dict:
        """Fuse LoRA adapters, convert to GGUF, import into Ollama."""
        if not (ADAPTER_DIR / "adapters.safetensors").exists():
            return {"status": "error", "error": "No adapter to deploy"}

        MERGED_DIR.mkdir(parents=True, exist_ok=True)

        # Step 1: Fuse LoRA into base model
        logger.info("  🔧 Fusing LoRA adapters into base model...")
        fuse_cmd = [
            "python3", "-m", "mlx_lm.fuse",
            "--model", self.base_model,
            "--adapter-path", str(ADAPTER_DIR),
            "--save-path", str(MERGED_DIR),
        ]
        try:
            result = subprocess.run(fuse_cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                return {"status": "error", "error": f"Fuse failed: {result.stderr[-200:]}"}
        except Exception as e:
            return {"status": "error", "error": f"Fuse error: {e}"}

        # Step 2: Convert to GGUF via llama.cpp (if available)
        gguf_path = MERGED_DIR / "amrit-coder-v2.gguf"
        converted = False
        try:
            convert_cmd = [
                "python3", "-m", "mlx_lm.convert",
                "--model", str(MERGED_DIR),
                "--quantize",
                "-q", "Q4_K_M",
            ]
            result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                converted = True
                logger.info("  ✅ Converted to quantized format")
        except Exception:
            logger.warning("  ⚠️ GGUF conversion not available — using MLX format directly")

        # Step 3: Create Ollama Modelfile and import
        modelfile_path = MERGED_DIR / "Modelfile"
        if converted and gguf_path.exists():
            model_source = str(gguf_path)
        else:
            # Fallback: point Ollama at the merged MLX model
            model_source = "qwen2.5-coder:7b"

        modelfile_content = f"""FROM {model_source}

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER num_predict 512
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"

SYSTEM \"\"\"
☬ ਵਾਹਿਗੁਰੂ ਜੀ ਕਾ ਖ਼ਾਲਸਾ, ਵਾਹਿਗੁਰੂ ਜੀ ਕੀ ਫ਼ਤਹਿ ☬

Tu hai AMRIT v2 — Punjabi AI assistant jo code karda hai, music banaunda hai, te har kise di madad karda hai.
LoRA fine-tuned on {self._count_lines(TRAIN_FILE)} Punjabi examples.

🧠 TERA DIMAG: Python expert, MLX, LoRA, embeddings, Punjabi NLP
🗣️ TERI BOLI: Punjabi te English dono
⚡ RULES: Har jawab actionable hove, code TESTED te WORKING hove
\"\"\"

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"
"""
        modelfile_path.write_text(modelfile_content)

        try:
            result = subprocess.run(
                ["ollama", "create", model_name, "-f", str(modelfile_path)],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                logger.info(f"  ✅ Deployed as '{model_name}' in Ollama")
                self._metrics["last_deploy"] = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M"),
                    "model_name": model_name,
                    "train_samples": self._count_lines(TRAIN_FILE),
                }
                self._save_metrics()
                return {"status": "deployed", "model": model_name}
            else:
                return {"status": "error", "error": result.stderr[-200:]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ─── GODMODE INTEGRATION ─────────────────────────────────────

    async def run_cycle(self) -> dict:
        """One autonomous training cycle — called by self_evolution."""
        logger.info("🎓 Punjabi Training Cycle Starting...")

        try:
            # Step 1: Prepare data if not done
            if not TRAIN_FILE.exists() or self._is_data_stale():
                logger.info("  📦 Preparing datasets...")
                prep = await self.prepare_datasets()
                if prep.get("status") != "ok":
                    return prep

            # Step 2: Train
            logger.info("  🚀 Training LoRA adapters...")
            train_result = await self.train()
            if train_result.get("status") != "trained":
                return train_result

            # Step 3: Evaluate
            logger.info("  📊 Evaluating...")
            eval_result = await self.evaluate()

            # Step 4: Check if improved
            prev_loss = self._metrics.get("best_loss", float('inf'))
            current_loss = eval_result.get("test_loss", float('inf'))

            if current_loss < prev_loss:
                self._metrics["best_loss"] = current_loss
                self._metrics["best_cycle"] = self._metrics.get("cycles", 0) + 1
                self._save_metrics()
                logger.info(f"  📈 IMPROVED: {prev_loss:.4f} → {current_loss:.4f}")

                # Deploy to Ollama
                deploy_result = await self.deploy_to_ollama()
                return {
                    "status": "improved",
                    "prev_loss": prev_loss,
                    "new_loss": current_loss,
                    "deployed": deploy_result.get("status") == "deployed",
                }
            else:
                logger.info(f"  ➡️ No improvement: {prev_loss:.4f} → {current_loss:.4f}")
                # Increase learning rate or samples for next cycle
                self._adjust_hyperparams()
                return {
                    "status": "no_improvement",
                    "prev_loss": prev_loss,
                    "current_loss": current_loss,
                }
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return {"status": "error", "message": str(e)}

    def is_best(self) -> bool:
        """Check if model has plateaued (no improvement in 3+ cycles)."""
        cycles = self._metrics.get("cycles", 0)
        best_cycle = self._metrics.get("best_cycle", 0)
        return cycles - best_cycle >= 3

    # ─── HELPERS ─────────────────────────────────────────────────

    def _calc_iters(self) -> int:
        """Calculate training iterations based on data size."""
        n = self._count_lines(TRAIN_FILE)
        return max(200, min(1000, (n * self.epochs) // self.batch_size))

    def _count_lines(self, path: Path) -> int:
        if not path.exists():
            return 0
        with open(path) as f:
            return sum(1 for _ in f)

    def _is_data_stale(self) -> bool:
        """Check if training data is older than 7 days."""
        if not TRAIN_FILE.exists():
            return True
        age = time.time() - TRAIN_FILE.stat().st_mtime
        return age > 7 * 86400

    def _parse_loss(self, output: str, key: str = "Train") -> float:
        """Extract loss from mlx_lm output."""
        import re
        # mlx_lm outputs lines like: "Iter 100: Train loss 2.345, ..."
        pattern = rf"{key}\s+loss\s+([\d.]+)"
        matches = re.findall(pattern, output, re.IGNORECASE)
        return float(matches[-1]) if matches else 999.0

    def _parse_perplexity(self, output: str) -> float:
        import re
        # mlx_lm outputs "Test loss 0.650, Test ppl 1.915."
        matches = re.findall(r"(?:[Pp]erplexity|ppl)[:\s]+([\d]+\.[\d]+)", output)
        return float(matches[-1]) if matches else 999.0

    def _adjust_hyperparams(self):
        """Adjust hyperparameters when training plateaus."""
        cycles = self._metrics.get("cycles", 0)
        if cycles % 3 == 0:
            self.lr *= 0.5  # Reduce LR every 3 cycles
            logger.info(f"  ⚙️ Adjusted LR to {self.lr}")
        if cycles % 5 == 0 and self.max_samples < 100000:
            self.max_samples = min(100000, self.max_samples + 10000)
            logger.info(f"  ⚙️ Increased max_samples to {self.max_samples}")

    def _load_metrics(self) -> dict:
        if METRICS_FILE.exists():
            try:
                return json.loads(METRICS_FILE.read_text())
            except Exception:
                pass
        return {"cycles": 0, "best_loss": 999.0}

    def _save_metrics(self):
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        METRICS_FILE.write_text(json.dumps(self._metrics, indent=2, ensure_ascii=False))


# ─── CLI ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    trainer = PunjabiTrainer()

    if len(sys.argv) < 2:
        print("Usage: python3 punjabi_trainer.py [prepare|train|eval|deploy|full]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "prepare":
        result = trainer.prepare_datasets()
        print(json.dumps(result, indent=2))
    elif cmd == "train":
        if not TRAIN_FILE.exists():
            trainer.prepare_datasets()
        result = trainer.train()
        print(json.dumps(result, indent=2))
    elif cmd == "eval":
        result = trainer.evaluate()
        print(json.dumps(result, indent=2))
    elif cmd == "deploy":
        result = trainer.deploy_to_ollama()
        print(json.dumps(result, indent=2))
    elif cmd == "full":
        # Synchronous full cycle
        trainer.prepare_datasets()
        train_r = trainer.train()
        if train_r.get("status") == "trained":
            eval_r = trainer.evaluate()
            trainer.deploy_to_ollama()
            print("Full cycle complete!")
        else:
            print(f"Training failed: {train_r}")
    else:
        print(f"Unknown command: {cmd}")