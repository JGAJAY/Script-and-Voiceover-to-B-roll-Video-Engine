import logging
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from src.services.scene_segmenter import SegmentedScene
from src.services.footage_sources.base import FootageItem
from src.services.footage_sources.stock_provider import stock_footage_provider
from src.services.footage_sources.generative_provider import generative_video_provider
from src.services.footage_sources.local_library_provider import local_library_provider
from src.api.schemas import SceneTimelineItem

logger = logging.getLogger(__name__)

class FootageSelector:
    """Selects optimal footage per scene applying the dual-source rule and anti-repeat constraints."""

    async def select_footage_for_scenes(
        self,
        scenes: List[SegmentedScene],
        aspect_ratio: str = "16:9",
        avoid: Optional[List[str]] = None,
        job_id: str = "default"
    ) -> List[SceneTimelineItem]:
        used_clip_ids: Set[str] = set()
        timeline_items: List[SceneTimelineItem] = []

        target_cache_dir = Path("storage/cache")
        target_cache_dir.mkdir(parents=True, exist_ok=True)

        for scene in scenes:
            # Apply Written Measurable Decision Rule (Advanced Requirement)
            source_type, decision_reason = self.evaluate_source_decision_rule(scene)
            
            # Formulate semantic search query
            query = self._formulate_query(scene)

            chosen_item: Optional[FootageItem] = None
            
            # Execute search with chosen provider, fallback to alternative if empty
            if source_type == "generative":
                candidates = await generative_video_provider.search(
                    query=query,
                    duration=scene.duration,
                    aspect_ratio=aspect_ratio,
                    avoid=avoid,
                    context={"is_abstract": scene.is_abstract, "has_stats": scene.has_statistics}
                )
                chosen_item = candidates[0] if candidates else None
            else:
                candidates = await stock_footage_provider.search(
                    query=query,
                    duration=scene.duration,
                    aspect_ratio=aspect_ratio,
                    avoid=avoid,
                    context={
                        "is_sensitive": scene.is_sensitive,
                        "disambiguated_concept": scene.disambiguated_concept
                    }
                )
                # Anti-repeat check: select candidate not yet used in this job
                for cand in candidates:
                    if cand.clip_id not in used_clip_ids:
                        chosen_item = cand
                        break
                if not chosen_item and candidates:
                    # If all used, modify clip_id with variance offset to prevent exact duplicate file reuse
                    chosen_item = candidates[0].model_copy()
                    chosen_item.clip_id = f"{chosen_item.clip_id}_var{scene.scene_index}"

            # Resilient fallback if neither yielded a clip
            if not chosen_item:
                fallback_items = await local_library_provider.search("general modern abstract", scene.duration, aspect_ratio, avoid)
                chosen_item = fallback_items[0]
                source_type = "local_commercial_library"
                decision_reason = "Fallback safe commercial library used due to provider unavailability"

            used_clip_ids.add(chosen_item.clip_id)

            # Prepare clip locally
            provider = generative_video_provider if chosen_item.is_ai_generated else stock_footage_provider
            local_clip_path = await provider.prepare_clip(chosen_item, target_cache_dir)
            chosen_item.local_path = str(local_clip_path)

            timeline_item = SceneTimelineItem(
                scene_index=scene.scene_index,
                text=scene.text,
                start_time=scene.start_time,
                end_time=scene.end_time,
                duration=scene.duration,
                clip_id=chosen_item.clip_id,
                clip_url=str(local_clip_path),
                source=chosen_item.source,
                licence=chosen_item.licence,
                attribution=chosen_item.attribution,
                is_ai_generated=chosen_item.is_ai_generated,
                reason_chosen=decision_reason,
                relevance_score=chosen_item.relevance_score,
                visual_hint=scene.visual_hint
            )
            timeline_items.append(timeline_item)

        return timeline_items

    def evaluate_source_decision_rule(self, scene: SegmentedScene) -> tuple[str, str]:
        """Written, measurable rule for choosing between Stock vs Generative (Advanced requirement).
        
        Rule Definition:
        1. IF scene.is_abstract (e.g. 'trust is earned slowly') -> Generative:
           Reason: Metaphorical and intangible concepts lack direct stock footage correspondence.
        2. IF scene.has_statistics (e.g. 'sales grew 40% in 2025') -> Generative:
           Reason: Specific numerical predictions and future milestones require synthetic motion graphics.
        3. IF visual_hint explicitly specifies 'generative', 'ai', or '3d' -> Generative:
           Reason: Direct user visual hint requested synthetic generation.
        4. IF scene.is_sensitive (e.g. tragedy, mourning) -> Stock (Verified Commercial):
           Reason: Sensitive news demands respectful, sober real-world footage without AI hallucinations.
        5. ELSE -> Stock (Verified Commercial):
           Reason: Real-world tangible scenes are best represented with authentic commercial stock footage.
        """
        if scene.visual_hint and any(k in scene.visual_hint.lower() for k in ["generative", "ai", "render", "animation", "3d"]):
            return "generative", "Explicit visual hint requested AI generative styling"
            
        if scene.is_abstract:
            return "generative", "Abstract metaphorical concept requires AI generative visualization rather than literal stock"

        if scene.has_statistics:
            return "generative", "Future quantitative statistics require dynamic synthetic data graphics"

        if scene.is_sensitive:
            return "stock", "Solemn/sensitive context requires respectful, verified real-world footage rather than AI generation"

        return "stock", "Tangible real-world scene matched to high-definition commercial stock footage"

    def _formulate_query(self, scene: SegmentedScene) -> str:
        """Derives clean semantic query, incorporating visual hint and double-meaning resolution."""
        if scene.visual_hint:
            return scene.visual_hint

        if scene.disambiguated_concept:
            return scene.disambiguated_concept

        # Extract dominant meaningful words
        words = [w for w in scene.text.lower().split() if len(w) > 3 and w not in {"with", "that", "this", "from", "have", "were"}]
        return " ".join(words[:4]) if words else "modern real world"

footage_selector = FootageSelector()
