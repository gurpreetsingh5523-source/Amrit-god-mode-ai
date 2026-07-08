#!/usr/bin/env python3
"""
BitNet b1.58 - Interactive inference helper
Falcon3-10B-Instruct (ਸਭ ਤੋਂ ਵੱਡਾ ਉਪਲਬਧ BitNet b1.58 ਮਾਡਲ)
"""

import subprocess
import sys
from pathlib import Path

BITNET_DIR = Path.home() / "BitNet"


def find_model_file() -> Path:
    """Find the downloaded GGUF model file."""
    for pattern in ["**/*.gguf"]:
        matches = list((BITNET_DIR / "models").glob(pattern))
        if matches:
            # Prefer i2_s quantization (best for BitNet b1.58)
            for f in matches:
                if "i2_s" in f.name:
                    return f
            return matches[0]
    raise FileNotFoundError(
        f"No GGUF model found in {BITNET_DIR}/models\n"
        "ਪਹਿਲਾਂ setup_bitnet.sh ਚਲਾਓ।"
    )


def run_inference(
    prompt: str,
    system_prompt: str = "You are a helpful AI assistant.",
    n_predict: int = 200,
    threads: int = 4,
    ctx_size: int = 2048,
    temperature: float = 0.7,
    chat_mode: bool = False,
):
    """Run inference using bitnet.cpp's run_inference.py."""
    model_file = find_model_file()
    script = BITNET_DIR / "run_inference.py"

    cmd = [
        sys.executable, str(script),
        "-m", str(model_file),
        "-p", system_prompt if chat_mode else prompt,
        "-n", str(n_predict),
        "-t", str(threads),
        "-c", str(ctx_size),
        "-temp", str(temperature),
    ]
    if chat_mode:
        cmd.append("-cnv")

    print(f"\n[BitNet b1.58] Model: {model_file.name}")
    print(f"[BitNet b1.58] Threads: {threads}  |  Ctx: {ctx_size}  |  Temp: {temperature}\n")
    print("─" * 60)

    subprocess.run(cmd, cwd=BITNET_DIR)


def benchmark(n_prompt: int = 512, n_token: int = 128, threads: int = 4):
    """Run performance benchmark."""
    model_file = find_model_file()
    script = BITNET_DIR / "utils" / "e2e_benchmark.py"

    cmd = [
        sys.executable, str(script),
        "-m", str(model_file),
        "-p", str(n_prompt),
        "-n", str(n_token),
        "-t", str(threads),
    ]
    print(f"\n[BitNet Benchmark] Model: {model_file.name}")
    print(f"Prompt tokens: {n_prompt}  |  Generate tokens: {n_token}\n")
    subprocess.run(cmd, cwd=BITNET_DIR)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BitNet b1.58 inference helper")
    sub = parser.add_subparsers(dest="cmd")

    # ── chat mode ────────────────────────────────────────────
    chat_p = sub.add_parser("chat", help="Interactive chat mode")
    chat_p.add_argument("-s", "--system", default="You are a helpful AI assistant.",
                        help="System prompt")
    chat_p.add_argument("-t", "--threads", type=int, default=4)
    chat_p.add_argument("-c", "--ctx", type=int, default=2048)
    chat_p.add_argument("--temp", type=float, default=0.7)

    # ── single prompt ─────────────────────────────────────────
    run_p = sub.add_parser("run", help="Single prompt inference")
    run_p.add_argument("-p", "--prompt", required=True, help="Prompt text")
    run_p.add_argument("-n", "--predict", type=int, default=200)
    run_p.add_argument("-t", "--threads", type=int, default=4)
    run_p.add_argument("--temp", type=float, default=0.7)

    # ── benchmark ────────────────────────────────────────────
    bench_p = sub.add_parser("bench", help="Performance benchmark")
    bench_p.add_argument("-t", "--threads", type=int, default=4)

    # ── info ─────────────────────────────────────────────────
    sub.add_parser("info", help="Show model info")

    args = parser.parse_args()

    if args.cmd == "chat":
        run_inference(
            prompt="",
            system_prompt=args.system,
            threads=args.threads,
            ctx_size=args.ctx,
            temperature=args.temp,
            chat_mode=True,
        )

    elif args.cmd == "run":
        run_inference(
            prompt=args.prompt,
            n_predict=args.predict,
            threads=args.threads,
            temperature=args.temp,
        )

    elif args.cmd == "bench":
        benchmark(threads=args.threads)

    elif args.cmd == "info":
        try:
            model = find_model_file()
            size_gb = model.stat().st_size / (1024 ** 3)
            print(f"\nModel path : {model}")
            print(f"File size  : {size_gb:.2f} GB")
            print(f"Quantization: i2_s (1.58-bit, ~{size_gb:.1f} GB / 16 GB RAM)\n")
        except FileNotFoundError as e:
            print(e)

    else:
        parser.print_help()
        print("\n── Examples ──────────────────────────────────────────")
        print("  python bitnet_run.py chat")
        print("  python bitnet_run.py run -p 'ਪੰਜਾਬ ਬਾਰੇ ਦੱਸੋ'")
        print("  python bitnet_run.py bench")
        print("  python bitnet_run.py info")
