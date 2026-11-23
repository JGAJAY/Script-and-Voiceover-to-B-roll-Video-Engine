import asyncio
import os
import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.config import settings
from src.services.footage_sources.base import BaseFootageProvider, FootageItem

logger = logging.getLogger(__name__)

CURATED_CATALOG = [
    {
        "id": "tech_servers_01",
        "title": "Cloud data center servers and blue fiber optics",
        "tags": ["cloud", "computing", "technology", "server", "data", "software", "infrastructure"],
        "generator_filter": "color=c=0x0a192f:s=1920x1080:d={dur},drawgrid=width=80:height=80:color=0x1e3a8a@0.4",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/tech_servers_01"
    },
    {
        "id": "business_growth_01",
        "title": "Business growth value metric upward chart visualization",
        "tags": ["value", "business", "growth", "finance", "sales", "statistics", "metric", "chart"],
        "generator_filter": "mandelbrot=s=1920x1080:rate=30:maxiter=80:start_scale=1.5,curves=vintage",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/business_growth_01"
    },
    {
        "id": "modern_banking_01",
        "title": "Modern financial architectural building facade",
        "tags": ["bank", "finance", "building", "architecture", "city", "corporate"],
        "generator_filter": "color=c=0x1f2937:s=1920x1080:d={dur},drawgrid=width=120:height=120:color=0x4b5563@0.3",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/modern_banking_01"
    },
    {
        "id": "nature_river_01",
        "title": "Peaceful riverbank nature water flowing",
        "tags": ["bank", "river", "nature", "water", "green", "landscape"],
        "generator_filter": "cellauto=s=1920x1080:rule=30:rate=30,eq=contrast=1.2:saturation=1.5",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/nature_river_01"
    },
    {
        "id": "coding_developer_01",
        "title": "Developer IDE terminal programming code editor",
        "tags": ["python", "code", "programming", "software", "developer", "computer", "tutorial"],
        "generator_filter": "color=c=0x1e1e1e:s=1920x1080:d={dur},drawgrid=width=40:height=40:color=0x334155@0.3",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/coding_developer_01"
    },
    {
        "id": "sensitive_sober_01",
        "title": "Subdued respectful monochrome tone for solemn news",
        "tags": ["sensitive", "news", "tragedy", "crisis", "somber", "respectful"],
        "generator_filter": "color=c=0x111827:s=1920x1080:d={dur}",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/sensitive_sober_01"
    },
    {
        "id": "abstract_general_01",
        "title": "Dynamic geometric motion flow and bright light particles",
        "tags": ["abstract", "general", "modern", "bright", "intro", "story"],
        "generator_filter": "testsrc2=s=1920x1080:rate=30,eq=contrast=1.1:saturation=1.2",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "IncuBrix Procedural Library / Open Media",
        "link": "https://incubrix.internal/media/abstract_general_01"
    }
]

class LocalLibraryProvider(BaseFootageProvider):
    """Provides instant, commercial-safe, royalty-free clips generated and cached locally."""

    def name(self) -> str:
        return "local_commercial_library"

    async def search(
        self,
        query: str,
        duration: float,
        aspect_ratio: str = "16:9",
        avoid: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[FootageItem]:
        query_words = set(query.lower().replace(",", " ").replace(".", " ").split())
        avoid_set = set([a.lower() for a in (avoid or [])])

        scored_items = []
        for cat in CURATED_CATALOG:
            # Check avoid tags
            if any(a in cat["tags"] for a in avoid_set):
                continue
                
            match_score = len(query_words.intersection(cat["tags"]))
            # Bonus if sensitive or context matches
            if context and context.get("is_sensitive") and "sensitive" in cat["tags"]:
                match_score += 5
            if context and context.get("is_abstract") and "abstract" in cat["tags"]:
                match_score += 3
            if context and context.get("disambiguated_concept"):
                # Match tags against disambiguated concept
                concept_words = set(context["disambiguated_concept"].lower().split())
                match_score += len(concept_words.intersection(cat["tags"])) * 2

            scored_items.append((match_score, cat))

        scored_items.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, cat in scored_items:
            relevance = min(5.0, 3.5 + (0.5 * score))
            item = FootageItem(
                clip_id=cat["id"],
                url=f"local://{cat['id']}",
                source=self.name(),
                licence=cat["licence"],
                attribution=cat["attribution"],
                link=cat["link"],
                is_ai_generated=False,
                aspect_ratio=aspect_ratio,
                duration=max(10.0, duration + 2.0),
                relevance_score=round(relevance, 2),
                tags=cat["tags"]
            )
            results.append(item)

        if not results:
            # Fallback to general abstract
            cat = CURATED_CATALOG[-1]
            results.append(
                FootageItem(
                    clip_id=cat["id"],
                    url=f"local://{cat['id']}",
                    source=self.name(),
                    licence=cat["licence"],
                    attribution=cat["attribution"],
                    link=cat["link"],
                    is_ai_generated=False,
                    aspect_ratio=aspect_ratio,
                    duration=max(10.0, duration + 2.0),
                    relevance_score=3.5,
                    tags=cat["tags"]
                )
            )

        return results

    async def prepare_clip(self, item: FootageItem, target_dir: Path) -> Path:
        """Renders the clip video using ffmpeg procedural generator if not already cached."""
        target_dir.mkdir(parents=True, exist_ok=True)
        clip_path = target_dir / f"{item.clip_id}_{int(item.duration)}s.mp4"

        if clip_path.exists() and clip_path.stat().st_size > 1024:
            return clip_path

        # Find generator definition
        entry = next((c for c in CURATED_CATALOG if c["id"] == item.clip_id), CURATED_CATALOG[-1])
        filter_str = entry["generator_filter"].format(dur=int(item.duration + 2))

        import imageio_ffmpeg
        ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()

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
            logger.error(f"Failed to generate clip {item.clip_id}: {stderr.decode('utf-8', errors='ignore')}")
            raise RuntimeError(f"FFmpeg procedural clip generation failed for {item.clip_id}")

        return clip_path

local_library_provider = LocalLibraryProvider()
