from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional

class IncuBrixErrorCodes:
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    SILENT_AUDIO = "SILENT_AUDIO"
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    AUDIO_DOWNLOAD_FAILED = "AUDIO_DOWNLOAD_FAILED"
    TTS_GENERATION_FAILED = "TTS_GENERATION_FAILED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    FOOTAGE_NOT_FOUND = "FOOTAGE_NOT_FOUND"
    FOOTAGE_FETCH_FAILED = "FOOTAGE_FETCH_FAILED"
    RENDER_FAILED = "RENDER_FAILED"
    SWAP_INVALID_SCENE = "SWAP_INVALID_SCENE"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    STORAGE_ERROR = "STORAGE_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"

class IncuBrixException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
                "details": self.details,
            }
        }

async def incubrix_exception_handler(request: Request, exc: IncuBrixException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": IncuBrixErrorCodes.INTERNAL_SERVER_ERROR,
                "message": str(exc),
                "retryable": True,
                "details": {"type": exc.__class__.__name__}
            }
        }
    )
