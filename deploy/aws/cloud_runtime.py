#!/usr/bin/env python3
"""
Jarvis OMNIX Workbench Cloud Runtime v1

Minimal safe cloud runtime service for ECS Fargate deployment.
Provides health checks and read-only status reporting without exposing
unauthenticated command/control surfaces.
"""

import json
import logging
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.environ.get('PORT', '3091'))
HOST = os.environ.get('HOST', '0.0.0.0')
STORAGE_PROVIDER = os.environ.get('OMNIX_WORKBENCH_STORAGE_PROVIDER', 'local')
SOURCE_OF_TRUTH = os.environ.get('OMNIX_WORKBENCH_SOURCE_OF_TRUTH', 'local')
AWS_REGION = os.environ.get('OMNIX_WORKBENCH_AWS_REGION', 'us-east-1')


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for health and status endpoints."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use structured logging."""
        logger.info(f"{self.address_string()} - {format % args}")

    def send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_text(self, text: str, status: int = 200) -> None:
        """Send plain text response."""
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(text.encode('utf-8'))

    def do_GET(self) -> None:
        """Handle GET requests."""
        path = self.path

        if path == '/health':
            self.handle_health()
        elif path == '/api/jarvis/status-bundle':
            self.handle_status_bundle()
        elif path == '/':
            self.handle_root()
        else:
            self.send_json({'error': 'Not found'}, 404)

    def handle_health(self) -> None:
        """Health check endpoint - always returns OK if service is running."""
        self.send_json({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'omnix-workbench-cloud-runtime'
        })

    def handle_root(self) -> None:
        """Root endpoint - minimal info."""
        self.send_text('Jarvis OMNIX Workbench Cloud Runtime v1\n')

    def handle_status_bundle(self) -> None:
        """Status bundle endpoint - read-only, no secrets."""
        try:
            # Build a minimal status bundle
            bundle = {
                'schema': 'omnix.jarvis.status_bundle.v1',
                'timestamp': datetime.utcnow().isoformat(),
                'runtime': {
                    'health': {
                        'status': 'ok',
                        'cloudRuntime': 'running',
                    },
                    'missions': [],
                    'pendingApprovals': [],
                },
                'slack': {
                    'installed': os.environ.get('SLACK_BOT_TOKEN') is not None,
                    'configured': os.environ.get('SLACK_BOT_TOKEN') is not None,
                    'continuousOpsRunning': False,  # Read-only check
                },
                'health': {
                    'commandCenter': {'ok': True},
                    'localGateway': {'ok': False},  # No local gateway in cloud
                },
                'safety': {
                    'readOnly': True,
                    'noWrites': True,
                    'noSecrets': True,
                },
                'cloud': {
                    'storageProvider': STORAGE_PROVIDER,
                    'sourceOfTruth': SOURCE_OF_TRUTH,
                    'awsRegion': AWS_REGION,
                    'deployment': 'ecs-fargate',
                }
            }
            self.send_json(bundle)
        except Exception as e:
            logger.error(f"Error generating status bundle: {e}")
            self.send_json({'error': 'Internal server error'}, 500)


def main() -> None:
    """Main entry point."""
    logger.info(f"Starting Jarvis OMNIX Workbench Cloud Runtime v1")
    logger.info(f"Configuration:")
    logger.info(f"  HOST: {HOST}")
    logger.info(f"  PORT: {PORT}")
    logger.info(f"  STORAGE_PROVIDER: {STORAGE_PROVIDER}")
    logger.info(f"  SOURCE_OF_TRUTH: {SOURCE_OF_TRUTH}")
    logger.info(f"  AWS_REGION: {AWS_REGION}")

    # Validate configuration
    if STORAGE_PROVIDER == 'aws':
        required_vars = ['OMNIX_WORKBENCH_MEMORY_BUCKET', 'OMNIX_WORKBENCH_STATE_TABLE']
        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            logger.error(f"Missing required AWS environment variables: {missing}")
            sys.exit(1)

    try:
        server = HTTPServer((HOST, PORT), HealthHandler)
        logger.info(f"Server listening on http://{HOST}:{PORT}")
        logger.info("Endpoints:")
        logger.info("  GET /health - Health check")
        logger.info("  GET /api/jarvis/status-bundle - Status bundle (read-only)")
        server.serve_forever()
    except OSError as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully")
        sys.exit(0)


if __name__ == '__main__':
    main()
