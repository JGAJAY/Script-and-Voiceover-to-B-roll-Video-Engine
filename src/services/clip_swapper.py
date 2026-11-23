import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from src.config import settings
from src.api.schemas import ClipSwapRequest, SceneTimelineItem
from src.api.errors import IncuBrixException, IncuBrixErrorCodes
from src.services.footage_sources.base import FootageItem
from src.services.footage_sources.stock_provider import stock_footage_provider
from src.services.footage_sources.generative_provider import generative_video_provider
from src.services.video_compositor import video_compositor

logger = logging.getLogger(__name__)

class ClipSwapper:
    """Handles single-scene clip replacement with fast partial re-rendering."""

    async def swap_scene_clip(
        self,
        job_dir: Path,
        swap_req: ClipSwapRequest,
        aspect_ratios: list[str],
        burn_in_captions: bool = True
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        timeline_path = job_dir / "timeline.json"
        manifest_path = job_dir / "manifest.json"
        audio_path = job_dir / "narration.mp3"
        srt_path = job_dir / "captions.srt"

        if not timeline_path.exists():
            raise IncuBrixException(
                code=IncuBrixErrorCodes.JOB_NOT_FOUND,
                message="Cannot swap clip: timeline.json not found for this job.",
                status_code=404
            )

        timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
        scenes = timeline_data.get("scenes", [])
        
        idx = swap_req.scene_index
        if idx < 0 or idx >= len(scenes):
            raise IncuBrixException(
                code=IncuBrixErrorCodes.SWAP_INVALID_SCENE,
                message=f"Invalid scene_index {idx}. Valid range is 0 to {len(scenes) - 1}.",
                status_code=400,
                details={"provided_index": idx, "scene_count": len(scenes)}
            )

        target_scene = scenes[idx]
        query = swap_req.new_query or target_scene.get("text", "modern visual")
        duration = float(target_scene.get("duration", 4.0))

        # Select new footage based on preference or query
        preferred = swap_req.preferred_source or ("generative" if target_scene.get("is_ai_generated") else "stock")
        cache_dir = Path(settings.STORAGE_DIR) / "cache"

        if preferred == "generative":
            candidates = await generative_video_provider.search(query, duration)
            new_item = candidates[0]
            local_clip = await generative_video_provider.prepare_clip(new_item, cache_dir)
            reason = f"User swapped clip to Generative AI visualization for: '{query}'"
        else:
            candidates = await stock_footage_provider.search(query, duration)
            new_item = candidates[0]
            local_clip = await stock_footage_provider.prepare_clip(new_item, cache_dir)
            reason = f"User swapped clip to verified Stock Footage for: '{query}'"

        # Update scene metadata in timeline
        target_scene["clip_id"] = new_item.clip_id
        target_scene["clip_url"] = str(local_clip)
        target_scene["source"] = new_item.source
        target_scene["licence"] = new_item.licence
        target_scene["attribution"] = new_item.attribution
        target_scene["is_ai_generated"] = new_item.is_ai_generated
        target_scene["reason_chosen"] = reason
        target_scene["relevance_score"] = new_item.relevance_score

        # Save updated timeline.json
        timeline_path.write_text(json.dumps(timeline_data, indent=2), encoding="utf-8")

        # Convert back to SceneTimelineItem objects
        timeline_objs = [SceneTimelineItem(**s) for s in scenes]
        swapped_item_obj = timeline_objs[idx]

        # Re-render ONLY the swapped scene segment across requested aspect ratios
        re_rendered_videos = {}
        for ratio in aspect_ratios:
            ratio_clean = ratio.replace(":", "-")
            segments_dir = job_dir / f"segments_{ratio_clean}"
            seg_path = segments_dir / f"scene_{idx:03d}.mp4"

            # 1. Re-render single segment
            await video_compositor.render_scene_clip(swapped_item_obj, ratio, seg_path)

            # 2. Fast stream-copy concat & mux (no re-encoding of unchanged segments!)
            ratio_filename = f"video_{ratio_clean}.mp4"
            final_out_path = job_dir / ratio_filename
            await video_compositor.recompose_from_cached_segments(
                job_dir=job_dir,
                aspect_ratio=ratio,
                narration_audio_path=audio_path,
                output_video_path=final_out_path,
                scene_count=len(scenes),
                srt_path=srt_path,
                burn_in_captions=burn_in_captions
            )
            re_rendered_videos[ratio] = final_out_path.name

        swap_duration = time.time() - start_time
        logger.info(f"Clip swap for scene {idx} completed in {swap_duration:.2f} seconds (fast partial re-render).")

        return {
            "scene_index": idx,
            "swap_render_duration_seconds": round(swap_duration, 2),
            "updated_scene": target_scene,
            "re_rendered_videos": re_rendered_videos
        }

clip_swapper = ClipSwapper()
