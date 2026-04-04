"""Text to Speech — pyttsx3 / ElevenLabs TTS."""
from logger import setup_logger
logger = setup_logger("TTS")

class TextToSpeech:
    def __init__(self, engine="pyttsx3", rate=155, volume=0.9):
        self.engine_name=engine; self.rate=rate; self.volume=volume; self._engine=None

    def _init_engine(self):
        if not self._engine:
            import pyttsx3
            self._engine=pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)

    def speak(self, text: str) -> bool:
        try:
            self._init_engine()
            self._engine.say(text); self._engine.runAndWait()
            return True
        except ImportError: print(f"[TTS] {text}"); return False
        except Exception as e: logger.error(f"TTS error: {e}"); return False

    def speak_elevenlabs(self, text: str, voice_id="21m00Tcm4TlvDq8ikWAM") -> bool:
        import os, urllib.request, json
        key = os.getenv("ELEVENLABS_API_KEY","")
        if not key: return self.speak(text)
        data = json.dumps({"text":text,"model_id":"eleven_monolingual_v1",
                           "voice_settings":{"stability":0.5,"similarity_boost":0.5}}).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=data, method="POST",
            headers={"xi-api-key":key,"Content-Type":"application/json","Accept":"audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                audio = r.read()
            path = "workspace/tts_output.mp3"
            with open(path,"wb") as f: f.write(audio)
            logger.info(f"TTS audio saved: {path}")
            return True
        except Exception as e: logger.error(f"ElevenLabs error: {e}"); return self.speak(text)

    def save_to_file(self, text: str, path: str) -> str:
        try:
            self._init_engine()
            self._engine.save_to_file(text, path); self._engine.runAndWait()
            return path
        except Exception as e: logger.error(f"Save error: {e}"); return ""
