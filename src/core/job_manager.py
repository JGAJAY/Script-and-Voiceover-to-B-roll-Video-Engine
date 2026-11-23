import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from src.config import settings
from src.api.schemas import JobStatusResponse, BrollJobRequest
from src.api.errors import IncuBrixException, IncuBrixErrorCodes

logger = logging.getLogger(__name__)

class JobManager:
    """Manages background job state, progress tracking, and idempotency mapping."""

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_job(
        self,
        job_id: str,
        request: BrollJobRequest,
        idempotency_key: Optional[str] = None
    ) -> tuple[Dict[str, Any], bool]:
        """Returns (job_dict, is_new). If idempotency_key matches an existing job, returns it."""
        async with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_map:
                existing_id = self._idempotency_map[idempotency_key]
                logger.info(f"Idempotent request matched existing job {existing_id} for key '{idempotency_key}'")
                return self._jobs[existing_id], False

            now = datetime.now(timezone.utc).isoformat()
            job = {
                "job_id": job_id,
                "status": "queued",
                "progress": 0,
                "stage": "queued",
                "created_at": now,
                "updated_at": now,
                "request": request.model_dump(),
                "result": None,
                "error": None,
                "timings": {}
            }
            self._jobs[job_id] = job
            if idempotency_key:
                self._idempotency_map[idempotency_key] = job_id

            self._persist_job_state(job_id)
            return job, True

    async def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        timings: Optional[Dict[str, float]] = None
    ):
        """Updates job state in memory and persists to disk."""
        async with self._lock:
            if job_id not in self._jobs:
                return

            job = self._jobs[job_id]
            if status:
                job["status"] = status
            if progress is not None:
                job["progress"] = progress
            if stage:
                job["stage"] = stage
            if result is not None:
                job["result"] = result
            if error is not None:
                job["error"] = error
            if timings is not None:
                job["timings"].update(timings)

            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._persist_job_state(job_id)

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]

        # Check disk if restarted
        state_file = Path(settings.STORAGE_DIR) / "outputs" / job_id / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                async with self._lock:
                    self._jobs[job_id] = data
                return data
            except Exception:
                pass
        return None

    def _persist_job_state(self, job_id: str):
        try:
            job = self._jobs.get(job_id)
            if not job:
                return
            out_dir = Path(settings.STORAGE_DIR) / "outputs" / job_id
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "state.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Failed to persist state for {job_id}: {e}")

job_manager = JobManager()
