import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Union, BinaryIO
from src.config import settings

class StorageService:
    def __init__(self):
        self.storage_dir = Path(settings.STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir = self.storage_dir / "uploads"
        self.outputs_dir = self.storage_dir / "outputs"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, file_bytes: bytes, filename: str, job_id: Optional[str] = None) -> Path:
        prefix = f"{job_id}_" if job_id else ""
        safe_filename = f"{prefix}{Path(filename).name}"
        dest_path = self.uploads_dir / safe_filename
        dest_path.write_bytes(file_bytes)
        return dest_path

    def save_output(self, file_path_or_bytes: Union[str, Path, bytes], job_id: str, filename: str) -> Path:
        job_dir = self.outputs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        dest_path = job_dir / filename
        
        if isinstance(file_path_or_bytes, (str, Path)):
            src_path = Path(file_path_or_bytes)
            if src_path != dest_path:
                shutil.copy2(src_path, dest_path)
        else:
            dest_path.write_bytes(file_path_or_bytes)
            
        return dest_path

    def get_output_path(self, job_id: str, filename: str) -> Path:
        return self.outputs_dir / job_id / filename

    def get_download_url(self, job_id: str, filename: str) -> str:
        # Returns public download route
        return f"{settings.BASE_URL}/api/v1/jobs/{job_id}/download/{filename}"

    def get_job_dir(self, job_id: str) -> Path:
        job_dir = self.outputs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

storage_service = StorageService()
