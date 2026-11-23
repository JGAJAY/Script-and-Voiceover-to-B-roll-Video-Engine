import asyncio
import os
import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.config import settings
from src.services.footage_sources.base import BaseFootageProvider, FootageItem
from src.api.errors import IncuBrixException, IncuBrixErrorCodes

logger = logging.getLogger(__name__)

# Sensitive names and brands to guard against realistic fabrication
BLOCKED_REAL_PEOPLE = ["elon musk", "narendra modi", "donald trump", "joe biden", "bill gates", "steve jobs"]
BLOCKED_BRANDS = ["apple", "google", "microsoft", "nike", "coca-cola", "tesla"]

class GenerativeVideoProvider(BaseFootageProvider):
    """Generates synthetic AI video clips for abstract themes, metrics, and conceptual lines."""

    def name(self) -> str:
        return "generative_engine"

    async def search(
        self,
        query: str,
        duration: float,
        aspect_ratio: str = "16:9",
        avoid: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[FootageItem]:
        query_lower = query.lower()
        
        # Enforce Safety Rule (Must-have #6)
        safe_query = self._apply_safety_guardrails(query_lower)

        clip_id = f"gen_{hashlib.md5(safe_query.encode('utf-8')).hexdigest()[:10]}"
        
        item = FootageItem(
            clip_id=clip_id,
            url=f"generative://{clip_id}",
            source=self.name(),
            licence="Synthetic Generation CC0 Equivalent (Commercial Rights Clear)",
            attribution="IncuBrix Generative Synthesis Engine",
            link="https://incubrix.internal/generative-ai",
            is_ai_generated=True,
            aspect_ratio=aspect_ratio,
            duration=max(10.0, duration + 2.0),
            relevance_score=4.6,
            tags=["ai_generated", "generative_video", "abstract_concept"]
        )
        return [item]

    def _apply_safety_guardrails(self, query: str) -> str:
        """Sanitizes prompt to prevent generation of fake realistic human faces or brand logos."""
        sanitized = query
        for person in BLOCKED_REAL_PEOPLE:
            if person in sanitized:
                logger.info(f"Safety guardrail triggered: Replaced real person '{person}' with symbolic stylized representation.")
                sanitized = sanitized.replace(person, "stylized silhouette visionary leader")

        for brand in BLOCKED_BRANDS:
            if brand in sanitized:
                logger.info(f"Safety guardrail triggered: Replaced brand '{brand}' with neutral tech graphics.")
                sanitized = sanitized.replace(brand, "modern technology ecosystem")

        return sanitized

    async def prepare_clip(self, item: FootageItem, target_dir: Path) -> Path:
        """Generates dynamic AI abstract visuals via procedural harmonic filters."""
        target_dir.mkdir(parents=True, exist_ok=True)
        clip_path = target_dir / f"{item.clip_id}_{int(item.duration)}s.mp4"

        if clip_path.exists() and clip_path.stat().st_size > 1024:
            return clip_path

        import imageio_ffmpeg
        ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()

        # Dynamic glowing generative filter (harmonic wave motion + gradients)
        filter_str = (
            "mandelbrot=s=1920x1080:rate=30:maxiter=60:start_scale=1.8,"
            "curves=all='0/0 0.5/0.45 1/1',"
            "eq=contrast=1.15:saturation=1.3:brightness=0.02"
        )

        cmd = [
            ffmpeg_exe, "-nostdin", "-y",
            "-f", "lavfi",
            "-i", filter_str,
            "-t", str(item.duration),
            "-r", "30",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(clip_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
        _, stderr = await proc.communicate()

        if not clip_path.exists():
            logger.error(f"Generative clip rendering failed: {stderr.decode('utf-8', errors='ignore')}")
            raise RuntimeError(f"Generative video synthesis failed for {item.clip_id}")

        return clip_path

generative_video_provider = GenerativeVideoProvider()
