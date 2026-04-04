"""
AMRIT GODMODE — AirLLM Qwen3 Patch
Patches AirLLM's MLX Llama backend to support Qwen3 architecture:
1. QK-Norm (q_norm/k_norm) in Attention layers
2. PyTorch → MLX tensor conversion for input_ids
3. Correct rope_theta extraction (nested in rope_scaling dict)
4. Correct head_dim extraction (Qwen3 uses explicit head_dim != dim/n_heads)

Apply this patch after pip install/upgrade airllm:
    python airllm_qwen3_patch.py
"""
import os
import sys

def patch_airllm():
    # Find AirLLM installation
    import airllm
    pkg_dir = os.path.dirname(airllm.__file__)
    mlx_file = os.path.join(pkg_dir, "airllm_llama_mlx.py")

    if not os.path.exists(mlx_file):
        print(f"ERROR: {mlx_file} not found")
        return False

    with open(mlx_file, 'r') as f:
        code = f.read()

    patched = False

    # Patch 1: Add qk_norm to ModelArgs
    if "qk_norm: bool = False" not in code:
        code = code.replace(
            "    rope_traditional: bool = True\n",
            "    rope_traditional: bool = True\n    qk_norm: bool = False\n"
        )
        patched = True
        print("✅ Patch 1: Added qk_norm to ModelArgs")

    # Patch 1b: Add head_dim extraction from config 
    if "Use explicit head_dim from config" not in code:
        code = code.replace(
            '    params["norm_eps"] = config.rms_norm_eps\n'
            '    params["rope_traditional"] = False\n\n'
            '    sconfig = sanitize_config(params)',
            '    params["norm_eps"] = config.rms_norm_eps\n'
            '    params["rope_traditional"] = False\n'
            '    # Use explicit head_dim from config if available (Qwen3 uses head_dim != dim//n_heads)\n'
            '    if hasattr(config, \'head_dim\') and config.head_dim is not None:\n'
            '        params["head_dim"] = config.head_dim\n'
            '    # Extract rope_theta: check top-level, then rope_scaling/rope_parameters dicts\n'
            '    rope_theta = getattr(config, \'rope_theta\', None)\n'
            '    if rope_theta is None:\n'
            '        for attr in (\'rope_scaling\', \'rope_parameters\'):\n'
            '            d = getattr(config, attr, None)\n'
            '            if isinstance(d, dict) and \'rope_theta\' in d:\n'
            '                rope_theta = d[\'rope_theta\']\n'
            '                break\n'
            '    if rope_theta is not None:\n'
            '        params["rope_theta"] = rope_theta\n\n'
            '    sconfig = sanitize_config(params)'
        )
        patched = True
        print("✅ Patch 1b: Added head_dim and rope_theta extraction")

    # Patch 2: Detect qk_norm from config (model_type == 'qwen3')
    if "model_type == 'qwen3'" not in code:
        code = code.replace(
            "    sconfig = sanitize_config(params)\n\n    # quantization",
            "    sconfig = sanitize_config(params)\n\n"
            "    # Detect QK-Norm (Qwen3 and similar models)\n"
            "    model_type = getattr(config, 'model_type', '')\n"
            "    if model_type == 'qwen3' or (hasattr(config, 'qk_norm') and config.qk_norm):\n"
            "        sconfig['qk_norm'] = True\n\n"
            "    # quantization"
        )
        patched = True
        print("✅ Patch 2: Added Qwen3 qk_norm detection")

    # Patch 3: Add q_norm/k_norm to Attention.__init__
    if "self.qk_norm = args.qk_norm" not in code:
        code = code.replace(
            "        self.rope = nn.RoPE(\n"
            "            args.head_dim, traditional=args.rope_traditional, base=args.rope_theta\n"
            "        )\n",
            "        self.rope = nn.RoPE(\n"
            "            args.head_dim, traditional=args.rope_traditional, base=args.rope_theta\n"
            "        )\n"
            "        self.qk_norm = args.qk_norm\n"
            "        if self.qk_norm:\n"
            "            self.q_norm = RMSNorm(args.head_dim, eps=args.norm_eps)\n"
            "            self.k_norm = RMSNorm(args.head_dim, eps=args.norm_eps)\n"
        )
        patched = True
        print("✅ Patch 3: Added q_norm/k_norm to Attention")

    # Patch 4: Apply QK-Norm in Attention.__call__
    if "Apply QK-Norm if present" not in code:
        code = code.replace(
            "        values = values.reshape(B, L, self.n_kv_heads, -1).transpose(0, 2, 1, 3)\n\n        def repeat(a):",
            "        values = values.reshape(B, L, self.n_kv_heads, -1).transpose(0, 2, 1, 3)\n\n"
            "        # Apply QK-Norm if present (Qwen3)\n"
            "        if self.qk_norm:\n"
            "            queries = self.q_norm(queries)\n"
            "            keys = self.k_norm(keys)\n\n"
            "        def repeat(a):"
        )
        patched = True
        print("✅ Patch 4: Added QK-Norm application in forward pass")

    # Patch 5: Convert PyTorch tensor to MLX array
    if "Convert PyTorch tensor to MLX array" not in code:
        code = code.replace(
            "    def model_generate(self, x, temperature=0, max_new_tokens=None):\n"
            "        cache = []\n"
            "        TEST_NO_LAYERED = True\n\n"
            "        # Make an additive causal mask.",
            "    def model_generate(self, x, temperature=0, max_new_tokens=None):\n"
            "        cache = []\n"
            "        TEST_NO_LAYERED = True\n\n"
            "        # Convert PyTorch tensor to MLX array if needed\n"
            "        if hasattr(x, 'numpy'):\n"
            "            x = mx.array(x.numpy().astype('int32'))\n\n"
            "        # Make an additive causal mask."
        )
        patched = True
        print("✅ Patch 5: Added PyTorch→MLX tensor conversion")

    if patched:
        with open(mlx_file, 'w') as f:
            f.write(code)
        print(f"\n🎯 Patched: {mlx_file}")
    else:
        print("ℹ️  All patches already applied")

    return True

if __name__ == "__main__":
    patch_airllm()
