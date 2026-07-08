"""Object Detector — Bounding box detection using OpenCV/YOLO."""
from logger import setup_logger
logger = setup_logger("ObjectDetector")

class ObjectDetector:
    def detect_motion(self, video_path: str, threshold=25) -> list:
        try:
            import cv2
            cap=cv2.VideoCapture(video_path)
            ret,prev=cap.read()
            if not ret:
                return []
            prev_gray=cv2.cvtColor(prev,cv2.COLOR_BGR2GRAY)
            motion_frames=[]
            idx=0
            while True:
                ret,frame=cap.read()
                if not ret:
                    break
                gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                diff=cv2.absdiff(prev_gray,gray)
                if diff.mean()>threshold:
                    motion_frames.append(idx)
                prev_gray=gray
                idx+=1
            cap.release()
            return motion_frames
        except ImportError:
            return []

    def find_faces(self, image_path: str) -> list:
        try:
            import cv2
            img=cv2.imread(image_path)
            gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            cascade=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
            faces=cascade.detectMultiScale(gray,1.1,4)
            return [{"x":int(x),"y":int(y),"w":int(w),"h":int(h)} for x,y,w,h in faces]
        except ImportError:
            return []
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []

    def describe_with_llm(self, image_path: str, orchestrator=None) -> str:
        if not orchestrator:
            return "No orchestrator available"
        vision = orchestrator.get_agent("vision")
        if not vision:
            return "No vision agent"
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(vision.execute({"data":{"action":"describe","source":image_path}}))
        return result.get("description","")
