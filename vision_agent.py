"""Vision Agent — Image description, OCR, video frames, object detection."""
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
            return await self._frames(source, d.get("fps",1))
        if action == "detect":
            return await self._detect(source)
        if action == "recall":
            return self.ok(observations=self.vmem.search(d.get("query","")))
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

    async def interactive_loop(self, orchestrator):
        while True:
            p = input("\n[Vision] Image path (or exit): ").strip()
            if p.lower() == "exit":
                break
            r = await self._describe(p)
            print(f"\n📸 {r.get('description', r.get('error'))}\n")
