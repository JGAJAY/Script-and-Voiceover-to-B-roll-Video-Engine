import uuid
import time
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from src.config import settings
from src.logging_config import setup_logging, correlation_id_ctx
from src.api.routes import api_router
from src.api.errors import (
    IncuBrixException,
    incubrix_exception_handler,
    generic_exception_handler
)

# Initialize structured JSON logging
setup_logging(level="DEBUG" if settings.DEBUG else "INFO")
logger = logging.getLogger("incubrix.api")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="IncuBrix Script & Voiceover to B-roll Video Engine API (IncuBrix Engineering Assessment 3)",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(IncuBrixException, incubrix_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Structured JSON logging middleware with Correlation-ID
@app.middleware("http")
async def correlation_and_logging_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-Id") or f"corr_{uuid.uuid4().hex[:10]}"
    token = correlation_id_ctx.set(corr_id)
    start_time = time.time()

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Correlation-Id"] = corr_id
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms)",
            extra={"correlation_id": corr_id}
        )
        return response
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unhandled error on {request.method} {request.url.path} ({duration_ms}ms): {exc}",
            extra={"correlation_id": corr_id}
        )
        raise
    finally:
        correlation_id_ctx.reset(token)

# Health & Ready endpoints (Integration Standard #8)
@app.get("/health", summary="Liveness Health Check")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

@app.get("/ready", summary="Readiness Check")
async def readiness_check():
    # Verify ffmpeg presence
    import imageio_ffmpeg
    ffmpeg_exe = settings.FFMPEG_PATH or imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_ready = Path(ffmpeg_exe).exists()
    storage_ready = Path(settings.STORAGE_DIR).exists()

    is_ready = ffmpeg_ready and storage_ready
    status_code = 200 if is_ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "dependencies": {
                "ffmpeg": ffmpeg_ready,
                "storage": storage_ready
            }
        }
    )

# Include API v1 routes
app.include_router(api_router)

# Mount Web Demo static files and index
web_dir = Path(__file__).parent / "web"
static_dir = web_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_demo_ui():
    index_file = web_dir / "templates" / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>IncuBrix B-Roll Engine is Running</h1><p><a href='/docs'>View API Docs</a></p>")
