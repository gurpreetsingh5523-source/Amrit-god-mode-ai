"""
TTS Engine — Natural voice synthesis.
Priority chain: Kokoro → Coqui TTS → pyttsx3 (robot fallback)
Kokoro: open-source, ElevenLabs-quality, runs fully local (MIT license)
Coqui TTS: open-source, many voices, runs local
"""
import asyncio
import os
import tempfile
from pathlib import Path
from logger import setup_logger

logger = setup_logger("TTSEngine")

_KOKORO_MODEL = None
_COQUI_MODEL = None
_PYTTSX_ENGINE = None

VOICE_CACHE_DIR = Path("workspace/voice_cache")
VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _try_kokoro(text: str) -> bool:
    """Try Kokoro TTS — highest quality, fully local."""
    global _KOKORO_MODEL
    try:
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np

        if _KOKORO_MODEL is None:
            logger.info("Loading Kokoro TTS model (first time — ~500ms)...")
            _KOKORO_MODEL = KPipeline(lang_code="a")  # 'a' = American English

        out_path = VOICE_CACHE_DIR / "tts_out.wav"
        generator = _KOKORO_MODEL(text, voice="af_heart", speed=1.0, split_pattern=r"\n+")

        audio_chunks = []
        sample_rate = 24000
        for _, _, audio in generator:
            audio_chunks.append(audio)

        if audio_chunks:
            import numpy as np
            combined = np.concatenate(audio_chunks)
            sf.write(str(out_path), combined, sample_rate)
            _play_audio(str(out_path))
            return True
        return False
    except Exception as e:
        logger.debug(f"Kokoro failed: {e}")
        return False


def _try_coqui(text: str) -> bool:
    """Try Coqui TTS — good quality, many voices."""
    global _COQUI_MODEL
    try:
        from TTS.api import TTS
        if _COQUI_MODEL is None:
            logger.info("Loading Coqui TTS model (first time — may download)...")
            _COQUI_MODEL = TTS("tts_models/en/ljspeech/tacotron2-DDC")

        out_path = str(VOICE_CACHE_DIR / "tts_coqui.wav")
        _COQUI_MODEL.tts_to_file(text=text, file_path=out_path)
        _play_audio(out_path)
        return True
    except Exception as e:
        logger.debug(f"Coqui failed: {e}")
        return False


def _try_pyttsx3(text: str) -> bool:
    """Fallback: pyttsx3 robot voice — always available."""
    global _PYTTSX_ENGINE
    try:
        import pyttsx3
        if _PYTTSX_ENGINE is None:
            _PYTTSX_ENGINE = pyttsx3.init()
            _PYTTSX_ENGINE.setProperty("rate", 165)
            _PYTTSX_ENGINE.setProperty("volume", 0.95)
            # Pick best available voice
            voices = _PYTTSX_ENGINE.getProperty("voices")
            for v in voices:
                if "samantha" in v.name.lower() or "karen" in v.name.lower():
                    _PYTTSX_ENGINE.setProperty("voice", v.id)
                    break
        _PYTTSX_ENGINE.say(text)
        _PYTTSX_ENGINE.runAndWait()
        return True
    except Exception as e:
        logger.warning(f"pyttsx3 failed: {e}")
        print(f"[AMRIT SPEAK] {text}")
        return True


def _play_audio(path: str):
    """Play audio file using macOS afplay — blocking so mic doesn't start during playback."""
    try:
        subprocess.run(["afplay", path], check=False)
        # Brief pause after speech so mic doesn't catch the tail
        import time
        time.sleep(0.4)
    except Exception:
        try:
            os.system(f"afplay '{path}'")
        except Exception:
            pass


def speak(text: str):
    """Speak text using best available TTS engine."""
    if not text or not text.strip():
        return
    # Truncate very long outputs for speaking
    if len(text) > 300:
        text = text[:280] + "... (see terminal for full output)"

    for engine_fn in [_try_kokoro, _try_coqui, _try_pyttsx3]:
        if engine_fn(text):
            return


async def speak_async(text: str):
    """Async wrapper for speak — runs in thread pool to avoid blocking."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, speak, text)


def get_tts_status() -> dict:
    """Return which TTS engines are available."""
    status = {}
    try:
        import kokoro
        status["kokoro"] = "available"
    except ImportError:
        status["kokoro"] = "not installed (pip install kokoro soundfile)"
    try:
        import TTS
        status["coqui"] = "available"
    except ImportError:
        status["coqui"] = "not installed (pip install TTS)"
    try:
        import pyttsx3
        status["pyttsx3"] = "available (fallback)"
    except ImportError:
        status["pyttsx3"] = "not installed"
    return status
