"""Speech to Text — Whisper-based transcription."""
from logger import setup_logger
logger = setup_logger("STT")

class SpeechToText:
    def __init__(self, model="base"):
        self.model_name = model
        self._model = None

    def _load(self):
        if not self._model:
            import whisper
            self._model=whisper.load_model(self.model_name)
            logger.info(f"Whisper loaded: {self.model_name}")

    def transcribe(self, audio_path: str) -> dict:
        try:
            self._load()
            r = self._model.transcribe(audio_path)
        except ImportError:
            return {"error": "pip install openai-whisper"}
        except Exception as e:
            return {"error": str(e)}
        return {"text": r.get("text", ""), "language": r.get("language", "en")}

    def transcribe_stream(self, duration=5) -> dict:
        try:
            import pyaudio
            import wave
            import tempfile
            import os
            p=pyaudio.PyAudio()
            s=p.open(format=pyaudio.paInt16,channels=1,rate=16000,input=True,frames_per_buffer=1024)
            frames=[s.read(1024) for _ in range(0,int(16000/1024*duration))]
            s.stop_stream()
            s.close()
            p.terminate()
            with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as f:
                wf=wave.open(f.name,"wb")
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b"".join(frames))
                wf.close()
                result=self.transcribe(f.name)
                os.unlink(f.name)
            return result
        except ImportError:
            return {"error":"pip install pyaudio"}
        except Exception as e:
            return {"error":str(e)}
