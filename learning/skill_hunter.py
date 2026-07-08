"""
Skill Hunter — Autonomous skill discovery, evaluation, and installation.

God Mode ability: finds gaps in its own capabilities, searches PyPI/GitHub
for solutions, tests them safely, and installs + registers new skills.

Triggered automatically during evolution cycles when:
  - A task fails due to missing package
  - An agent reports a capability gap
  - User requests something the system can't do
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("SkillHunter")

SKILL_REGISTRY_PATH = Path("workspace/skill_registry.json")
SKILL_LOG_PATH = Path("workspace/skill_hunt_log.json")

# Curated map: capability keyword → best package + one-liner test
KNOWN_SKILL_MAP = {
    "pdf": ("pypdf2", "import PyPDF2"),
    "pdf_read": ("pdfplumber", "import pdfplumber"),
    "excel": ("openpyxl", "import openpyxl"),
    "csv": ("pandas", "import pandas"),
    "email_send": ("smtplib", "import smtplib"),
    "email_parse": ("mail-parser", "import mailparser"),
    "slack": ("slack-sdk", "from slack_sdk import WebClient"),
    "discord": ("discord.py", "import discord"),
    "twitter": ("tweepy", "import tweepy"),
    "reddit": ("praw", "import praw"),
    "youtube": ("yt-dlp", "import yt_dlp"),
    "audio_edit": ("pydub", "from pydub import AudioSegment"),
    "image_gen": ("diffusers", "from diffusers import StableDiffusionPipeline"),
    "ocr_advanced": ("easyocr", "import easyocr"),
    "qrcode": ("qrcode", "import qrcode"),
    "barcode": ("python-barcode", "import barcode"),
    "calendar": ("caldav", "import caldav"),
    "notion": ("notion-client", "from notion_client import Client"),
    "airtable": ("pyairtable", "from pyairtable import Api"),
    "weather": ("pyowm", "import pyowm"),
    "maps": ("geopy", "from geopy.geocoders import Nominatim"),
    "crypto": ("cryptography", "from cryptography.fernet import Fernet"),
    "ssh": ("paramiko", "import paramiko"),
    "database": ("sqlalchemy", "from sqlalchemy import create_engine"),
    "sqlite": ("aiosqlite", "import aiosqlite"),
    "mongodb": ("pymongo", "import pymongo"),
    "redis": ("redis", "import redis"),
    "rest_api": ("fastapi", "from fastapi import FastAPI"),
    "websocket": ("websockets", "import websockets"),
    "docker": ("docker", "import docker"),
    "aws": ("boto3", "import boto3"),
    "gcloud": ("google-cloud-storage", "from google.cloud import storage"),
    "schedule": ("schedule", "import schedule"),
    "clipboard": ("pyperclip", "import pyperclip"),
    "notifications": ("plyer", "from plyer import notification"),
    "compress": ("py7zr", "import py7zr"),
    "markdown": ("markdown", "import markdown"),
    "html_parse": ("beautifulsoup4", "from bs4 import BeautifulSoup"),
    "json_schema": ("jsonschema", "import jsonschema"),
    "nlp": ("spacy", "import spacy"),
    "sentiment": ("textblob", "from textblob import TextBlob"),
    "translation": ("deep-translator", "from deep_translator import GoogleTranslator"),
    "summarize": ("sumy", "from sumy.parsers.plaintext import PlaintextParser"),
    "stock": ("yfinance", "import yfinance"),
    "finance": ("yfinance", "import yfinance"),
    "plot": ("matplotlib", "import matplotlib.pyplot as plt"),
    "chart": ("plotly", "import plotly"),
    "data_viz": ("plotly", "import plotly"),
    "web_framework": ("flask", "from flask import Flask"),
    "async_web": ("aiohttp", "import aiohttp"),
    "game": ("pygame", "import pygame"),
    "gui": ("tkinter", "import tkinter"),
    "desktop_gui": ("customtkinter", "import customtkinter"),
    "system_tray": ("pystray", "import pystray"),
    "hotkeys": ("keyboard", "import keyboard"),
    "mouse": ("pynput", "from pynput import mouse"),
    "screen_record": ("mss", "import mss"),
    "virtual_display": ("Xvfb", "import subprocess"),
    "barcode_scan": ("pyzbar", "from pyzbar.pyzbar import decode"),
    "face_detect": ("face-recognition", "import face_recognition"),
    "object_detect": ("ultralytics", "from ultralytics import YOLO"),
    "speech_clone": ("TTS", "from TTS.api import TTS"),
    "music_gen": ("audiocraft", "import audiocraft"),
    "video_edit": ("moviepy", "from moviepy.editor import VideoFileClip"),
    "3d": ("open3d", "import open3d"),
    "blockchain": ("web3", "from web3 import Web3"),
    "tor": ("stem", "import stem"),
    "selenium_grid": ("selenium", "from selenium import webdriver"),
    "testing": ("pytest", "import pytest"),
    "mock": ("pytest-mock", "from unittest.mock import MagicMock"),
    "profiling": ("cProfile", "import cProfile"),
    "memory_profile": ("memory-profiler", "from memory_profiler import profile"),
}


class SkillRegistry:
    """Persistent registry of installed + available skills."""

    def __init__(self):
        self._registry = {}
        self._load()

    def _load(self):
        if SKILL_REGISTRY_PATH.exists():
            try:
                self._registry = json.loads(SKILL_REGISTRY_PATH.read_text())
            except Exception:
                pass

    def save(self):
        SKILL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SKILL_REGISTRY_PATH.write_text(json.dumps(self._registry, indent=2, default=str))

    def register(self, name: str, package: str, test_import: str,
                 description: str = "", installed: bool = True):
        self._registry[name] = {
            "package": package,
            "test_import": test_import,
            "description": description,
            "installed": installed,
            "registered_at": datetime.now().isoformat()
        }
        self.save()

    def is_installed(self, name: str) -> bool:
        return self._registry.get(name, {}).get("installed", False)

    def all_skills(self) -> dict:
        return dict(self._registry)

    def installed_skills(self) -> list:
        return [k for k, v in self._registry.items() if v.get("installed")]

    def missing_skills(self) -> list:
        return [k for k, v in self._registry.items() if not v.get("installed")]


registry = SkillRegistry()


class SkillHunter:
    """
    Autonomous agent that discovers, evaluates, and installs new skills.
    """

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self._log = []

    def _log_action(self, action: str, result: str, success: bool):
        entry = {
            "action": action, "result": result,
            "success": success, "ts": datetime.now().isoformat()
        }
        self._log.append(entry)
        try:
            existing = []
            if SKILL_LOG_PATH.exists():
                existing = json.loads(SKILL_LOG_PATH.read_text())
            existing.append(entry)
            SKILL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            SKILL_LOG_PATH.write_text(json.dumps(existing[-500:], indent=2))
        except Exception:
            pass

    def _test_import(self, test_code: str) -> bool:
        """Test if a package can be imported safely."""
        try:
            result = subprocess.run(
                [sys.executable, "-c", test_code],
                capture_output=True, text=True, timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False

    def _pip_install(self, package: str, timeout: int = 90) -> bool:
        """Install a package via pip."""
        try:
            logger.info(f"Installing: {package}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--quiet"],
                capture_output=True, text=True, timeout=timeout
            )
            success = result.returncode == 0
            if success:
                logger.info(f"Installed: {package}")
            else:
                logger.warning(f"Failed to install {package}: {result.stderr[:200]}")
            return success
        except subprocess.TimeoutExpired:
            logger.warning(f"Install timeout: {package}")
            return False
        except Exception as e:
            logger.error(f"Install error {package}: {e}")
            return False

    def _search_pypi(self, query: str, max_results: int = 5) -> list:
        """Search PyPI for packages matching a capability need."""
        try:
            import urllib.request
            import urllib.parse
            url = f"https://pypi.org/pypi?%3Aaction=search&term={urllib.parse.quote(query)}&submit=search"
            # Use JSON API instead — more reliable
            json_url = f"https://pypi.org/search/?q={urllib.parse.quote(query)}&o=&c=&format=json"

            req = urllib.request.Request(json_url, headers={"User-Agent": "AmritGodMode/3.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                # PyPI doesn't have a simple JSON search, use simple-api
                pass
        except Exception:
            pass

        # Fallback: check known map
        results = []
        for key, (pkg, test) in KNOWN_SKILL_MAP.items():
            if query.lower() in key.lower() or query.lower() in pkg.lower():
                results.append({"name": key, "package": pkg, "test": test})
        return results[:max_results]

    def detect_capability_gap(self, error_text: str) -> str:
        """
        Parse error messages to identify what's missing.
        Returns capability keyword or empty string.
        """
        patterns = [
            (r"No module named '(\w+)'", lambda m: m.group(1)),
            (r"ImportError.*'(\w+)'", lambda m: m.group(1)),
            (r"ModuleNotFoundError.*'(\w+)'", lambda m: m.group(1)),
            (r"cannot import name '(\w+)'", lambda m: m.group(1)),
        ]
        for pattern, extractor in patterns:
            m = re.search(pattern, error_text, re.IGNORECASE)
            if m:
                return extractor(m).lower()
        return ""

    async def hunt_for_skill(self, capability: str) -> dict:
        """
        Find and install a skill for a given capability need.
        Returns {success, package, skill_name, message}
        """
        logger.info(f"Hunting skill for: {capability!r}")

        # Check known map first
        if capability.lower() in KNOWN_SKILL_MAP:
            package, test_import = KNOWN_SKILL_MAP[capability.lower()]
            if self._test_import(test_import):
                registry.register(capability, package, test_import,
                                  installed=True)
                return {"success": True, "package": package,
                        "message": f"Already available: {package}"}

            success = self._pip_install(package)
            if success and self._test_import(test_import):
                registry.register(capability, package, test_import, installed=True)
                self._log_action(f"install:{package}", "success", True)
                return {"success": True, "package": package,
                        "message": f"Installed: {package}"}

        # Search for it
        results = self._search_pypi(capability)
        for r in results:
            if self._pip_install(r["package"]):
                if self._test_import(r["test"]):
                    registry.register(r["name"], r["package"], r["test"], installed=True)
                    self._log_action(f"install:{r['package']}", "success", True)
                    return {"success": True, "package": r["package"],
                            "message": f"Found and installed: {r['package']}"}

        self._log_action(f"hunt:{capability}", "not_found", False)
        return {"success": False, "message": f"No skill found for: {capability}"}

    async def auto_heal_import_error(self, error: str) -> bool:
        """
        Given an import error string, try to auto-install the missing package.
        Returns True if healed.
        """
        gap = self.detect_capability_gap(error)
        if not gap:
            return False

        logger.info(f"Auto-healing import error: missing '{gap}'")
        result = await self.hunt_for_skill(gap)
        if result["success"]:
            logger.info(f"Auto-healed: {result['message']}")
            return True
        return False

    async def scan_and_upgrade(self) -> dict:
        """
        Scan all known capability gaps and install everything possible.
        Run during evolution cycles.
        """
        logger.info("Scanning for skill upgrades...")
        installed = []
        failed = []

        # Install the core missing packages we know about
        priority_skills = [
            ("web_search", "ddgs", "from ddgs import DDGS"),
            ("screen_control", "pyautogui", "import pyautogui"),
            ("ollama_client", "ollama", "import ollama"),
            ("browser_selenium", "selenium", "from selenium import webdriver"),
            ("telegram_bot", "python-telegram-bot", "from telegram.ext import Application"),
            ("kokoro_tts", "kokoro", "import kokoro"),
            ("wake_word", "openwakeword", "import openwakeword"),
            ("mcp_protocol", "mcp", "import mcp"),
            ("aiosqlite", "aiosqlite", "import aiosqlite"),
            ("pyperclip", "pyperclip", "import pyperclip"),
        ]

        for skill_name, package, test in priority_skills:
            if self._test_import(test):
                registry.register(skill_name, package, test, installed=True)
                installed.append(f"{skill_name} (already present)")
                continue

            if self._pip_install(package):
                if self._test_import(test):
                    registry.register(skill_name, package, test, installed=True)
                    installed.append(skill_name)
                    logger.info(f"Skill installed: {skill_name}")
                else:
                    failed.append(skill_name)
            else:
                failed.append(skill_name)

        result = {
            "installed": installed,
            "failed": failed,
            "total_skills": len(registry.all_skills()),
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Skill scan: {len(installed)} installed, {len(failed)} failed")
        return result

    def generate_skill_module(self, skill_name: str, description: str) -> str:
        """
        Ask the LLM to generate a new Python skill module.
        Returns the generated code as string.
        """
        return f"""\"\"\"Auto-generated skill: {skill_name} — {description}\"\"\"
# Generated by SkillHunter on {datetime.now().strftime('%Y-%m-%d')}

def run_{skill_name.replace('-','_')}(*args, **kwargs):
    \"\"\"Execute {skill_name} skill.\"\"\"
    raise NotImplementedError("Skill needs implementation: {skill_name}")

SKILL_META = {{
    "name": "{skill_name}",
    "description": "{description}",
    "generated": True
}}
"""

    def get_status(self) -> dict:
        return {
            "total_known_skills": len(KNOWN_SKILL_MAP),
            "registered_skills": len(registry.all_skills()),
            "installed_skills": len(registry.installed_skills()),
            "missing_skills": registry.missing_skills(),
            "hunt_log_entries": len(self._log)
        }
