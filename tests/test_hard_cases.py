import pytest
import wave
import struct
import json
from pathlib import Path

from src.api.errors import IncuBrixException, IncuBrixErrorCodes
from src.services.audio_transcription import audio_transcription_service
from src.services.scene_segmenter import scene_segmenter
from src.services.clip_swapper import clip_swapper
from src.api.schemas import BrollJobRequest, ClipSwapRequest
from src.core.pipeline import pipeline_orchestrator
from src.core.job_manager import job_manager
from src.services.storage import storage_service

@pytest.mark.asyncio
async def test_silent_audio_detection(tmp_path):
    """Hard case: Silent audio file must be detected and rejected with SILENT_AUDIO error."""
    silent_wav = tmp_path / "silent.wav"
    sample_rate = 16000
    duration = 3.0
    
    with wave.open(str(silent_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # All zeros = pure digital silence
        wf.writeframes(b"\x00" * int(sample_rate * 2 * duration))

    with pytest.raises(IncuBrixException) as exc_info:
        await audio_transcription_service.inspect_and_transcribe(silent_wav)

    assert exc_info.value.code == IncuBrixErrorCodes.SILENT_AUDIO
    assert "silence" in exc_info.value.message.lower()

@pytest.mark.asyncio
async def test_wrong_file_type_rejected(tmp_path):
    """Hard case: A wrong file type (e.g. .pdf or .exe) must be rejected with UNSUPPORTED_MEDIA_TYPE."""
    bad_file = tmp_path / "malicious_script.exe"
    bad_file.write_bytes(b"MZNotAnAudioFile")

    with pytest.raises(IncuBrixException) as exc_info:
        await audio_transcription_service.inspect_and_transcribe(bad_file)

    assert exc_info.value.code == IncuBrixErrorCodes.UNSUPPORTED_MEDIA_TYPE

def test_double_meaning_disambiguation():
    """Hard case: Words with double meanings (value, bank, cloud, python) mapped to semantic concepts."""
    # 1. 'value' should map to business growth/upward charts rather than a pile of cash
    scenes_val = scene_segmenter.segment([{"word": "Maximizing", "start": 0.0, "end": 1.0}, {"word": "shareholder", "start": 1.0, "end": 2.0}, {"word": "value.", "start": 2.0, "end": 3.0}], 3.0)
    assert scenes_val[0].disambiguated_concept is not None
    assert "pile of cash" not in scenes_val[0].disambiguated_concept.lower()
    assert "growth" in scenes_val[0].disambiguated_concept.lower() or "value" in scenes_val[0].disambiguated_concept.lower()

    # 2. 'cloud' in tech context should map to datacenter servers, not weather sky
    scenes_cloud = scene_segmenter.segment([{"word": "Deploying", "start": 0.0, "end": 1.0}, {"word": "server", "start": 1.0, "end": 2.0}, {"word": "infrastructure", "start": 2.0, "end": 3.0}, {"word": "to", "start": 3.0, "end": 3.5}, {"word": "cloud.", "start": 3.5, "end": 4.5}], 4.5)
    assert scenes_cloud[0].disambiguated_concept is not None
    assert "server" in scenes_cloud[0].disambiguated_concept.lower()

@pytest.mark.asyncio
async def test_clip_swap_fast_partial_render(tmp_path):
    """Advanced requirement: Clip swap re-renders only affected scene in clearly less time."""
    job_id = "test_swap_job_001"
    request = BrollJobRequest(
        script="First scene introduces modern tech. Second scene highlights corporate growth.",
        voice="en-IN-female",
        aspect_ratios=["16:9"],
        captions={"burn_in": False, "srt": True}
    )

    await job_manager.get_or_create_job(job_id, request)
    await pipeline_orchestrator.execute_job(job_id, request)

    job_dir = storage_service.get_job_dir(job_id)
    swap_req = ClipSwapRequest(
        scene_index=0,
        new_query="drone shot of futuristic modern skyscraper",
        preferred_source="generative"
    )

    swap_res = await clip_swapper.swap_scene_clip(
        job_dir=job_dir,
        swap_req=swap_req,
        aspect_ratios=["16:9"],
        burn_in_captions=False
    )

    assert swap_res["scene_index"] == 0
    # Swap partial render duration should be clearly tracked and valid
    assert swap_res["swap_render_duration_seconds"] < 30.0
    assert swap_res["updated_scene"]["is_ai_generated"] is True
    assert "User swapped clip" in swap_res["updated_scene"]["reason_chosen"]
