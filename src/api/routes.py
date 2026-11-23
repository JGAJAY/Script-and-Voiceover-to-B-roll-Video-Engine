import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, Header, BackgroundTasks, UploadFile, File, Form, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List

from src.config import settings
from src.api.schemas import (
    BrollJobRequest,
    JobAcceptedResponse,
    JobStatusResponse,
    ClipSwapRequest
)
from src.api.errors import IncuBrixException, IncuBrixErrorCodes
from src.core.job_manager import job_manager
from src.core.pipeline import pipeline_orchestrator
from src.services.storage import storage_service
from src.services.clip_swapper import clip_swapper

logger = logging.getLogger(__name__)
api_router = APIRouter(prefix="/api/v1")

@api_router.post(
    "/broll/jobs",
    response_model=JobAcceptedResponse,
    status_code=202,
    summary="Submit B-roll Video Generation Job",
    description="Submits an audio URL, text script, or scene list to generate a timed, licence-clean B-roll video."
)
async def create_broll_job(
    request: BrollJobRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_data, is_new = await job_manager.get_or_create_job(
        job_id=job_id,
        request=request,
        idempotency_key=idempotency_key
    )

    if not is_new:
        # Return existing job if idempotent retry
        return JobAcceptedResponse(
            job_id=job_data["job_id"],
            status=job_data["status"],
            created_at=job_data["created_at"],
            message="Existing job returned via Idempotency-Key"
        )

    # Launch background job execution
    background_tasks.add_task(pipeline_orchestrator.execute_job, job_id, request)

    return JobAcceptedResponse(
        job_id=job_id,
        status="queued",
        created_at=job_data["created_at"],
        message="Job accepted for processing"
    )

@api_router.post(
    "/broll/jobs/upload",
    response_model=JobAcceptedResponse,
    status_code=202,
    summary="Upload Media and Create Job",
    description="Accepts direct file upload (audio file or script file) to create a video job (Integration Standard #7)."
)
async def upload_and_create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    voice: str = Form("en-IN-female"),
    style: str = Form("bright, modern, real-world footage"),
    aspect_ratios: str = Form("16:9,9:16"),
    avoid: Optional[str] = Form(None),
    burn_in_captions: bool = Form(True),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    content = await file.read()
    
    # Save uploaded file
    saved_path = storage_service.save_upload(content, file.filename or "upload.bin", job_id=job_id)
    ext = saved_path.suffix.lower()

    # Determine whether uploaded file is audio or script
    req_kwargs = {
        "voice": voice,
        "style": style,
        "aspect_ratios": [r.strip() for r in aspect_ratios.split(",") if r.strip()],
        "avoid": [a.strip() for a in avoid.split(",") if a.strip()] if avoid else [],
        "captions": {"burn_in": burn_in_captions, "srt": True}
    }

    if ext in [".txt", ".md"]:
        req_kwargs["script"] = content.decode("utf-8", errors="ignore")
    else:
        req_kwargs["audio_url"] = str(saved_path.resolve())

    broll_req = BrollJobRequest(**req_kwargs)
    job_data, _ = await job_manager.get_or_create_job(
        job_id=job_id,
        request=broll_req,
        idempotency_key=idempotency_key
    )

    background_tasks.add_task(pipeline_orchestrator.execute_job, job_id, broll_req)

    return JobAcceptedResponse(
        job_id=job_id,
        status="queued",
        created_at=job_data["created_at"],
        message="Uploaded file accepted and queued"
    )

@api_router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get Job Status and Results",
    description="Polls job progress (0-100), stage, timings, and result download links."
)
async def get_job_status(job_id: str):
    job = await job_manager.get_job(job_id)
    if not job:
        raise IncuBrixException(
            code=IncuBrixErrorCodes.JOB_NOT_FOUND,
            message=f"Job with ID '{job_id}' does not exist.",
            status_code=404
        )

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        stage=job["stage"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        result=job.get("result"),
        error=job.get("error"),
        timings=job.get("timings")
    )

@api_router.post(
    "/broll/jobs/{job_id}/swap",
    summary="Swap Clip for a Scene",
    description="Replaces footage for a single scene and performs fast partial re-render (Advanced Requirement)."
)
async def swap_clip_endpoint(job_id: str, swap_req: ClipSwapRequest):
    job = await job_manager.get_job(job_id)
    if not job:
        raise IncuBrixException(
            code=IncuBrixErrorCodes.JOB_NOT_FOUND,
            message=f"Job '{job_id}' not found.",
            status_code=404
        )
    if job.get("status") != "succeeded":
        raise IncuBrixException(
            code=IncuBrixErrorCodes.INVALID_INPUT,
            message=f"Job must be in 'succeeded' state before swapping clips. Current: {job.get('status')}",
            status_code=400
        )

    job_dir = storage_service.get_job_dir(job_id)
    aspect_ratios = job.get("request", {}).get("aspect_ratios", ["16:9"])
    burn_in = job.get("request", {}).get("captions", {}).get("burn_in", True)

    swap_result = await clip_swapper.swap_scene_clip(
        job_dir=job_dir,
        swap_req=swap_req,
        aspect_ratios=aspect_ratios,
        burn_in_captions=burn_in
    )

    return {"status": "success", "job_id": job_id, "swap": swap_result}

@api_router.get(
    "/jobs/{job_id}/download/{filename}",
    summary="Download Job Output File",
    description="Downloads generated video, captions.srt, timeline.json, or manifest.json."
)
async def download_job_file(job_id: str, filename: str):
    file_path = storage_service.get_output_path(job_id, filename)
    if not file_path.exists():
        raise IncuBrixException(
            code=IncuBrixErrorCodes.JOB_NOT_FOUND,
            message=f"Requested file '{filename}' for job '{job_id}' does not exist.",
            status_code=404
        )

    media_type = "application/octet-stream"
    if filename.endswith(".mp4"):
        media_type = "video/mp4"
    elif filename.endswith(".srt"):
        media_type = "text/plain"
    elif filename.endswith(".json"):
        media_type = "application/json"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )
