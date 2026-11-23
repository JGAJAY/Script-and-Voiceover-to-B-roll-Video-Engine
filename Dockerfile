FROM python:3.11-slim

# Install system dependencies including FFmpeg and fonts for subtitle rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY pyproject.toml requirements.txt* ./
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    pydantic-settings \
    python-multipart \
    httpx \
    numpy \
    pillow \
    requests \
    openpyxl \
    edge-tts \
    pytest \
    pytest-asyncio

# Copy application source code
COPY . /app

# Ensure storage directories exist
RUN mkdir -p /app/storage/uploads /app/storage/outputs /app/storage/cache

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
