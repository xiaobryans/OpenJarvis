# VANTA WhatsApp webhook — Railway deploy (Dockerfile build).
# Avoids the nixpacks "$NIXPACKS_PATH undefined" error by using a plain,
# reproducible Python image. Serves only the lean webhook entrypoint.

FROM python:3.12-slim

# Minimal system deps. (The lean webhook entrypoint does NOT import the voice
# pipeline, so PortAudio/etc. are intentionally not installed.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata + source, then install with the server extra only
# (fastapi/uvicorn/python-multipart) — not the ML/desktop extras.
COPY pyproject.toml README* ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[server,scheduler]"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Railway provides $PORT. Bind the lean webhook app.
CMD ["sh", "-c", "uvicorn openjarvis.server.railway_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
