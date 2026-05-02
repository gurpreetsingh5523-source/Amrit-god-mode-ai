"""Image Reader — PIL-based image processing."""
import base64
from logger import setup_logger
logger = setup_logger("ImageReader")

class ImageReader:
    def info(self, path: str) -> dict:
        try:
            from PIL import Image
            img=Image.open(path)
            return {"path":path,"size":img.size,"mode":img.mode,"format":img.format}
        except ImportError:
            return {"error":"pip install Pillow"}
        except Exception as e:
            return {"error":str(e)}

    def to_base64(self, path: str) -> str:
        with open(path,"rb") as f:
            return base64.b64encode(f.read()).decode()

    def resize(self, path: str, w: int, h: int, out: str=None) -> str:
        from PIL import Image
        img=Image.open(path).resize((w,h))
        out=out or path.replace(".",f"_{w}x{h}.")
        img.save(out)
        return out

    def to_grayscale(self, path: str, out: str=None) -> str:
        from PIL import Image
        img=Image.open(path).convert("L")
        out=out or path.replace(".","_gray.")
        img.save(out)
        return out

    def crop(self, path: str, box: tuple, out: str=None) -> str:
        from PIL import Image
        img=Image.open(path).crop(box)
        out=out or path.replace(".","_crop.")
        img.save(out)
        return out

    def thumbnail(self, path: str, size=(128,128)) -> str:
        from PIL import Image
        img=Image.open(path)
        img.thumbnail(size)
        out=path.replace(".","_thumb.")
        img.save(out)
        return out
