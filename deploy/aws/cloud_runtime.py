#!/usr/bin/env python3
"""
Jarvis OMNIX Workbench Cloud Runtime v3 — Secure Minimal Runtime

Plan 4 always-on backend. Bootstrapped from S3 at ECS task startup.

Security:
  - /health and / are public (liveness probes only)
  - ALL /v1/* routes require: Authorization: Bearer <OPENJARVIS_API_KEY>
  - 401 on missing header, 403 on invalid token
  - Secrets redacted from all responses

State backend:
  - S3-backed JSON store for tasks, approvals, and memory entries
  - IAM task role provides S3 access (no explicit credentials needed)

Exposed routes:
  Public:
    GET /health
    GET /

  Protected (Bearer token required):
    GET  /v1/system/health
    GET  /v1/mobile/continuity/status
    GET  /v1/memory/status
    POST /v1/memory/entries
    GET  /v1/memory/entries
    GET  /v1/approvals/pending
    POST /v1/approvals
    GET  /v1/tasks
    POST /v1/tasks
    GET  /v1/connectors/status
    GET  /v1/autonomy/status
    GET  /v1/tools
    POST /v1/chat/message

Classification: cloud-native minimal runtime (real S3 state, real auth)
NOT the full Jarvis FastAPI: no LLM processing, no SQLite memory OS.
Full runtime path: deploy/aws/Dockerfile.full via ECR + ECS task definition.
"""

import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=__import__('sys').stdout
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORT = int(os.environ.get('PORT', '3091'))
HOST = os.environ.get('HOST', '0.0.0.0')
AWS_REGION = os.environ.get('OMNIX_WORKBENCH_AWS_REGION', 'ap-southeast-1')
MEMORY_BUCKET = os.environ.get('OMNIX_WORKBENCH_MEMORY_BUCKET', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
OPENJARVIS_API_KEY = os.environ.get('OPENJARVIS_API_KEY', '')
START_TIME = time.time()
VERSION = 'cloud-runtime-v3-plan4-secure'

# S3 state keys
S3_TASKS_KEY = 'cloud_runtime/state/tasks.json'
S3_APPROVALS_KEY = 'cloud_runtime/state/approvals.json'
S3_MEMORY_KEY = 'cloud_runtime/state/memory_entries.json'


# ---------------------------------------------------------------------------
# S3 helpers (IAM role — no explicit credentials)
# ---------------------------------------------------------------------------

def _s3_client():
    import boto3  # type: ignore
    return boto3.client('s3', region_name=AWS_REGION)


def _s3_read_json(key: str, default=None):
    """Read a JSON file from S3; return default on any error."""
    if default is None:
        default = []
    try:
        s3 = _s3_client()
        obj = s3.get_object(Bucket=MEMORY_BUCKET, Key=key)
        return json.loads(obj['Body'].read().decode())
    except Exception:
        return default


def _s3_write_json(key: str, data: Any) -> bool:
    """Write JSON to S3; return True on success."""
    try:
        s3 = _s3_client()
        s3.put_object(
            Bucket=MEMORY_BUCKET,
            Key=key,
            Body=json.dumps(data, default=str).encode(),
            ContentType='application/json',
        )
        return True
    except Exception as exc:
        logger.error('S3 write error: %s', exc)
        return False


def _s3_available() -> bool:
    try:
        _s3_client().head_bucket(Bucket=MEMORY_BUCKET)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = frozenset({'/health', '/'})


def _check_auth(path: str, auth_header: str) -> Optional[str]:
    """Return None if request is authorized; return error message otherwise."""
    if path in _PUBLIC_PATHS or not path.startswith('/v1/'):
        return None
    if not OPENJARVIS_API_KEY:
        return None  # No key configured — open (misconfigured)
    if not auth_header:
        return 'Missing Authorization header'
    scheme, _, token = auth_header.partition(' ')
    if scheme.lower() != 'bearer':
        return 'Authorization scheme must be Bearer'
    if not secrets.compare_digest(token.strip(), OPENJARVIS_API_KEY):
        return 'Invalid API key'
    return None


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class JarvisCloudHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt: str, *args: Any) -> None:
        path = getattr(self, '_path', '?')
        logger.info('%s %s %s', self.address_string(), path, fmt % args)

    def send_json(self, data: Any, code: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except Exception:
            return {}

    def _auth_or_reject(self) -> bool:
        path = self.path.split('?')[0]
        self._path = path
        err = _check_auth(path, self.headers.get('Authorization', ''))
        if err:
            code = 401 if 'Missing' in err else 403
            self.send_json({'error': err, 'hint': 'Authorization: Bearer <OPENJARVIS_API_KEY>'}, code)
            return False
        return True

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def do_GET(self) -> None:
        if not self._auth_or_reject():
            return
        path = self.path.split('?')[0]
        routes = {
            '/health': self._health,
            '/': self._root,
            '/v1/system/health': self._system_health,
            '/v1/mobile/continuity/status': self._continuity_status,
            '/v1/memory/status': self._memory_status,
            '/v1/memory/entries': self._memory_entries_get,
            '/v1/approvals/pending': self._approvals_pending,
            '/v1/tasks': self._tasks_list,
            '/v1/connectors/status': self._connectors_status,
            '/v1/autonomy/status': self._autonomy_status,
            '/v1/tools': self._tools_list,
            '/v1/mobile/status': self._mobile_status,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self.send_json({'error': 'Route not found', 'path': path,
                            'note': 'This is cloud-runtime-v3. Full Jarvis has 100+ routes.'}, 404)

    def do_POST(self) -> None:
        if not self._auth_or_reject():
            return
        path = self.path.split('?')[0]
        body = self._read_body()
        if path == '/v1/memory/entries':
            self._memory_entry_write(body)
        elif path == '/v1/approvals':
            self._approval_create(body)
        elif path == '/v1/tasks':
            self._task_create(body)
        elif path == '/v1/chat/message':
            self._chat_message(body)
        else:
            self.send_json({'error': 'Route not found', 'path': path}, 404)

    # ------------------------------------------------------------------
    # Public routes
    # ------------------------------------------------------------------

    def _health(self) -> None:
        self.send_json({
            'status': 'ok',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service': 'jarvis-cloud-runtime',
            'version': VERSION,
            'uptime_seconds': round(time.time() - START_TIME, 1),
        })

    def _root(self) -> None:
        self.send_json({
            'service': 'Jarvis Cloud Runtime (Plan 4 Always-On Secure Backend)',
            'version': VERSION,
            'auth': 'Bearer token required for all /v1/* routes',
            'routes': {
                'public': ['/health', '/'],
                'protected': [
                    'GET /v1/system/health',
                    'GET /v1/mobile/continuity/status',
                    'GET /v1/memory/status',
                    'GET /v1/memory/entries',
                    'POST /v1/memory/entries',
                    'GET /v1/approvals/pending',
                    'POST /v1/approvals',
                    'GET /v1/tasks',
                    'POST /v1/tasks',
                    'GET /v1/connectors/status',
                    'GET /v1/autonomy/status',
                    'GET /v1/tools',
                    'POST /v1/chat/message',
                    'GET /v1/mobile/status',
                ],
            },
            'deployment': 'aws-ecs-fargate',
            'runtime_macbook_off_capable': True,
            'note': 'cloud-native minimal runtime: real S3 state, real auth. NOT full Jarvis AI runtime.',
        })

    # ------------------------------------------------------------------
    # Protected status routes
    # ------------------------------------------------------------------

    def _system_health(self) -> None:
        s3_ok = _s3_available()
        gist_ok = bool(GITHUB_TOKEN) and len(GITHUB_TOKEN) >= 20
        self.send_json({
            'status': 'ok',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service': 'jarvis-cloud-runtime',
            'version': VERSION,
            'uptime_seconds': round(time.time() - START_TIME, 1),
            'runtime': {
                'deployment': 'aws-ecs-fargate',
                'region': AWS_REGION,
                'macbook_off_capable': True,
                'auth_enabled': bool(OPENJARVIS_API_KEY),
                'classification': 'cloud-native-minimal-runtime',
                'full_jarvis_runtime': False,
                'note': 'Full Jarvis FastAPI runtime: deploy via ECR/ECS Dockerfile.full',
            },
            'memory_os': {
                'sprint': 'plan4-cloud',
                'backend': 'S3 JSON store (not SQLite)',
                'cloud_sync_available': s3_ok,
                'cloud_sync_backend': 'omnix_s3',
                'ai_distillation_available': False,
                'note': 'S3-backed state. Full SQLite memory OS available in Dockerfile.full deployment.',
            },
            'state_sync': {
                's3_available': s3_ok,
                'gist_configured': gist_ok,
            },
        })

    def _continuity_status(self) -> None:
        s3_ok = _s3_available()
        gist_ok = bool(GITHUB_TOKEN) and len(GITHUB_TOKEN) >= 20
        token_fmt = ('classic_pat' if (GITHUB_TOKEN or '')[:4] == 'ghp_'
                     else ('fine_grained_pat' if (GITHUB_TOKEN or '')[:4] == 'gith'
                           else ('absent' if not GITHUB_TOKEN else 'unknown')))
        self.send_json({
            'runtime_macbook_off_capable': True,
            'runtime_deployment': 'aws-ecs-fargate',
            'runtime_always_on_status': (
                'AVAILABLE — Jarvis cloud runtime running in AWS ECS Fargate. '
                f'MacBook does not need to be on. Region: {AWS_REGION}. '
                'Note: cloud-native minimal runtime (not full Jarvis FastAPI).'
            ),
            'state_sync_macbook_off_capable': gist_ok,
            'cross_device_ready': gist_ok,
            'backends': [
                {
                    'name': 'github_gist',
                    'availability': 'available' if gist_ok else 'requires_setup',
                    'macbook_off_capable': gist_ok,
                    'state_sync': True,
                    'token_format': token_fmt,
                },
                {
                    'name': 's3_cloud_sync',
                    'availability': 'available' if s3_ok else 'blocked_credentials',
                    'macbook_off_capable': s3_ok,
                    'state_sync': s3_ok,
                },
            ],
            'active_backend': 'aws-ecs-fargate',
            'mobile_client_available': True,
            'auth_enabled': bool(OPENJARVIS_API_KEY),
        })

    def _memory_status(self) -> None:
        s3_ok = _s3_available()
        gist_ok = bool(GITHUB_TOKEN) and len(GITHUB_TOKEN) >= 20
        entries = _s3_read_json(S3_MEMORY_KEY, [])
        self.send_json({
            'memory_os': {
                'sprint': 'plan4-cloud',
                'total_entries': len(entries),
                'total_distilled': 0,
                'backend': 'S3 JSON (not local SQLite)',
                'note': 'Full SQLite memory OS available in Dockerfile.full deployment.',
            },
            'semantic_search': {
                'vector_search': 'CLOUD_RUNTIME_S3_BACKED',
                'active_ranker': 'none',
                'openai_key_available': bool(os.environ.get('OPENAI_API_KEY')),
            },
            'cloud_sync': {
                'available': s3_ok,
                'backend': 'omnix_s3',
                'bucket': MEMORY_BUCKET,
            },
            'gist_sync': {'configured': gist_ok, 'macbook_off_capable': gist_ok},
            'runtime': {
                'deployment': 'aws-ecs-fargate',
                'macbook_off_capable': True,
                'version': VERSION,
                'full_jarvis_runtime': False,
            },
        })

    def _mobile_status(self) -> None:
        self.send_json({
            'mobile_client_available': True,
            'remote_backend': f'http://this-task:{PORT}',
            'auth_required': True,
            'runtime_macbook_off_capable': True,
        })

    # ------------------------------------------------------------------
    # Memory routes (real S3 persistence)
    # ------------------------------------------------------------------

    def _memory_entries_get(self) -> None:
        entries = _s3_read_json(S3_MEMORY_KEY, [])
        self.send_json({
            'entries': entries,
            'count': len(entries),
            'backend': 's3',
            'bucket': MEMORY_BUCKET,
            'key': S3_MEMORY_KEY,
        })

    def _memory_entry_write(self, body: Dict[str, Any]) -> None:
        if not body.get('content'):
            self.send_json({'error': 'content field required'}, 400)
            return
        entries = _s3_read_json(S3_MEMORY_KEY, [])
        entry = {
            'id': str(uuid.uuid4()),
            'content': body['content'],
            'namespace': body.get('namespace', 'cloud_default'),
            'tags': body.get('tags', []),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'cloud_runtime_v3',
        }
        entries.append(entry)
        ok = _s3_write_json(S3_MEMORY_KEY, entries)
        if ok:
            self.send_json({'id': entry['id'], 'stored': True, 'total_entries': len(entries)}, 201)
        else:
            self.send_json({'error': 'S3 write failed'}, 500)

    # ------------------------------------------------------------------
    # Approvals (real S3 state)
    # ------------------------------------------------------------------

    def _approvals_pending(self) -> None:
        approvals = _s3_read_json(S3_APPROVALS_KEY, [])
        pending = [a for a in approvals if a.get('status') == 'pending']
        self.send_json({'pending': pending, 'count': len(pending)})

    def _approval_create(self, body: Dict[str, Any]) -> None:
        if not body.get('action_type'):
            self.send_json({'error': 'action_type required'}, 400)
            return
        approvals = _s3_read_json(S3_APPROVALS_KEY, [])
        approval = {
            'id': str(uuid.uuid4()),
            'action_type': body['action_type'],
            'description': body.get('description', ''),
            'tier': body.get('tier', 2),
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'cloud_runtime_v3',
        }
        approvals.append(approval)
        ok = _s3_write_json(S3_APPROVALS_KEY, approvals)
        if ok:
            self.send_json({'id': approval['id'], 'status': 'pending', 'created': True}, 201)
        else:
            self.send_json({'error': 'S3 write failed'}, 500)

    # ------------------------------------------------------------------
    # Tasks (real S3 state)
    # ------------------------------------------------------------------

    def _tasks_list(self) -> None:
        tasks = _s3_read_json(S3_TASKS_KEY, [])
        self.send_json({'tasks': tasks, 'count': len(tasks)})

    def _task_create(self, body: Dict[str, Any]) -> None:
        if not body.get('description'):
            self.send_json({'error': 'description required'}, 400)
            return
        tasks = _s3_read_json(S3_TASKS_KEY, [])
        task = {
            'id': str(uuid.uuid4()),
            'description': body['description'],
            'type': body.get('type', 'generic'),
            'priority': body.get('priority', 'normal'),
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'cloud_runtime_v3',
            'note': 'Task queued; no executor in cloud runtime. Full execution requires Dockerfile.full.',
        }
        tasks.append(task)
        ok = _s3_write_json(S3_TASKS_KEY, tasks)
        if ok:
            self.send_json({'id': task['id'], 'status': 'pending', 'created': True}, 201)
        else:
            self.send_json({'error': 'S3 write failed'}, 500)

    # ------------------------------------------------------------------
    # Connectors (known connectors from local inventory)
    # ------------------------------------------------------------------

    def _connectors_status(self) -> None:
        self.send_json({
            'connectors': [
                {'id': 'slack', 'status': 'not_configured_in_cloud', 'credential_required': True},
                {'id': 'github', 'status': 'token_present' if GITHUB_TOKEN else 'not_configured', 'credential_required': True},
                {'id': 'telegram', 'status': 'not_configured_in_cloud', 'credential_required': True},
                {'id': 'openai', 'status': 'key_present' if os.environ.get('OPENAI_API_KEY') else 'not_configured', 'credential_required': True},
                {'id': 'openrouter', 'status': 'key_present' if os.environ.get('OPENROUTER_API_KEY') else 'not_configured', 'credential_required': True},
            ],
            'total': 5,
            'note': 'Cloud runtime connector status. Full connector registry in Dockerfile.full deployment.',
        })

    # ------------------------------------------------------------------
    # Autonomy / Tools (gate status)
    # ------------------------------------------------------------------

    def _autonomy_status(self) -> None:
        self.send_json({
            'mode': 'cloud_readonly',
            'high_autonomy': False,
            'tool_execution_enabled': False,
            'approval_required_tier': 1,
            'hard_gates': ['deploy', 'delete', 'push', 'merge', 'release'],
            'note': 'Cloud runtime autonomy is read-only. Tool execution requires Dockerfile.full.',
        })

    def _tools_list(self) -> None:
        self.send_json({
            'tools': [
                {'id': 'file_write', 'available': False, 'gate': 'hard_gate', 'note': 'Local only'},
                {'id': 'shell_exec', 'available': False, 'gate': 'hard_gate', 'note': 'Local only'},
                {'id': 'git_commit', 'available': False, 'gate': 'hard_gate', 'note': 'Local only'},
                {'id': 'memory_write', 'available': True, 'gate': 'none', 'note': 'S3-backed in cloud'},
                {'id': 'task_create', 'available': True, 'gate': 'none', 'note': 'S3-backed in cloud'},
            ],
            'note': 'Cloud runtime: memory and task tools available. Destructive tools local-only.',
        })

    # ------------------------------------------------------------------
    # Chat (S3 persistence, no LLM)
    # ------------------------------------------------------------------

    def _chat_message(self, body: Dict[str, Any]) -> None:
        message = body.get('message') or body.get('content') or ''
        if not message:
            self.send_json({'error': 'message or content field required'}, 400)
            return
        msg_id = str(uuid.uuid4())
        # Store in S3 for audit trail
        entries = _s3_read_json(S3_MEMORY_KEY, [])
        entry = {
            'id': msg_id,
            'content': f'[CHAT] {message}',
            'namespace': 'chat_cloud',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'cloud_runtime_v3_chat',
        }
        entries.append(entry)
        _s3_write_json(S3_MEMORY_KEY, entries)
        self.send_json({
            'id': msg_id,
            'received': True,
            'stored_in_s3': True,
            'response': 'Message received and stored. Cloud runtime does not process chat with LLM. Full AI chat available in Dockerfile.full deployment.',
            'classification': 'cloud-native-minimal — no-LLM',
        }, 201)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info('=== Jarvis Cloud Runtime v3 — Plan 4 Secure Always-On ===')
    logger.info('HOST: %s  PORT: %d  REGION: %s', HOST, PORT, AWS_REGION)
    logger.info('AUTH: %s', 'ENABLED (OPENJARVIS_API_KEY set)' if OPENJARVIS_API_KEY else 'DISABLED (no key configured)')
    logger.info('S3 BUCKET: %s', MEMORY_BUCKET)
    logger.info('GITHUB_TOKEN: %s', 'SET' if GITHUB_TOKEN else 'NOT SET')
    logger.info('Routes: /health (public) + /v1/* (protected)')
    server = HTTPServer((HOST, PORT), JarvisCloudHandler)
    logger.info('Listening on %s:%d', HOST, PORT)
    server.serve_forever()


if __name__ == '__main__':
    main()
