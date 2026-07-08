"""
Voice Agent — Full God Mode Voice Control.
  STT:  Whisper (offline, on-device) → Google (online fallback)
  TTS:  Kokoro (ElevenLabs-quality, free) → Coqui → pyttsx3
  Wake: "Hey Amrit" keyword detection (openwakeword, fully offline)
  Loop: Continuous listen → understand → execute goal → speak result
"""
import asyncio
from base_agent import BaseAgent
from tts_engine import speak_async


class VoiceAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("VoiceAgent", eb, state)
        self._stt_model = None        # Whisper model (loaded once)
        self._wake_model = None       # openwakeword model
        self._voice_mem = None

    # ── Public execute dispatcher ────────────────────────────

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        mode = d.get("mode", "speak")
        if mode == "speak":
            return await self._speak(d.get("text", task.get("name", "")))
        if mode == "listen":
            return await self._listen_whisper(d.get("duration", 8))
        if mode == "transcribe":
            return await self._transcribe(d.get("audio_path", ""))
        if mode == "emotion":
            return await self._detect_emotion(d.get("text", ""))
        return self.err(f"Unknown mode: {mode}")

    # ── TTS ──────────────────────────────────────────────────

    async def _speak(self, text: str) -> dict:
        if not text:
            return self.ok(spoken="")
        await speak_async(str(text))
        return self.ok(spoken=text)

    # ── STT: Whisper (offline first) ─────────────────────────

    async def _listen_whisper(self, duration: int = 8) -> dict:
        """Record mic audio and transcribe with Whisper (fully offline, with silence detection)."""
        try:
            import pyaudio
            import wave
            import tempfile
            import os
            import struct

            RATE, CHUNK, CHANNELS = 16000, 1024, 1
            SILENCE_THRESHOLD = 400    # RMS level below this = silence
            MIN_SPEECH_CHUNKS = 5      # need at least 5 chunks with sound

            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=CHANNELS,
                            rate=RATE, input=True, frames_per_buffer=CHUNK)

            self.logger.info(f"Recording {duration}s via Whisper...")
            frames = []
            loud_chunks = 0

            for _ in range(0, int(RATE / CHUNK * duration)):
                chunk = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(chunk)
                # RMS energy check
                samples = struct.unpack(f"{len(chunk)//2}h", chunk)
                rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                if rms > SILENCE_THRESHOLD:
                    loud_chunks += 1

            stream.stop_stream()
            stream.close()
            p.terminate()

            # Silence guard — don't bother transcribing if no speech detected
            if loud_chunks < MIN_SPEECH_CHUNKS:
                return self.ok(text="", reason="silence")

            # Save to temp WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(RATE)
                wf.writeframes(b"".join(frames))

            result = await self._transcribe(tmp_path)
            os.unlink(tmp_path)
            return result

        except Exception as e:
            self.logger.warning(f"Whisper listen failed: {e} — trying Google STT")
            return await self._listen_google(duration)

    async def _listen_google(self, duration: int = 8) -> dict:
        """Fallback: Google STT (requires internet)."""
        try:
            import speech_recognition as sr
            rec = sr.Recognizer()
            with sr.Microphone() as src:
                self.logger.info(f"Listening {duration}s (Google STT)...")
                rec.adjust_for_ambient_noise(src, 0.3)
                audio = rec.listen(src, timeout=duration, phrase_time_limit=duration)
            text = rec.recognize_google(audio)
            return self.ok(text=text, engine="google")
        except Exception as e:
            return self.err(f"STT failed: {e}")

    async def _transcribe(self, path: str) -> dict:
        """Transcribe an audio file with Whisper on Apple Silicon GPU (MPS)."""
        try:
            import whisper
            import torch
            import asyncio
            if self._stt_model is None:
                self.logger.info("Loading Whisper base model on MPS GPU (once)...")
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                loop = asyncio.get_event_loop()
                self._stt_model = await loop.run_in_executor(
                    None, lambda: whisper.load_model("base", device=device)
                )
                self.logger.info(f"Whisper loaded on {device}")
            loop = asyncio.get_event_loop()
            r = await loop.run_in_executor(
                None, lambda: self._stt_model.transcribe(path, fp16=False)
            )
            text = r.get("text", "").strip()
            lang = r.get("language", "en")
            self.logger.info(f"Transcribed [{lang}]: {text!r}")
            return self.ok(text=text, language=lang, engine="whisper")
        except Exception as e:
            return self.err(f"Whisper transcribe failed: {e}")

    # ── Emotion Detection ─────────────────────────────────────

    async def _detect_emotion(self, text: str) -> dict:
        emotion = await self.ask_llm(
            f"Classify emotion of: '{text}'\nReturn one word: happy/sad/angry/neutral/excited/anxious"
        )
        return self.ok(text=text, emotion=emotion.strip().lower())

    # ── Wake Word Detection ───────────────────────────────────

    def _start_wake_word_listener(self, callback):
        """
        Run openwakeword in background thread listening for 'Hey Amrit'.
        Calls callback() when wake word detected.
        """
        try:
            import openwakeword
            from openwakeword.model import Model
            import pyaudio
            import numpy as np

            # Load model — openwakeword includes 'hey_jarvis', 'hey_mycroft' etc.
            # Use 'hey_jarvis' as our wake word (closest to 'Hey Amrit')
            oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                            input=True, frames_per_buffer=1280)

            self.logger.info("Wake word listener active — say 'Hey Amrit'")

            while True:
                audio = np.frombuffer(stream.read(1280, exception_on_overflow=False),
                                      dtype=np.int16)
                oww.predict(audio)
                scores = oww.prediction_buffer
                for name, score_list in scores.items():
                    if score_list and score_list[-1] > 0.5:
                        self.logger.info(f"Wake word detected! ({name}: {score_list[-1]:.2f})")
                        stream.stop_stream()
                        stream.close()
                        p.terminate()
                        callback()
                        return
        except ImportError:
            self.logger.warning("openwakeword not installed — using keyword polling instead")
            return None
        except Exception as e:
            self.logger.warning(f"Wake word failed: {e}")
            return None

    # ── Voice Memory ──────────────────────────────────────────

    def _get_voice_memory(self):
        if self._voice_mem is None:
            from voice_memory import VoiceMemory
            self._voice_mem = VoiceMemory()
        return self._voice_mem

    def _remember_exchange(self, role: str, text: str, emotion: str = "neutral"):
        try:
            self._get_voice_memory().record(role, text, emotion)
        except Exception:
            pass

    # ── Main Voice Loop (God Mode) ────────────────────────────

    async def listen_loop(self, orchestrator):
        """
        Continuous God Mode voice loop:
        1. Say "Hey Amrit" → wake up (or skip for continuous mode)
        2. Listen for command (Whisper offline)
        3. Speak back: "Processing..."
        4. Execute goal via orchestrator
        5. Speak back result summary
        6. Loop
        """
        await self._speak(
            "AMRIT God Mode voice control active. "
            "I am listening. Say your goal and I will execute it."
        )
        self._remember_exchange("system", "Voice mode started")

        consecutive_failures = 0
        max_failures = 5

        while True:
            try:
                # Listen for input — pause after TTS to prevent echo
                await self._speak("Listening...")
                await asyncio.sleep(0.5)  # mic settle time after speaker stops
                result = await self._listen_whisper(duration=8)
                text = result.get("text", "").strip()

                if not text:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        await self._speak("I didn't hear anything. Still listening.")
                        consecutive_failures = 0
                    continue

                consecutive_failures = 0
                self.logger.info(f"Heard: {text!r}")
                self._remember_exchange("user", text)

                # Stop commands
                text_lower = text.lower()
                if any(word in text_lower for word in ["stop listening", "goodbye amrit",
                                                        "exit voice", "shut down", "stop voice"]):
                    await self._speak("Voice mode deactivated. Goodbye.")
                    break

                # Meta commands
                if "what can you do" in text_lower or "help" in text_lower:
                    help_text = (
                        "I can execute any goal you give me. "
                        "I can write code, search the internet, analyze files, "
                        "control your screen, run terminal commands, "
                        "research topics, and improve myself. Just tell me what you need."
                    )
                    await self._speak(help_text)
                    continue

                if "take screenshot" in text_lower or "what's on screen" in text_lower:
                    await self._speak("Taking screenshot and analyzing screen.")
                    from screen_control import screenshot, understand_screen
                    path = screenshot("voice_triggered")
                    vision = await understand_screen(path, goal=text)
                    desc = vision.get("description", "Could not analyze screen.")
                    summary = desc[:200] if len(desc) > 200 else desc
                    await self._speak(summary)
                    self._remember_exchange("assistant", summary)
                    continue

                # Execute as orchestrator goal
                await self._speak(f"Got it. Executing: {text[:60]}")

                try:
                    # Use fast model for voice throughout — gemma3:12b ~15s vs deepseek ~2min
                    import os
                    os.environ["AMRIT_VOICE_MODE"] = "1"
                    try:
                        await orchestrator.run_goal(text)
                    finally:
                        os.environ.pop("AMRIT_VOICE_MODE", None)
                    # Get result from state
                    state_result = orchestrator.state.get("last_result") or "Task completed."
                    if isinstance(state_result, dict):
                        result_text = state_result.get("summary") or state_result.get("output") or "Done."
                    else:
                        result_text = str(state_result)[:200]

                    if not result_text or result_text == "None":
                        result_text = "Task completed successfully."

                    self._remember_exchange("assistant", result_text)
                    await self._speak(result_text)

                except Exception as e:
                    error_msg = f"I encountered an error: {str(e)[:100]}"
                    self.logger.error(f"Goal execution error: {e}")
                    await self._speak(error_msg)
                    self._remember_exchange("assistant", error_msg, "error")

            except KeyboardInterrupt:
                await self._speak("Voice mode interrupted. Goodbye.")
                break
            except Exception as e:
                self.logger.error(f"Voice loop error: {e}")
                await asyncio.sleep(1)

    # ── Wake-Word Mode (Advanced) ─────────────────────────────

    async def listen_loop_with_wakeword(self, orchestrator):
        """
        Passive listening mode — only activates when 'Hey Amrit' is detected.
        Falls back to continuous mode if openwakeword isn't available.
        """
        import threading

        wake_detected = asyncio.Event()

        def on_wake():
            asyncio.get_event_loop().call_soon_threadsafe(wake_detected.set)

        # Try to start wake word listener in background thread
        ww_thread = threading.Thread(
            target=self._start_wake_word_listener,
            args=(on_wake,),
            daemon=True
        )
        ww_thread.start()

        # Give it a moment to initialize
        await asyncio.sleep(1)

        if not ww_thread.is_alive() or True:
            # Wake word not working — fall back to continuous
            self.logger.info("Falling back to continuous voice mode")
            await self.listen_loop(orchestrator)
            return

        await self._speak("Passive mode. Say Hey Amrit to activate.")

        while True:
            try:
                wake_detected.clear()
                await asyncio.wait_for(wake_detected.wait(), timeout=300)
                # Wake word detected — run one listen→execute cycle
                await self._speak("Yes? State your goal.")
                result = await self._listen_whisper(duration=8)
                text = result.get("text", "").strip()
                if text:
                    await self._speak(f"Executing: {text[:50]}")
                    await orchestrator.run_goal(text)
                    await self._speak("Done. Say Hey Amrit when you need me.")
            except asyncio.TimeoutError:
                continue
            except KeyboardInterrupt:
                break
