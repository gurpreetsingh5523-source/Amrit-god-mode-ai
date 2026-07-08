"""
Screen Control — pyautogui + LLaVA vision for full Mac system control.

Capabilities:
  - screenshot() → capture screen
  - understand_screen() → send screenshot to LLaVA, get description + action plan
  - click(x, y) / click_text(label) → mouse control
  - type_text(text) → keyboard input
  - open_app(name) → launch any macOS app
  - run_shortcut(keys) → keyboard shortcuts
  - scroll(direction, amount)
  - find_and_click(description) → vision-guided click (screenshot → LLaVA → click coords)
  - do_goal_on_screen(goal) → fully autonomous: see screen, plan, act
"""

import asyncio
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("ScreenControl")

SCREENSHOT_DIR = Path("workspace/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# LLaVA model available in Ollama
VISION_MODEL = "llava:7b"


# ── Screenshot ────────────────────────────────────────────────

def screenshot(label: str = "") -> str:
    """Capture full screen, return saved path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = label.replace(" ", "_")[:20] if label else "screen"
    path = str(SCREENSHOT_DIR / f"{slug}_{ts}.png")
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img.save(path)
        logger.info(f"Screenshot → {path}")
        return path
    except ImportError:
        # macOS fallback: screencapture
        subprocess.run(["screencapture", "-x", path], check=True)
        return path
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        # macOS native fallback
        try:
            subprocess.run(["screencapture", "-x", path], check=True)
            return path
        except Exception:
            return ""


# ── LLaVA Vision ─────────────────────────────────────────────

async def understand_screen(path: str = "", goal: str = "") -> dict:
    """
    Send screenshot to LLaVA via Ollama. Returns:
      description, active_app, suggested_actions, answer_to_goal
    """
    if not path:
        path = screenshot("understand")
    if not path or not Path(path).exists():
        return {"error": "No screenshot available"}

    prompt = (
        f"You are controlling a Mac computer. Look at this screenshot carefully.\n"
        f"1. What application/window is currently active?\n"
        f"2. What is visible on screen? (menus, buttons, text, dialogs)\n"
        f"3. What is the current state? (idle, loading, error, form, etc)\n"
    )
    if goal:
        prompt += f"4. To achieve the goal: '{goal}' — what exact steps should be taken? List them numbered."

    try:
        import ollama as ollama_client
        import base64

        with open(path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        response = ollama_client.chat(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [img_b64]
            }]
        )
        text = response["message"]["content"]
        return {
            "description": text,
            "screenshot": path,
            "goal": goal,
            "model": VISION_MODEL
        }
    except ImportError:
        return {"error": "ollama package not installed: pip install ollama"}
    except Exception as e:
        # LLaVA not available — use metadata description
        logger.warning(f"LLaVA unavailable: {e} — using basic screen info")
        return {
            "description": f"Screenshot taken at {path}. LLaVA not available: {e}",
            "screenshot": path,
            "fallback": True
        }


# ── Mouse & Keyboard Control ──────────────────────────────────

def click(x: int, y: int, button: str = "left", clicks: int = 1):
    """Click at screen coordinates."""
    try:
        import pyautogui
        pyautogui.PAUSE = 0.3
        pyautogui.click(x, y, button=button, clicks=clicks)
        logger.info(f"Clicked ({x}, {y}) [{button}]")
        return True
    except Exception as e:
        logger.error(f"Click failed: {e}")
        return False


def double_click(x: int, y: int):
    return click(x, y, clicks=2)


def right_click(x: int, y: int):
    return click(x, y, button="right")


def move_to(x: int, y: int, duration: float = 0.3):
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        return True
    except Exception as e:
        logger.error(f"Move failed: {e}")
        return False


def type_text(text: str, interval: float = 0.03):
    """Type text with natural interval."""
    try:
        import pyautogui
        time.sleep(0.2)
        pyautogui.write(text, interval=interval)
        return True
    except Exception as e:
        # Fallback: use pbcopy + cmd+v
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(text.encode())
            run_shortcut("command", "v")
            return True
        except Exception as e2:
            logger.error(f"Type failed: {e}, {e2}")
            return False


def run_shortcut(*keys):
    """Press keyboard shortcut. e.g. run_shortcut('command','c')"""
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.error(f"Shortcut {keys} failed: {e}")
        return False


def press_key(key: str):
    try:
        import pyautogui
        pyautogui.press(key)
        return True
    except Exception as e:
        logger.error(f"Key press {key} failed: {e}")
        return False


def scroll(direction: str = "down", amount: int = 3):
    try:
        import pyautogui
        clicks = -amount if direction == "down" else amount
        pyautogui.scroll(clicks)
        return True
    except Exception as e:
        logger.error(f"Scroll failed: {e}")
        return False


def drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
    try:
        import pyautogui
        pyautogui.drag(x1 - pyautogui.position().x,
                       y1 - pyautogui.position().y, duration=duration)
        return True
    except Exception as e:
        logger.error(f"Drag failed: {e}")
        return False


# ── App Control ───────────────────────────────────────────────

def open_app(name: str) -> bool:
    """Open any macOS application by name."""
    try:
        result = subprocess.run(["open", "-a", name], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Opened app: {name}")
            time.sleep(1.5)
            return True
        # Try Spotlight
        subprocess.Popen(["open", "-a", "Spotlight"])
        time.sleep(0.3)
        return False
    except Exception as e:
        logger.error(f"Open app {name} failed: {e}")
        return False


def get_active_app() -> str:
    """Return name of currently active macOS app."""
    try:
        script = 'tell application "System Events" to get name of first application process whose frontmost is true'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return "unknown"


def run_applescript(script: str) -> str:
    """Execute AppleScript for deep macOS control."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr}"
    except Exception as e:
        return f"AppleScript error: {e}"


def set_volume(level: int):
    """Set system volume 0-100."""
    run_applescript(f"set volume output volume {level}")


def show_notification(title: str, message: str):
    """Show macOS notification."""
    script = f'display notification "{message}" with title "{title}"'
    run_applescript(script)


def get_screen_size() -> tuple:
    try:
        import pyautogui
        return pyautogui.size()
    except Exception:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True
        )
        return (1920, 1080)  # fallback


# ── Autonomous Vision-Guided Action ──────────────────────────

async def find_and_click(description: str) -> dict:
    """
    Take screenshot → ask LLaVA where the element is → click it.
    Returns {success, message, screenshot}
    """
    path = screenshot(f"find_{description[:15]}")
    vision = await understand_screen(
        path,
        goal=f"Find the UI element: '{description}'. Return ONLY: FOUND:x,y or NOTFOUND"
    )
    desc = vision.get("description", "")

    if "FOUND:" in desc:
        try:
            coords = desc.split("FOUND:")[1].strip().split(",")
            x, y = int(coords[0].strip()), int(coords[1].strip())
            click(x, y)
            return {"success": True, "message": f"Clicked {description} at ({x},{y})", "screenshot": path}
        except Exception as e:
            return {"success": False, "message": f"Parse coords failed: {e}", "screenshot": path}
    return {"success": False, "message": f"Element not found: {description}", "screenshot": path}


async def do_goal_on_screen(goal: str, max_steps: int = 5) -> dict:
    """
    Fully autonomous screen goal execution.
    Loop: screenshot → LLaVA understand → plan action → execute → repeat until done.
    """
    logger.info(f"Screen goal: {goal!r}")
    history = []

    for step in range(max_steps):
        path = screenshot(f"step{step}")
        vision = await understand_screen(path, goal=goal)
        description = vision.get("description", "")

        logger.info(f"Step {step+1}: {description[:100]}")
        history.append({"step": step + 1, "vision": description, "screenshot": path})

        # Check if done
        if any(word in description.lower() for word in ["complete", "done", "finished", "success"]):
            return {"success": True, "steps": step + 1, "history": history}

        # Parse action from LLaVA response
        action_taken = await _execute_vision_action(description, goal)
        history[-1]["action"] = action_taken
        time.sleep(0.8)

    return {"success": False, "reason": "max_steps reached", "history": history}


async def _execute_vision_action(llava_response: str, goal: str) -> str:
    """Parse LLaVA instructions and execute them."""
    resp_lower = llava_response.lower()

    if "click" in resp_lower:
        # Extract click target from response
        import re
        coords = re.findall(r'click.*?(\d+).*?(\d+)', resp_lower)
        if coords:
            x, y = int(coords[0][0]), int(coords[0][1])
            click(x, y)
            return f"Clicked ({x}, {y})"

    if "type" in resp_lower or "enter" in resp_lower:
        import re
        quoted = re.findall(r'"([^"]+)"', llava_response)
        if quoted:
            type_text(quoted[0])
            return f"Typed: {quoted[0]}"

    if "open" in resp_lower:
        import re
        apps = re.findall(r'open\s+([A-Z][a-zA-Z\s]+)', llava_response)
        if apps:
            open_app(apps[0].strip())
            return f"Opened: {apps[0]}"

    if "command" in resp_lower or "shortcut" in resp_lower:
        if "command+c" in resp_lower or "copy" in resp_lower:
            run_shortcut("command", "c")
            return "Copied"
        if "command+v" in resp_lower or "paste" in resp_lower:
            run_shortcut("command", "v")
            return "Pasted"
        if "command+space" in resp_lower or "spotlight" in resp_lower:
            run_shortcut("command", "space")
            return "Opened Spotlight"

    return "observed"


# ── Quick Actions ─────────────────────────────────────────────

def spotlight_search(query: str):
    """Open Spotlight and search."""
    run_shortcut("command", "space")
    time.sleep(0.5)
    type_text(query)
    time.sleep(0.5)
    press_key("return")


def take_screenshot_and_show() -> str:
    """Take screenshot and open in Preview."""
    path = screenshot("preview")
    if path:
        subprocess.Popen(["open", path])
    return path
