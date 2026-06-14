# Dockerfile for Jarvis OMNIX Workbench Cloud Runtime
# This container runs the Mission Control bridge and OMNIX Workbench

FROM public.ecr.aws/docker/library/node:20-alpine

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    git \
    curl

# Set working directory
WORKDIR /app

# Copy Mission Control bridge files
COPY package*.json ./
RUN npm ci --only=production

COPY . .

# Copy OpenJarvis workbench
COPY /Users/user/OpenJarvis /opt/openjarvis
RUN pip3 install -e /opt/openjarvis

# Create workspace directory
RUN mkdir -p /app/openclaw-workspace/state/omnix

# Environment variables
ENV PORT=3091
ENV HOST=0.0.0.0
ENV OMNIX_WORKBENCH_STORAGE_PROVIDER=aws
ENV OMNIX_WORKBENCH_SOURCE_OF_TRUTH=cloud
ENV OPENCLAW_WORKSPACE_DIR=/app/openclaw-workspace

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3091/health || exit 1

# Expose port
EXPOSE 3091

# Run Mission Control bridge
CMD ["node", "server.js"]
