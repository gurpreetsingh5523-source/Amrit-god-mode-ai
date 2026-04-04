"""Voice Agent — STT (Whisper) + TTS (pyttsx3/ElevenLabs) + emotion detection."""
from base_agent import BaseAgent

class VoiceAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("VoiceAgent", eb, state)
        self._tts = self._stt = None

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        mode = d.get("mode", "speak")
        if mode == "speak":     return await self._speak(d.get("text", task.get("name","")))
        if mode == "listen":    return await self._listen(d.get("duration", 6))
        if mode == "transcribe": return await self._transcribe(d.get("audio_path",""))
        if mode == "emotion":   return await self._detect_emotion(d.get("text",""))
        return self.err(f"Unknown mode: {mode}")

    async def _speak(self, text: str) -> dict:
        try:
            import pyttsx3
            if not self._tts:
                self._tts = pyttsx3.init()
                self._tts.setProperty("rate", 155)
            self._tts.say(text)
            self._tts.runAndWait()
            return self.ok(spoken=text)
        except ImportError:
            print(f"[TTS] {text}"); return self.ok(fallback="print", text=text)
        except Exception as e: return self.err(str(e))

    async def _listen(self, duration: int = 6) -> dict:
        try:
            import speech_recognition as sr
            rec = sr.Recognizer()
            with sr.Microphone() as src:
                self.logger.info(f"Listening {duration}s...")
                rec.adjust_for_ambient_noise(src, 0.5)
                audio = rec.listen(src, timeout=duration)
            text = rec.recognize_google(audio)
            return self.ok(text=text)
        except ImportError:
            return self.err("SpeechRecognition required: pip install SpeechRecognition pyaudio")
        except Exception as e: return self.err(str(e))

    async def _transcribe(self, path: str) -> dict:
        try:
            import whisper
            if not self._stt:
                self._stt = whisper.load_model("base")
            r = self._stt.transcribe(path)
            return self.ok(text=r.get("text",""), language=r.get("language",""))
        except ImportError:
            return self.err("openai-whisper required: pip install openai-whisper")
        except Exception as e: return self.err(str(e))

    async def _detect_emotion(self, text: str) -> dict:
        emotion = await self.ask_llm(
            f"Classify emotion of: '{text}'\nReturn one word: happy/sad/angry/neutral/excited/anxious")
        return self.ok(text=text, emotion=emotion.strip().lower())

    async def listen_loop(self, orchestrator):
        await self._speak("GODMODE voice mode active. State your goal.")
        while True:
            r = await self._listen()
            text = r.get("text","")
            if not text: continue
            if "stop" in text.lower() or "exit" in text.lower():
                await self._speak("Goodbye."); break
            await self._speak(f"Processing: {text}")
            await orchestrator.run_goal(text)
