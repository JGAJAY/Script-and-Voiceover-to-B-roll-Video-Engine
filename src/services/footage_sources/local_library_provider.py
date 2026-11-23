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
        "id": "money_savings_coins_01",
        "title": "Physical currency, saving coins and financial growth",
        "tags": [
            "money", "save", "saving", "savings", "coin", "coins", "currency", "cash",
            "dollar", "wealth", "piggy", "deposit", "habit", "habits", "secure", "future",
            "amount", "small", "step", "steps", "grow", "growth", "build", "building"
        ],
        "stock_file": "storage/clips/money_coins.mp4",
        "generator_filter": "color=c=0x1e3a1e:s=1920x1080:d={dur},drawgrid=width=100:height=100:color=0x22c55e@0.3",
        "licence": "CC0 1.0 Universal / Wikimedia Commons Public Domain",
        "attribution": "US Coins 20th Century / Open Public Domain Archive",
        "link": "https://commons.wikimedia.org/wiki/File:US_Coins_20th_Century.webm"
    },
    {
        "id": "finance_banking_digital_01",
        "title": "Digital banking, transaction expenses and income management",
        "tags": [
            "finance", "financial", "bank", "banking", "expense", "expenses", "income",
            "account", "transfer", "track", "tracking", "purchase", "purchases", "budget",
            "need", "needs", "want", "wants", "freedom", "goal", "monthly", "portion",
            "daily", "spend", "spending", "balance", "cost", "transaction"
        ],
        "stock_file": "storage/clips/digital_finance.mp4",
        "generator_filter": "color=c=0x0f2942:s=1920x1080:d={dur},drawgrid=width=100:height=100:color=0x38bdf8@0.3",
        "licence": "Creative Commons Attribution 3.0 / GSMA Mobile Money",
        "attribution": "GSMA MISTT Mobile Money Educational Project",
        "link": "https://commons.wikimedia.org/wiki/File:GSMA_MISTT_Mobile_Money_Educational_Video_(en).webm"
    },
    {
        "id": "lifestyle_daily_expenses_01",
        "title": "People daily lifestyle, shopping habits and city life",
        "tags": [
            "people", "lifestyle", "daily", "habit", "habits", "shopping", "purchase",
            "purchases", "spend", "spending", "walk", "walking", "commute", "living",
            "life", "decision", "choice", "team", "friends", "consumer", "market"
        ],
        "stock_file": "storage/clips/people_walking.mp4",
        "generator_filter": "color=c=0x0f172a:s=1920x1080:d={dur},drawgrid=width=100:height=100:color=0x38bdf8@0.2",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "Open Media / Commercial Verified Library",
        "link": "https://incubrix.internal/media/people_walking"
    },
    {
        "id": "modern_banking_01",
        "title": "Modern financial architectural city and streets",
        "tags": ["bank", "banking", "finance", "building", "architecture", "city", "corporate", "traffic", "speed", "institution", "district", "economy"],
        "stock_file": "storage/clips/city_traffic.mp4",
        "generator_filter": "color=c=0x1f2937:s=1920x1080:d={dur},drawgrid=width=120:height=120:color=0x4b5563@0.3",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "Open Media / Commercial Verified Library",
        "link": "https://incubrix.internal/media/modern_banking_01"
    },
    {
        "id": "tech_servers_01",
        "title": "Cloud data center servers and tech workspace",
        "tags": ["cloud", "computing", "technology", "tech", "server", "data", "software", "infrastructure", "code", "coding", "python", "developer", "tutorial", "ai", "machine", "learning"],
        "stock_file": "storage/clips/classroom.mp4",
        "generator_filter": "color=c=0x0a192f:s=1920x1080:d={dur},drawgrid=width=80:height=80:color=0x1e3a8a@0.4",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "Open Media / Commercial Verified Library",
        "link": "https://incubrix.internal/media/tech_servers_01"
    },
    {
        "id": "nature_river_01",
        "title": "Peaceful riverbank nature water and blossoms",
        "tags": ["river", "stream", "nature", "water", "green", "landscape", "travel", "peaceful", "calm", "flower", "blossom", "organic", "fresh", "environment"],
        "stock_file": "storage/clips/nature_flower.mp4",
        "generator_filter": "color=c=0x064e3b:s=1920x1080:d={dur},drawgrid=width=90:height=90:color=0x10b981@0.2",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "Open Media / Commercial Verified Library",
        "link": "https://incubrix.internal/media/nature_river_01"
    },
    {
        "id": "sensitive_sober_01",
        "title": "Subdued respectful monochrome tone for solemn news",
        "tags": ["sensitive", "news", "tragedy", "crisis", "somber", "respectful", "mourning", "loss"],
        "stock_file": "storage/clips/people_walking.mp4",
        "generator_filter": "color=c=0x111827:s=1920x1080:d={dur}",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "Open Media / Commercial Verified Library",
        "link": "https://incubrix.internal/media/sensitive_sober_01"
    },
    {
        "id": "abstract_general_01",
        "title": "Dynamic modern city transit motion and light",
        "tags": ["abstract", "general", "modern", "bright", "intro", "story", "motion", "light"],
        "stock_file": "storage/clips/city_traffic.mp4",
        "generator_filter": "color=c=0x0b132b:s=1920x1080:d={dur},drawgrid=width=60:height=60:color=0x38bdf8@0.2",
        "licence": "CC0 1.0 Universal Public Domain (Commercial Use Permitted)",
        "attribution": "Open Media / Commercial Verified Library",
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
        import re
        query_words = [w for w in re.sub(r"[^\w\s]", " ", query.lower()).split() if len(w) > 2]
        avoid_set = set([a.lower() for a in (avoid or [])])

        scored_items = []
        for cat in CURATED_CATALOG:
            # Check avoid tags
            if any(a in cat["tags"] for a in avoid_set):
                continue
                
            match_score = 0.0
            for qw in query_words:
                for tag in cat["tags"]:
                    if qw == tag:
                        match_score += 2.0
                    elif len(qw) >= 4 and len(tag) >= 4:
                        if qw.startswith(tag) or tag.startswith(qw):
                            match_score += 1.5
                        elif qw[:4] == tag[:4]:
                            match_score += 1.0

            # Bonus if sensitive or context matches
            if context and context.get("is_sensitive") and "sensitive" in cat["tags"]:
                match_score += 5.0
            if context and context.get("is_abstract") and "abstract" in cat["tags"]:
                match_score += 3.0
            if context and context.get("disambiguated_concept"):
                concept_words = [w for w in re.sub(r"[^\w\s]", " ", context["disambiguated_concept"].lower()).split() if len(w) > 3]
                for cw in concept_words:
                    for tag in cat["tags"]:
                        if cw == tag:
                            match_score += 3.0
                        elif len(cw) >= 4 and len(tag) >= 4 and (cw.startswith(tag) or tag.startswith(cw)):
                            match_score += 2.0

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
        """Renders the clip video using local stock video file if available, or procedural generator."""
        target_dir.mkdir(parents=True, exist_ok=True)
        clip_path = target_dir / f"{item.clip_id}_{int(item.duration)}s.mp4"

        # Find generator definition
        base_id = item.clip_id.split("_var")[0]
        entry = next((c for c in CURATED_CATALOG if c["id"] == base_id or c["id"] == item.clip_id), CURATED_CATALOG[-1])
        stock_file = entry.get("stock_file")
        stock_path = Path(stock_file).resolve() if stock_file else None

        min_size = 500_000 if (stock_path and stock_path.exists()) else 1024
        if clip_path.exists() and clip_path.stat().st_size > min_size:
            return clip_path

        import imageio_ffmpeg
        ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()

        offset_seconds = 0.0
        if "_var" in item.clip_id:
            try:
                var_num = int(item.clip_id.split("_var")[1])
                offset_seconds = (var_num * 5.0) % 25.0
            except Exception:
                offset_seconds = 5.0

        if stock_path and stock_path.exists():
            cmd = [
                ffmpeg_exe, "-nostdin", "-y",
                "-ss", str(offset_seconds),
                "-stream_loop", "-1",
                "-i", str(stock_path),
                "-t", str(item.duration),
                "-r", "30",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "ultrafast",
                str(clip_path)
            ]
        else:
            filter_str = entry["generator_filter"].format(dur=int(item.duration + 2))
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
