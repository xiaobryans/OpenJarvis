# Dockerfile for Jarvis OMNIX Workbench Cloud Runtime
# Minimal Python HTTP server for health checks and status reporting

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy cloud runtime script
COPY deploy/aws/cloud_runtime.py /app/cloud_runtime.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV PORT=3091
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3091/health || exit 1

# Expose port
EXPOSE 3091

# Run cloud runtime
CMD ["python3", "/app/cloud_runtime.py"]
