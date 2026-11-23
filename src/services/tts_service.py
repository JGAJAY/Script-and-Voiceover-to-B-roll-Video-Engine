import asyncio
import os
import re
import wave
import math
import struct
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging

from src.config import settings
from src.api.errors import IncuBrixException, IncuBrixErrorCodes

logger = logging.getLogger(__name__)

VOICE_MAP = {
    # English Indian
    "en-IN-female": "en-IN-NeerjaNeural",
    "en-IN-male": "en-IN-PrabhatNeural",
    # English US
    "en-US-female": "en-US-JennyNeural",
    "en-US-male": "en-US-GuyNeural",
    # Hindi
    "hi-IN-female": "hi-IN-SwaraNeural",
    "hi-IN-male": "hi-IN-MadhurNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    # Tamil
    "ta-IN-female": "ta-IN-PallaviNeural",
    "ta-IN-male": "ta-IN-ValluvarNeural",
    "ta-IN": "ta-IN-PallaviNeural",
}

class TTSService:
    """Provides text-to-speech with word-level timestamps and offline mock fallback."""

    def resolve_voice(self, voice_name: Optional[str], text: str) -> str:
        # Detect Hindi / Tamil script characters if voice not explicitly given
        if any('\u0900' <= char <= '\u097F' for char in text):
            return "hi-IN-SwaraNeural"
        if any('\u0B80' <= char <= '\u0BFF' for char in text):
            return "ta-IN-PallaviNeural"
            
        if not voice_name:
            return "en-IN-NeerjaNeural"
        return VOICE_MAP.get(voice_name, voice_name)

    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = "en-IN-female",
        output_path: Optional[Path] = None,
        job_id: str = "default"
    ) -> Dict[str, Any]:
        """Generates speech file and returns audio path, duration, and word timestamps."""
        if not text or not text.strip():
            raise IncuBrixException(
                code=IncuBrixErrorCodes.INVALID_INPUT,
                message="Cannot generate speech for an empty script.",
                status_code=400
            )

        clean_text = text.strip()
        voice_id = self.resolve_voice(voice, clean_text)
        
        if output_path is None:
            cache_dir = Path(settings.STORAGE_DIR) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            output_path = cache_dir / f"{job_id}_narration.mp3"

        # Check if running in offline test / mock mode
        if settings.ENABLE_MOCK_SOURCES or os.environ.get("ENABLE_MOCK_SOURCES") == "true" or os.environ.get("APP_ENV") == "test":
            logger.info("Test/offline mode active: using instant offline synthesizer.")
            return self._generate_offline_speech(clean_text, voice_id, output_path, job_id)

        # Try edge-tts with strict timeout
        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, voice_id)
            submaker = edge_tts.SubMaker()
            
            async def _stream_edge():
                with open(output_path, "wb") as f:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            f.write(chunk["data"])
                        elif chunk["type"] == "WordBoundary":
                            submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])

            await asyncio.wait_for(_stream_edge(), timeout=4.0)

            duration = await self._get_audio_duration(output_path)
            words = self._extract_words_from_submaker(submaker, clean_text, duration)
            
            logger.info(f"Generated speech via edge-tts ({voice_id}), duration: {duration:.2f}s")
            return {
                "audio_path": output_path,
                "duration": duration,
                "words": words,
                "voice": voice_id,
                "provider": "edge-tts"
            }
        except Exception as e:
            logger.warning(f"edge-tts unavailable or timed out ({e}); falling back to offline synthesizer.")
            return self._generate_offline_speech(clean_text, voice_id, output_path, job_id)

    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Determines duration using ffmpeg / ffprobe."""
        try:
            import imageio_ffmpeg
            ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_exe, "-nostdin", "-i", str(audio_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL
            )
            _, stderr = await proc.communicate()
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr.decode("utf-8", errors="ignore"))
            if match:
                hours, minutes, seconds = match.groups()
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except Exception as err:
            logger.debug(f"Failed to read duration via ffmpeg: {err}")

        # Fallback approximation: 150 words per minute ~ 2.5 words/sec
        return max(2.5, len(text.split()) / 2.5)

    def _extract_words_from_submaker(self, submaker, text: str, total_duration: float) -> List[Dict[str, Any]]:
        words = []
        # Fallback or synthetic boundaries if submaker entries are empty
        raw_words = text.split()
        if not hasattr(submaker, "subs") or not submaker.subs:
            avg_word_dur = total_duration / max(1, len(raw_words))
            for i, w in enumerate(raw_words):
                words.append({
                    "word": w,
                    "start": round(i * avg_word_dur, 2),
                    "end": round((i + 1) * avg_word_dur, 2)
                })
            return words

        for sub in submaker.subs:
            # edge_tts sub items: start time, end time, text
            start = sub.start.total_seconds()
            end = sub.end.total_seconds()
            words.append({
                "word": sub.text,
                "start": round(start, 2),
                "end": round(end, 2)
            })
        return words

    def _generate_offline_speech(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        job_id: str
    ) -> Dict[str, Any]:
        """Generates a high-quality offline PCM wav file with realistic pacing for offline testing."""
        words_raw = text.split()
        word_count = len(words_raw)
        
        # Realistic narration pace: ~2.5 words per second + pause per comma/period
        base_dur_per_word = 0.40  # 400ms per word
        words = []
        current_time = 0.0

        for w in words_raw:
            dur = base_dur_per_word * (1.2 if len(w) > 6 else 1.0)
            if w.endswith((".", "!", "?")):
                pause = 0.4
            elif w.endswith((",", ";", ":")):
                pause = 0.2
            else:
                pause = 0.05
                
            start = current_time
            end = start + dur
            current_time = end + pause
            words.append({"word": w, "start": round(start, 2), "end": round(end, 2)})

        total_duration = max(2.0, current_time)
        wav_path = output_path.with_suffix(".wav")

        # Fast vectorized audio synthesis using numpy
        import numpy as np
        sample_rate = 24000
        total_samples = int(sample_rate * total_duration)
        t = np.linspace(0, total_duration, total_samples, endpoint=False, dtype=np.float32)
        
        mask = np.zeros(total_samples, dtype=bool)
        for w in words:
            s_idx = int(w["start"] * sample_rate)
            e_idx = min(total_samples, int(w["end"] * sample_rate))
            mask[s_idx:e_idx] = True

        f0 = 150.0 + 20.0 * np.sin(2 * np.pi * 1.5 * t)
        speech_sig = 0.3 * np.sin(2 * np.pi * f0 * t) + 0.15 * np.sin(2 * np.pi * f0 * 2.5 * t)
        ambience = 0.001 * np.sin(2 * np.pi * 50 * t)
        signal = np.where(mask, speech_sig, ambience)
        int_data = (signal * 16000).clip(-32767, 32767).astype(np.int16)

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int_data.tobytes())

        # Convert to mp3 if requested or use wav
        final_path = wav_path
        try:
            import imageio_ffmpeg
            ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()
            mp3_path = output_path.with_suffix(".mp3")
            import subprocess
            subprocess.run([
                ffmpeg_exe, "-nostdin", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            final_path = mp3_path
        except Exception:
            final_path = wav_path

        logger.info(f"Synthesized offline mock speech, duration: {total_duration:.2f}s, words: {word_count}")
        return {
            "audio_path": final_path,
            "duration": total_duration,
            "words": words,
            "voice": voice_id,
            "provider": "offline-synthesizer"
        }

tts_service = TTSService()
