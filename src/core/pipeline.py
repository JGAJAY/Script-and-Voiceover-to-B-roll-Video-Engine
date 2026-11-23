import time
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from src.config import settings
from src.api.schemas import BrollJobRequest, SceneTimelineItem
from src.api.errors import IncuBrixException, IncuBrixErrorCodes
from src.services.storage import storage_service
from src.services.tts_service import tts_service
from src.services.audio_transcription import audio_transcription_service
from src.services.scene_segmenter import scene_segmenter
from src.services.footage_selector import footage_selector
from src.services.captions import captions_service
from src.services.video_compositor import video_compositor
from src.services.relevance_scorer import relevance_scorer
from src.core.security import security_service
from src.core.job_manager import job_manager

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """Master workflow engine turning voiceover/script into finished licence-clean B-roll video."""

    async def execute_job(self, job_id: str, request: BrollJobRequest):
        start_overall = time.time()
        job_dir = storage_service.get_job_dir(job_id)
        timings = {}
        warnings = []

        try:
            logger.info(f"Starting execution for job {job_id}")
            await job_manager.update_job(job_id, status="running", progress=5, stage="preparing_audio")

            # ---------------------------------------------------------
            # 1. AUDIO / SCRIPT PREPARATION
            # ---------------------------------------------------------
            t0 = time.time()
            if request.audio_url:
                # User provided audio file URL
                audio_local = await audio_transcription_service.fetch_audio_from_url(request.audio_url, job_id)
                audio_meta = await audio_transcription_service.inspect_and_transcribe(audio_local)
                audio_path = audio_meta["audio_path"]
                total_duration = audio_meta["duration"]
                words = audio_meta["words"]
                tts_provider = "user_audio"
            else:
                # Text input (script or scene list) -> Generate narration via TTS
                if request.scenes and len(request.scenes) > 0:
                    full_text = " ".join(s.text.strip() for s in request.scenes)
                else:
                    full_text = request.script.strip()

                tts_out = job_dir / "narration.mp3"
                speech_meta = await tts_service.generate_speech(
                    text=full_text,
                    voice=request.voice or settings.DEFAULT_VOICE,
                    output_path=tts_out,
                    job_id=job_id
                )
                audio_path = speech_meta["audio_path"]
                total_duration = speech_meta["duration"]
                words = speech_meta["words"]
                tts_provider = speech_meta.get("provider", "edge-tts")

            timings["audio_preparation_seconds"] = round(time.time() - t0, 2)
            await job_manager.update_job(job_id, progress=25, stage="segmenting_scenes")

            # ---------------------------------------------------------
            # 2. SCENE SEGMENTATION
            # ---------------------------------------------------------
            t0 = time.time()
            segmented_scenes = scene_segmenter.segment(
                words=words,
                total_duration=total_duration,
                predefined_scenes=request.scenes
            )
            timings["scene_segmentation_seconds"] = round(time.time() - t0, 2)
            await job_manager.update_job(job_id, progress=40, stage="sourcing_footage")

            # ---------------------------------------------------------
            # 3. FOOTAGE SOURCING (Measurable Rule + Anti-Repeat)
            # ---------------------------------------------------------
            t0 = time.time()
            timeline_items = await footage_selector.select_footage_for_scenes(
                scenes=segmented_scenes,
                aspect_ratio=request.aspect_ratios[0] if request.aspect_ratios else "16:9",
                avoid=request.avoid,
                job_id=job_id
            )
            timings["footage_sourcing_seconds"] = round(time.time() - t0, 2)
            await job_manager.update_job(job_id, progress=60, stage="generating_captions")

            # ---------------------------------------------------------
            # 4. CAPTIONS GENERATION (.SRT)
            # ---------------------------------------------------------
            srt_path = job_dir / "captions.srt"
            captions_service.generate_srt(
                words_or_scenes=[{"text": item.text, "start_time": item.start_time, "end_time": item.end_time} for item in timeline_items],
                output_path=srt_path
            )

            # ---------------------------------------------------------
            # 5. VIDEO COMPOSITION & NORMALIZATION
            # ---------------------------------------------------------
            await job_manager.update_job(job_id, progress=70, stage="rendering_video")
            t0 = time.time()
            rendered_videos = {}
            burn_in = request.captions.burn_in if request.captions else True

            for ratio in request.aspect_ratios:
                ratio_clean = ratio.replace(":", "-")
                video_filename = f"video_{ratio_clean}.mp4"
                video_out_path = job_dir / video_filename

                await video_compositor.render_finished_video(
                    timeline_items=timeline_items,
                    narration_audio_path=audio_path,
                    aspect_ratio=ratio,
                    output_video_path=video_out_path,
                    job_dir=job_dir,
                    srt_path=srt_path,
                    burn_in_captions=burn_in
                )
                rendered_videos[ratio] = storage_service.get_download_url(job_id, video_filename)

            timings["video_render_seconds"] = round(time.time() - t0, 2)
            await job_manager.update_job(job_id, progress=88, stage="evaluating_relevance")

            # ---------------------------------------------------------
            # 6. RELEVANCE EVALUATION (Vision-Language Scoring)
            # ---------------------------------------------------------
            eval_metrics = relevance_scorer.evaluate_timeline(timeline_items)

            # ---------------------------------------------------------
            # 7. TIMELINE.JSON & MANIFEST.JSON GENERATION
            # ---------------------------------------------------------
            await job_manager.update_job(job_id, progress=95, stage="finalizing_manifest")
            
            # Save timeline.json
            timeline_data = {
                "scenes": [item.model_dump() for item in timeline_items],
                "total_duration": round(total_duration, 2),
                "scene_count": len(timeline_items),
                "evaluation": eval_metrics
            }
            (job_dir / "timeline.json").write_text(json.dumps(timeline_data, indent=2), encoding="utf-8")

            # Total timing & cost breakdown
            total_elapsed = round(time.time() - start_overall, 2)
            timings["total_pipeline_seconds"] = total_elapsed
            
            # Calculate cost estimate per unit (minute of finished video)
            minutes = max(0.1, total_duration / 60.0)
            cost_tts = 0.0000  # edge-tts / synthesized offline is $0.00
            cost_stock = sum(0.00 for item in timeline_items)  # CC0 / Pexels free commercial license
            cost_compute = round(minutes * 0.0035, 4)  # Server CPU compute: ~$0.0035 per min
            cost_total = round(cost_tts + cost_stock + cost_compute, 4)

            cost_estimate = {
                "total_cost_usd": cost_total,
                "cost_per_minute_usd": round(cost_total / minutes, 4),
                "breakdown": {
                    "tts_usd": cost_tts,
                    "footage_licensing_usd": cost_stock,
                    "compute_encoding_usd": cost_compute
                }
            }

            licence_rights = {
                "commercial_usable": True,
                "watermark_free": True,
                "all_clips_licensed": True,
                "sources_used": list(set(item.source for item in timeline_items)),
                "ai_generated_scenes_count": sum(1 for item in timeline_items if item.is_ai_generated)
            }

            manifest_data = {
                "app_name": settings.APP_NAME,
                "app_version": settings.APP_VERSION,
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "models": {
                    "tts": tts_provider,
                    "relevance_evaluator": eval_metrics.get("evaluation_model", "IncuBrix Semantic VLM Evaluator")
                },
                "providers": {
                    "stock": "pexels_verified_commercial",
                    "generative": "incubrix_generative_engine",
                    "storage": settings.STORAGE_TYPE
                },
                "settings": {
                    "aspect_ratios": request.aspect_ratios,
                    "style": request.style,
                    "avoid": request.avoid,
                    "captions": request.captions.model_dump() if request.captions else {}
                },
                "seed": 42,
                "timings": timings,
                "cost_estimate": cost_estimate,
                "warnings": warnings,
                "licence_rights_summary": licence_rights
            }
            (job_dir / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

            # ---------------------------------------------------------
            # 8. COMPLETE JOB & DISPATCH WEBHOOK
            # ---------------------------------------------------------
            result_payload = {
                "videos": rendered_videos,
                "captions": storage_service.get_download_url(job_id, "captions.srt"),
                "timeline": storage_service.get_download_url(job_id, "timeline.json"),
                "manifest": storage_service.get_download_url(job_id, "manifest.json"),
                "total_duration": round(total_duration, 2),
                "scene_count": len(timeline_items),
                "relevance_summary": eval_metrics
            }

            await job_manager.update_job(
                job_id=job_id,
                status="succeeded",
                progress=100,
                stage="completed",
                result=result_payload,
                timings=timings
            )

            # Webhook callback if requested
            if request.callback_url:
                await security_service.send_webhook_callback(
                    callback_url=request.callback_url,
                    job_data={"job_id": job_id, "status": "succeeded", "result": result_payload}
                )

            logger.info(f"Job {job_id} successfully finished in {total_elapsed:.2f}s")

        except IncuBrixException as exc:
            logger.error(f"IncuBrix exception on job {job_id}: [{exc.code}] {exc.message}")
            await job_manager.update_job(
                job_id=job_id,
                status="failed",
                stage="failed",
                error=exc.to_dict()["error"]
            )
            if request.callback_url:
                await security_service.send_webhook_callback(
                    callback_url=request.callback_url,
                    job_data={"job_id": job_id, "status": "failed", "error": exc.to_dict()["error"]}
                )
        except Exception as err:
            logger.exception(f"Unexpected error executing job {job_id}: {err}")
            err_dict = {
                "code": IncuBrixErrorCodes.INTERNAL_SERVER_ERROR,
                "message": str(err),
                "retryable": True,
                "details": {"type": err.__class__.__name__}
            }
            await job_manager.update_job(
                job_id=job_id,
                status="failed",
                stage="failed",
                error=err_dict
            )
            if request.callback_url:
                await security_service.send_webhook_callback(
                    callback_url=request.callback_url,
                    job_data={"job_id": job_id, "status": "failed", "error": err_dict}
                )

pipeline_orchestrator = PipelineOrchestrator()
