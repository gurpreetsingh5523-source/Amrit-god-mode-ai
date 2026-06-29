#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMRIT GODMODE - Reverse Engineering Agent
ਇਹ Agent Binaries (EXE, ELF, APK, Mach-O) ਦਾ Static & Dynamic Analysis ਕਰਦਾ ਹੈ।
Orchestrator, Sandbox, Memory, ਤੇ Ethical Guard ਨਾਲ ਪੂਰੀ ਤਰ੍ਹਾਂ ਇੰਟੀਗ੍ਰੇਟਿਡ।
"""

import os
import sys
import subprocess
import tempfile
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# ============================================================
# 1. OPTIONAL LIBRARIES (Safe Import)
# ============================================================
try:
    import pefile  # Windows PE (EXE/DLL)
except ImportError:
    pefile = None

try:
    from elftools.elf.elffile import ELFFile  # Linux ELF
    from elftools.elf.sections import SymbolTableSection
except ImportError:
    ELFFile = None

try:
    from capstone import Cs, CS_ARCH_X86, CS_ARCH_ARM64, CS_MODE_64, CS_MODE_32
except ImportError:
    Cs = None

try:
    from androguard.core.bytecodes.apk import APK  # Android APK
    from androguard.core.bytecodes.dvm import DalvikVMFormat
except ImportError:
    APK = None

# ============================================================
# 2. LOGGING SETUP
# ============================================================
logger = logging.getLogger("Amrit.ReverseAgent")
logger.setLevel(logging.INFO)


# ============================================================
# 3. REVERSE AGENT CLASS
# ============================================================
class ReverseAgent:
    """
    AMRIT ਦਾ Reverse Engineering Agent।
    ਇਹ Binary Files ਨੂੰ ਪੜ੍ਹਦਾ, Disassemble ਕਰਦਾ, Strings ਚੋਰੀ ਕਰਦਾ, ਤੇ APK/EXE ਦਾ Analysis ਕਰਦਾ ਹੈ।
    """

    def __init__(self, config: Dict[str, Any] = None, sandbox=None, memory=None, ethical_guard=None):
        """
        Args:
            config: config.yaml ਤੋਂ ਪੂਰਾ config dict (ਖਾਸ ਕਰਕੇ 'reverse_agent' ਸੈਕਸ਼ਨ)
            sandbox: godmode/core/sandbox.py ਦਾ Sandbox instance
            memory: Memory Stack (Context/Vector memory ਲਈ)
            ethical_guard: EthicalGuard instance (ਮਾਲਵੇਅਰ ਚੈਕ ਕਰਨ ਲਈ)
        """
        self.config = (config or {}).get("reverse_agent", {})
        self.sandbox = sandbox
        self.memory = memory
        self.ethical_guard = ethical_guard

        # Limits
        self.max_file_size = self.config.get("max_file_size", 50 * 1024 * 1024)  # 50MB
        self.timeout = self.config.get("timeout", 60)

        # Supported types
        self.supported_extensions = [".exe", ".dll", ".elf", ".so", ".apk", ".a", ".o", ".bin", ".hex", ".class"]
        self.magic_headers = {
            b"MZ": "PE32",
            b"\x7fELF": "ELF",
            b"PK\x03\x04": "ZIP/APK",
            b"\xca\xfe\xba\xbe": "Mach-O (32-bit)",
            b"\xbe\xba\xfe\xca": "Mach-O (64-bit)",
            b"\xde\xc0\x17\x0b": "Java Class",
        }

        logger.info("ReverseAgent initialized successfully.")

    # ============================================================
    # 4. MAIN EXECUTE METHOD (Orchestrator ਇਸਨੂੰ call ਕਰੇਗਾ)
    # ============================================================
    def execute(self, task: str, file_path: str = None, hex_dump: str = None, **kwargs) -> Dict[str, Any]:
        """
        Orchestrator ਤੋਂ ਆਉਣ ਵਾਲਾ ਮੁੱਖ entry point।

        Args:
            task: "analyze_binary", "disassemble_hex", "extract_strings", "analyze_apk"
            file_path: Local file path (or URL)
            hex_dump: Raw hex string (for disassembly)
        """
        # --- Ethical Guard Check (optional / adapter-tolerant) ---
        if self.ethical_guard is not None and hasattr(self.ethical_guard, "is_safe_target"):
            if not self.ethical_guard.is_safe_target(file_path, task):
                return {"status": "blocked", "reason": "EthicalGuard: Malicious or restricted target detected."}

        # --- Route Task ---
        if task == "analyze_binary" and file_path:
            return self._analyze_binary(file_path)
        elif task == "disassemble_hex" and hex_dump:
            return self._disassemble_hex(hex_dump, arch=kwargs.get("arch", "x86_64"))
        elif task == "extract_strings" and file_path:
            return self._extract_strings(file_path)
        elif task == "analyze_apk" and file_path:
            return self._analyze_apk(file_path)
        elif task == "full_recon" and file_path:
            return self._full_recon(file_path)
        else:
            return {"status": "error", "message": "Invalid task or missing file_path/hex_dump."}

    # ============================================================
    # 5. BINARY DETECTION & ANALYSIS
    # ============================================================
    def _detect_type(self, file_path: str) -> str:
        """Magic bytes ਨਾਲ file type ਪਤਾ ਕਰੋ"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
            for magic, ftype in self.magic_headers.items():
                if header.startswith(magic):
                    return ftype
            return "Unknown"
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return "Error"

    def _mem(self, method: str, **kwargs):
        """Memory adapter — call it only if the backend supports it."""
        if self.memory is not None and hasattr(self.memory, method):
            try:
                getattr(self.memory, method)(**kwargs)
            except Exception:
                pass

    def _analyze_binary(self, file_path: str) -> Dict[str, Any]:
        """PE/ELF/Mach-O ਦਾ ਪੂਰਾ static analysis"""
        if not os.path.exists(file_path):
            return {"status": "error", "message": "File not found."}

        if os.path.getsize(file_path) > self.max_file_size:
            return {"status": "error", "message": "File exceeds max size limit."}

        result = {
            "status": "success",
            "file": file_path,
            "hash_md5": hashlib.md5(open(file_path, "rb").read()).hexdigest(),
            "file_type": self._detect_type(file_path),
            "sections": [],
            "imports": [],
            "exports": [],
            "entry_point": None,
            "analysis_details": {}
        }

        # --- PE (Windows) ---
        if result["file_type"] == "PE32" and pefile:
            try:
                pe = pefile.PE(file_path)
                result["entry_point"] = hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint)
                for section in pe.sections:
                    result["sections"].append({
                        "name": section.Name.decode().strip('\x00'),
                        "virtual_size": hex(section.Misc_VirtualSize),
                        "raw_size": hex(section.SizeOfRawData)
                    })
                if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                    for entry in pe.DIRECTORY_ENTRY_IMPORT:
                        for imp in entry.imports:
                            result["imports"].append(imp.name.decode() if imp.name else "ordinal")
            except Exception as e:
                result["analysis_details"]["pe_error"] = str(e)

        # --- ELF (Linux) ---
        elif result["file_type"] == "ELF" and ELFFile:
            try:
                with open(file_path, "rb") as f:
                    elf = ELFFile(f)
                    result["entry_point"] = hex(elf.header.e_entry)
                    for section in elf.iter_sections():
                        if section.name:
                            result["sections"].append({
                                "name": section.name,
                                "type": hex(section.header.sh_type)
                            })
            except Exception as e:
                result["analysis_details"]["elf_error"] = str(e)

        # --- APK (Android) ---
        elif result["file_type"] == "ZIP/APK" and APK:
            return self._analyze_apk(file_path)

        # --- Store in Memory ---
        self._mem("store_episodic", context="reverse_binary",
                  content=f"Analyzed {file_path}: {len(result['sections'])} sections found.")

        return result

    # ============================================================
    # 6. HEX DISASSEMBLY (Capstone Engine)
    # ============================================================
    def _disassemble_hex(self, hex_dump: str, arch: str = "x86_64") -> Dict[str, Any]:
        """Raw Hex ਨੂੰ Assembly Instructions ਵਿੱਚ ਬਦਲੋ"""
        if not Cs:
            return {"status": "error", "message": "Capstone library not installed. Run: pip install capstone"}

        try:
            raw_bytes = bytes.fromhex(hex_dump.replace(" ", ""))
        except ValueError:
            return {"status": "error", "message": "Invalid hex string."}

        # Architecture selection
        if arch == "x86_64":
            md = Cs(CS_ARCH_X86, CS_MODE_64)
        elif arch == "x86":
            md = Cs(CS_ARCH_X86, CS_MODE_32)
        elif arch == "arm64":
            md = Cs(CS_ARCH_ARM64, CS_MODE_64)
        else:
            md = Cs(CS_ARCH_X86, CS_MODE_64)

        instructions = []
        for i in md.disasm(raw_bytes, 0x1000):
            instructions.append({
                "address": hex(i.address),
                "mnemonic": i.mnemonic,
                "op_str": i.op_str,
                "size": i.size
            })

        self._mem("store_context", key="last_disassembly",
                  value={"arch": arch, "count": len(instructions)})

        return {
            "status": "success",
            "architecture": arch,
            "instruction_count": len(instructions),
            "instructions": instructions[:100]  # ਪਹਿਲੇ 100 instructions
        }

    # ============================================================
    # 7. STRING EXTRACTION (Binutils strings)
    # ============================================================
    def _extract_strings(self, file_path: str, min_len: int = 4) -> Dict[str, Any]:
        """Binary 'ਚੋਂ human-readable strings ਕੱਢੋ"""
        if not os.path.exists(file_path):
            return {"status": "error", "message": "File not found."}

        strings_list = []
        try:
            # Method 1: Pure Python
            with open(file_path, "rb") as f:
                data = f.read()
                current = ""
                for b in data:
                    if 32 <= b <= 126:
                        current += chr(b)
                    else:
                        if len(current) >= min_len:
                            strings_list.append(current)
                        current = ""
                if len(current) >= min_len:
                    strings_list.append(current)

            # Method 2: External `strings` command (ਜੇਕਰ system 'ਚ available)
            try:
                output = subprocess.check_output(
                    ["strings", "-n", str(min_len), file_path],
                    timeout=10, stderr=subprocess.DEVNULL
                )
                external_strings = output.decode("utf-8", errors="ignore").splitlines()
                if len(external_strings) > len(strings_list):
                    strings_list = external_strings
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass  # Use Python method

            # Flag potentially sensitive tokens (defensive review aid)
            sensitive = [s for s in strings_list if any(k in s.lower() for k in ["api", "key", "pass", "token", "secret", "admin"])]

            return {
                "status": "success",
                "total_strings": len(strings_list),
                "top_20_strings": strings_list[:20],
                "sensitive_strings": sensitive[:10],
                "file": file_path
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ============================================================
    # 8. ANDROID APK ANALYSIS
    # ============================================================
    def _analyze_apk(self, file_path: str) -> Dict[str, Any]:
        """Android APK (DEX + Manifest) ਪੂਰਾ scan"""
        if not APK:
            return {"status": "error", "message": "Androguard not installed. Run: pip install androguard"}

        try:
            apk = APK(file_path)
            result = {
                "status": "success",
                "package": apk.get_package(),
                "app_name": apk.get_app_name(),
                "version": apk.get_androidversion_name(),
                "permissions": apk.get_permissions(),
                "main_activity": apk.get_main_activity(),
                "activities": apk.get_activities(),
                "services": apk.get_services(),
                "receivers": apk.get_receivers(),
                "libraries": apk.get_libraries(),
                "files": apk.get_files()[:20],
                "malicious_score": self._check_apk_risk(apk)
            }

            self._mem("store_vector", context="apk_analysis",
                      embedding=result["package"], metadata=result)

            return result

        except Exception as e:
            return {"status": "error", "message": f"APK parse error: {str(e)}"}

    def _check_apk_risk(self, apk) -> int:
        """Basic risk score (0-10) ਓਨਾ 'ਚ ਕਿੰਨਾ ਖ਼ਤਰਨਾਕ"""
        risk = 0
        suspicious_perms = ["READ_SMS", "RECORD_AUDIO", "CAMERA", "READ_CONTACTS", "INSTALL_PACKAGES"]
        perms = apk.get_permissions()
        for sp in suspicious_perms:
            if any(sp in p for p in perms):
                risk += 1
        return min(risk, 10)

    # ============================================================
    # 9. FULL RECONNAISSANCE (All-in-one)
    # ============================================================
    def _full_recon(self, file_path: str) -> Dict[str, Any]:
        """Strings + Binary Analysis + Type detection ਇੱਕੋ ਵਾਰ"""
        result = {
            "status": "success",
            "binary_analysis": self._analyze_binary(file_path),
            "strings": self._extract_strings(file_path),
        }

        # APK ਜੇਕਰ ਹੈ ਤਾਂ details merge
        if result["binary_analysis"].get("file_type") == "ZIP/APK":
            result["apk_details"] = self._analyze_apk(file_path)

        # Sandbox 'ਚ dynamic analysis (safe execution) - ਜੇਕਰ execute permission ਹੈ
        if self.sandbox and self.config.get("allow_dynamic", False) and hasattr(self.sandbox, "run_secure"):
            try:
                output = self.sandbox.run_secure(cmd=f"file '{file_path}'", timeout=5)
                result["sandbox_output"] = output
            except Exception as e:
                result["sandbox_error"] = str(e)

        return result


# ============================================================
# 10. STANDALONE TEST (ਜੇਕਰ ਇਸ ਫਾਈਲ ਨੂੰ ਸਿੱਧਾ ਚਲਾਓ)
# ============================================================
if __name__ == "__main__":
    config = {"reverse_agent": {"max_file_size": 50000000, "timeout": 60, "allow_dynamic": False}}
    agent = ReverseAgent(config)

    # Test 1: Hex Disassembly (x64 NOP slide)
    result = agent.execute("disassemble_hex", hex_dump="90 90 90 48 31 C0")
    print("Disassembly:", result.get("instruction_count"), "instructions")
    for ins in result.get("instructions", []):
        print(f"   {ins['address']}: {ins['mnemonic']} {ins['op_str']}")

    # Test 2: Strings (ਆਪਣੀ ਖੁਦ ਦੀ .py file 'ਤੇ test)
    result = agent.execute("extract_strings", file_path=__file__)
    print("Strings Found:", result.get("total_strings"))
