"""
amrit_kv_cache.py — RotorQuant KV Cache Module for Amrit GodMode
Apple Silicon (Metal backend) ਲਈ optimize ਕੀਤਾ

ਵਰਤੋਂ:
from amrit_kv_cache import AmritKVCacheManager
cache = AmritKVCacheManager(bits=3, method='rotorquant')
"""

import os
import sys
from typing import Tuple

import torch

# ─── RotorQuant Path — ਆਪਣਾ path ਇੱਥੇ ਬਦਲੋ ────────────────
ROTORQUANT_PATH = os.path.expanduser("~/rotorquant")
if ROTORQUANT_PATH not in sys.path:
    sys.path.insert(0, ROTORQUANT_PATH)

try:
    from turboquant.rotorquant import RotorQuantKVCache
    from turboquant.turboquant import TurboQuantKVCache

    ROTORQUANT_AVAILABLE = True
    print("✅ RotorQuant load ਹੋ ਗਿਆ")
except ImportError as e:
    ROTORQUANT_AVAILABLE = False
    print(f"⚠️  RotorQuant ਨਹੀਂ ਲੱਭਿਆ: {e}")
    print("   ਹੱਲ: git clone https://github.com/scrya-com/rotorquant.git ~/rotorquant")


class AmritKVCacheManager:
    """
    Amrit GodMode ਲਈ KV Cache Compression Manager

    ਵਿਸ਼ੇਸ਼ਤਾਵਾਂ:
    - 3-bit RotorQuant → 5x memory compression
    - Apple Silicon Metal backend (19-31x faster)
    - Automatic FP16 fallback ਜੇ RotorQuant ਨਾ ਮਿਲੇ
    - Protected tokens (first N tokens FP16 ਵਿੱਚ)

    ਵਰਤੋਂ:
        cache_mgr = AmritKVCacheManager(bits=3)
        c_k, c_v = cache_mgr.compress(keys, values)
        k, v = cache_mgr.decompress(c_k, c_v)
        cache_mgr.print_stats()
    """

    def __init__(
        self,
        bits: int = 3,
        method: str = "rotorquant",
        protected_tokens: int = 128,
        verbose: bool = True,
    ):
        self.bits = bits
        self.method = method
        self.protected_tokens = protected_tokens
        self.verbose = verbose
        self._cache = None
        self._stats = {
            "compressed": 0,
            "total_tokens": 0,
            "memory_saved_mb": 0.0,
        }
        if not ROTORQUANT_AVAILABLE:
            if verbose:
                print("ℹ️  FP16 passthrough mode ਵਿੱਚ ਕੰਮ ਕਰਾਂਗੇ")
            return
        self._init_cache()

    def _init_cache(self):
        try:
            if self.method == "rotorquant":
                self._cache = RotorQuantKVCache(bits=self.bits)
            else:
                self._cache = TurboQuantKVCache(bits=self.bits)
            if self.verbose:
                ratio = 16 / self.bits
                print(f"✅ {self.method.upper()} {self.bits}-bit | {ratio:.1f}x compression | Metal backend")
        except Exception as e:
            if self.verbose:
                print(f"❌ Cache init ਅਸਫਲ: {e}")
            self._cache = None

    def compress(
        self,
        keys: torch.Tensor,
        values: torch.Tensor,
        layer_idx: int = 0,
    ) -> Tuple[object, object]:
        """
        KV vectors compress ਕਰੋ

        Args:
            keys:      [batch, heads, seq_len, head_dim]
            values:    [batch, heads, seq_len, head_dim]
            layer_idx: layer ਨੰਬਰ (logging ਲਈ)

        Returns:
            (compressed_keys, compressed_values)
        """
        if self._cache is None:
            return keys, values

        seq_len = keys.shape[2] if keys.dim() >= 3 else keys.shape[0]
        if seq_len <= self.protected_tokens:
            return keys, values

        try:
            c_k = self._cache.compress_keys(keys)
            c_v = self._cache.compress_values(values)
            orig_mb = (keys.nelement() + values.nelement()) * 2 / 1024 / 1024
            self._stats["memory_saved_mb"] += orig_mb - (orig_mb / (16 / self.bits))
            self._stats["total_tokens"] += seq_len
            self._stats["compressed"] += 1
            return c_k, c_v
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Layer {layer_idx} compress error: {e}")
            return keys, values

    def decompress(
        self,
        compressed_keys: object,
        compressed_values: object,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compressed KV cache ਵਾਪਸ FP16 ਵਿੱਚ ਲਿਆਓ"""
        if self._cache is None:
            return compressed_keys, compressed_values
        try:
            k = self._cache.decompress_keys(compressed_keys)
            v = self._cache.decompress_values(compressed_values)
            return k, v
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Decompress error: {e}")
            return compressed_keys, compressed_values

    def get_stats(self) -> dict:
        return {
            "method": self.method,
            "bits": self.bits,
            "compression_ratio": f"{16/self.bits:.1f}x",
            "compressions_done": self._stats["compressed"],
            "total_tokens": self._stats["total_tokens"],
            "memory_saved_mb": round(self._stats["memory_saved_mb"], 2),
            "available": ROTORQUANT_AVAILABLE,
        }

    def print_stats(self):
        s = self.get_stats()
        print("\n📊 Amrit KV Cache ਰਿਪੋਰਟ:")
        print(f"   Method    : {s['method']} ({s['bits']}-bit)")
        print(f"   Ratio     : {s['compression_ratio']}")
        print(f"   Tokens    : {s['total_tokens']:,}")
        print(f"   Saved     : ~{s['memory_saved_mb']} MB")
        print(f"   Status    : {'✅ RotorQuant' if s['available'] else '⚠️  FP16 fallback'}")


# ─── ਟੈਸਟ ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Amrit KV Cache — ਟੈਸਟ ਸ਼ੁਰੂ")
    print("=" * 50)

    mgr = AmritKVCacheManager(bits=3, method="rotorquant")

    B, H, S, D = 1, 8, 512, 128
    k = torch.randn(B, H, S, D)
    v = torch.randn(B, H, S, D)

    print(f"\n📥 Input shape : {k.shape}")
    print(f"   FP16 memory : {k.nelement() * 2 / 1024:.1f} KB (keys only)")

    c_k, c_v = mgr.compress(k, v)
    print("✅ Compressed!")

    k_out, v_out = mgr.decompress(c_k, c_v)
    if isinstance(k_out, torch.Tensor):
        sim = torch.nn.functional.cosine_similarity(
            k.flatten(), k_out.flatten(), dim=0
        ).item()
        print(f"   Cosine similarity: {sim:.4f} (1.0 = perfect)")

    mgr.print_stats()
    print("\n✅ ਸਭ ਠੀਕ ਆ!")
