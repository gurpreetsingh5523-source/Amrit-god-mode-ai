"""Video Reader — Frame extraction and video metadata."""
from pathlib import Path
from logger import setup_logger
logger = setup_logger("VideoReader")

class VideoReader:
    def get_info(self, path: str) -> dict:
        try:
            import cv2; cap=cv2.VideoCapture(path)
            info={"fps":cap.get(cv2.CAP_PROP_FPS),"frames":int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                  "width":int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),"height":int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
            info["duration_s"]=round(info["frames"]/(info["fps"] or 1),2)
            cap.release(); return info
        except ImportError: return {"error":"pip install opencv-python"}

    def extract_frames(self, path: str, fps=1, out_dir="workspace/frames") -> list:
        try:
            import cv2; Path(out_dir).mkdir(parents=True,exist_ok=True)
            cap=cv2.VideoCapture(path); rate=int(cap.get(cv2.CAP_PROP_FPS) or 25)
            step=max(1,rate//fps); frames=[]; idx=0
            while cap.isOpened():
                ret,frame=cap.read()
                if not ret: break
                if idx%step==0:
                    fp=f"{out_dir}/frame_{idx:05d}.jpg"; cv2.imwrite(fp,frame); frames.append(fp)
                idx+=1
            cap.release(); logger.info(f"Extracted {len(frames)} frames")
            return frames
        except ImportError: raise ImportError("pip install opencv-python")

    def frame_at(self, path: str, second: float, out="workspace/frame_at.jpg") -> str:
        import cv2; cap=cv2.VideoCapture(path)
        fps=cap.get(cv2.CAP_PROP_FPS); cap.set(cv2.CAP_PROP_POS_FRAMES,fps*second)
        ret,frame=cap.read(); cap.release()
        if ret: cv2.imwrite(out,frame)
        return out
