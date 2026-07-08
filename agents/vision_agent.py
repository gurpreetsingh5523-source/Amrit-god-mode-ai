"""Vision Agent — Image description, OCR, video frames, object detection, LLaVA screen understanding."""
import base64
from pathlib import Path
from base_agent import BaseAgent
from visual_memory import VisualMemory

class VisionAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("VisionAgent", eb, state)
        self.vmem = VisualMemory()

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "describe")
        source = d.get("source", "")
        await self.report(f"Vision [{action}]: {source}")
        if action == "describe":
            return await self._describe(source)
        if action == "ocr":
            return await self._ocr(source)
        if action == "frames":
            return await self._frames(source, d.get("fps", 1))
        if action == "detect":
            return await self._detect(source)
        if action == "recall":
            return self.ok(observations=self.vmem.search(d.get("query", "")))
        if action == "screenshot":
            return await self._screenshot_and_understand(d.get("goal", ""))
        if action == "screen_goal":
            return await self._screen_goal(d.get("goal", source))
        if action == "llava":
            return await self._llava_describe(source, d.get("prompt", ""))
        return await self._describe(source)

    async def _describe(self, path: str) -> dict:
        if not Path(path).exists():
            return self.err(f"Not found: {path}")
        try:
            from PIL import Image
            img  = Image.open(path)
            info = {"size": img.size, "mode": img.mode, "format": img.format}
            desc = await self.ask_llm(f"Describe this image. Format:{img.format} Size:{img.size}")
            self.vmem.store(desc, path)
            return self.ok(image=path, metadata=info, description=desc)
        except ImportError:
            return self.err("Pillow required: pip install Pillow")
        except Exception as e:
            return self.err(str(e))

    async def _ocr(self, path: str) -> dict:
        try:
            from PIL import Image
            import pytesseract
            text = pytesseract.image_to_string(Image.open(path))
            return self.ok(text=text, image=path)
        except ImportError:
            return self.err("pip install pytesseract Pillow")
        except Exception as e:
            return self.err(str(e))

    async def _frames(self, path: str, fps: int) -> dict:
        try:
            import cv2
            out = Path("workspace/frames")
            out.mkdir(parents=True,exist_ok=True)
            cap   = cv2.VideoCapture(path)
            rate  = int(cap.get(cv2.CAP_PROP_FPS) or 25)
            step  = max(1, rate//fps)
            frames= []
            idx = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if idx % step == 0:
                    fp = str(out/f"frame_{idx:05d}.jpg")
                    cv2.imwrite(fp, frame)
                    frames.append(fp)
                idx += 1
            cap.release()
            return self.ok(count=len(frames), frames=frames[:10])
        except ImportError:
            return self.err("pip install opencv-python")
        except Exception as e:
            return self.err(str(e))

    async def _detect(self, path: str) -> dict:
        desc = await self._describe(path)
        objects = await self.ask_llm(
            f"List objects in: {desc.get('description','')}\nReturn comma-separated list.")
        return self.ok(image=path, objects=[o.strip() for o in objects.split(",")])

    async def _llava_describe(self, path: str, prompt: str = "") -> dict:
        """Send image to LLaVA via Ollama for multimodal understanding."""
        if not Path(path).exists():
            return self.err(f"Not found: {path}")
        try:
            import ollama as ollama_client
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            user_prompt = prompt or "Describe this image in detail. What do you see?"
            response = ollama_client.chat(
                model="llava:7b",
                messages=[{"role": "user", "content": user_prompt, "images": [img_b64]}]
            )
            text = response["message"]["content"]
            self.vmem.store(text, path)
            return self.ok(image=path, description=text, model="llava:7b")
        except ImportError:
            return self.err("pip install ollama")
        except Exception as e:
            return self.err(f"LLaVA error: {e}")

    async def _screenshot_and_understand(self, goal: str = "") -> dict:
        """Take a screenshot and analyze it with LLaVA."""
        from screen_control import screenshot, understand_screen
        path = screenshot("vision_agent")
        result = await understand_screen(path, goal=goal)
        self.vmem.store(result.get("description", ""), path)
        return self.ok(**result)

    async def _screen_goal(self, goal: str) -> dict:
        """Fully autonomous screen goal: see → plan → act."""
        from screen_control import do_goal_on_screen
        result = await do_goal_on_screen(goal)
        return self.ok(**result)

    async def interactive_loop(self, orchestrator):
        print("\n[Vision] Commands: path/to/image.jpg | screenshot | screen:<goal> | exit")
        while True:
            p = input("\n[Vision]> ").strip()
            if not p or p.lower() == "exit":
                break
            if p.lower() == "screenshot":
                r = await self._screenshot_and_understand()
                print(f"\n📸 {r.get('description', r.get('error', 'No description'))[:400]}\n")
            elif p.lower().startswith("screen:"):
                goal = p[7:].strip()
                r = await self._screen_goal(goal)
                print(f"\n🖥  Screen goal result: {r}\n")
            elif Path(p).exists():
                r = await self._llava_describe(p)
                if "error" in r:
                    r = await self._describe(p)
                print(f"\n📸 {r.get('description', r.get('error'))}\n")
            else:
                print(f"File not found: {p}")
