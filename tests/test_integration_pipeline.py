import pytest
import json
import asyncio
from pathlib import Path

from src.config import settings
from src.api.schemas import BrollJobRequest
from src.core.pipeline import pipeline_orchestrator
from src.core.job_manager import job_manager
from src.services.storage import storage_service

@pytest.mark.asyncio
async def test_end_to_end_broll_pipeline(tmp_path):
    job_id = "test_e2e_job_001"
    request = BrollJobRequest(
        script="IncuBrix automated video engine transforms your script into finished footage scene by scene.",
        voice="en-IN-female",
        aspect_ratios=["16:9"],
        style="modern tech clean",
        avoid=["people's faces"],
        captions={"burn_in": False, "srt": True}
    )

    await job_manager.get_or_create_job(job_id, request)
    await pipeline_orchestrator.execute_job(job_id, request)

    job_data = await job_manager.get_job(job_id)
    assert job_data["status"] == "succeeded"
    assert job_data["progress"] == 100

    job_dir = storage_service.get_job_dir(job_id)

    # 1. Check video file
    video_path = job_dir / "video_16-9.mp4"
    assert video_path.exists()
    assert video_path.stat().st_size > 1000

    # 2. Check captions.srt
    srt_path = job_dir / "captions.srt"
    assert srt_path.exists()
    assert len(srt_path.read_text(encoding="utf-8")) > 10

    # 3. Check timeline.json
    timeline_path = job_dir / "timeline.json"
    assert timeline_path.exists()
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert len(timeline["scenes"]) > 0
    first_scene = timeline["scenes"][0]
    assert "clip_id" in first_scene
    assert "licence" in first_scene
    assert "reason_chosen" in first_scene
    assert "relevance_score" in first_scene

    # 4. Check manifest.json
    manifest_path = job_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "cost_estimate" in manifest
    assert "timings" in manifest
    assert "licence_rights_summary" in manifest
    assert manifest["licence_rights_summary"]["commercial_usable"] is True
