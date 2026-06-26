/**
 * MobilePage — Plan 4 mobile-safe Jarvis dashboard.
 *
 * Single-column, touch-friendly view with configurable backend targeting:
 *   - Local mode:  targets same origin (MacBook Jarvis server)
 *   - Remote mode: targets AWS ECS Fargate full Jarvis FastAPI (port 8000)
 *
 * Auth: Bearer token stored in localStorage (OPENJARVIS_API_KEY).
 *       Required for all /v1/* routes on both local and remote backends.
 *
 * Real remote flows (Plan 4 proof):
 *   GET  /health                       — backend reachability (public)
 *   GET  /v1/system/health             — memory_os sub-key (auth)
 *   GET  /v1/memory/status             — semantic search, cloud sync, distillation (auth)
 *   GET  /v1/mobile/continuity/status  — cross-device backend state (auth)
 *   GET  /v1/approvals/pending         — pending approval queue (auth, works locally + remotely)
 *   POST /v1/memory                    — write memory entry to cloud (auth)
 *   POST /v1/chat/completions          — send chat to real LLM (auth, remote)
 *   POST /v1/tasks                     — create task in cloud (auth, remote via cloud runtime)
 */

import { useEffect, useRef, useState } from 'react';
import { MobileAuthorityCockpit } from '../components/Authority/MobileAuthorityCockpit';

// ---------------------------------------------------------------------------
// Backend + Auth management
// ---------------------------------------------------------------------------

const LS_BACKEND_KEY = 'jarvis_mobile_backend_url';
const LS_AUTH_KEY = 'jarvis_mobile_api_key';
// Full Jarvis FastAPI — HTTPS via API Gateway (Plan 4 TLS closure)
// https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com → proxies to ECS Fargate :8000
// TLS cert: Amazon RSA 2048 M04, valid until Aug 2026
const AWS_BACKEND = 'https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com';

function getStoredBackend(): string {
  try { return localStorage.getItem(LS_BACKEND_KEY) ?? ''; } catch { return ''; }
}
function storeBackend(url: string): void {
  try {
    if (url) localStorage.setItem(LS_BACKEND_KEY, url);
    else localStorage.removeItem(LS_BACKEND_KEY);
  } catch { /* ignore */ }
}
function normalizeApiKey(raw: string): string {
  if (!raw) return '';
  let k = raw.trim();
  if ((k.startsWith('"') && k.endsWith('"')) || (k.startsWith("'") && k.endsWith("'"))) {
    k = k.slice(1, -1).trim();
  }
  while (/^bearer\s+/i.test(k)) {
    k = k.replace(/^bearer\s+/i, '').trim();
  }
  return k;
}

function getStoredApiKey(): string {
  try {
    const raw = localStorage.getItem(LS_AUTH_KEY) ?? '';
    const norm = normalizeApiKey(raw);
    if (raw && norm && norm !== raw) {
      localStorage.setItem(LS_AUTH_KEY, norm);
    }
    return norm;
  } catch { return ''; }
}
function storeApiKey(key: string): void {
  try {
    const norm = normalizeApiKey(key);
    if (norm) localStorage.setItem(LS_AUTH_KEY, norm);
    else localStorage.removeItem(LS_AUTH_KEY);
  } catch { /* ignore */ }
}

async function backendFetch(backendUrl: string, path: string, apiKey: string, opts?: RequestInit): Promise<Response> {
  const base = backendUrl.replace(/\/$/, '');
  const url = base ? `${base}${path}` : path;
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = normalizeApiKey(apiKey);
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (opts?.body) headers['Content-Type'] = 'application/json';
  return fetch(url, { ...opts, headers: { ...headers, ...(opts?.headers as Record<string, string> | undefined) } });
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthStatus {
  reachable: boolean;
  status?: string;
  version?: string;
  uptime_seconds?: number;
  memory_os?: {
    sprint?: string;
    total_entries?: number;
    vector_search?: string;
    cloud_sync_available?: boolean;
    cloud_sync_backend?: string;
    ai_distillation_available?: boolean;
  };
  runtime?: {
    deployment?: string;
    macbook_off_capable?: boolean;
  };
}

interface MemoryStatus {
  memory_os?: { sprint?: string; total_entries?: number; total_distilled?: number };
  semantic_search?: { vector_search?: string; active_ranker?: string };
  cloud_sync?: { available?: boolean; backend?: string; last_error?: string | null };
  ai_distillation?: { ai_available?: boolean; ai_model?: string };
}

interface ContinuityBackend {
  name?: string;
  backend_name?: string;
  availability: string;
  macbook_off_capable: boolean;
  notes?: string;
}

interface ContinuityStatus {
  backends?: ContinuityBackend[];
  active_backend?: string;
  cross_device_ready?: boolean;
  active_task_description?: string;
  active_task_status?: string;
  runtime_macbook_off_capable?: boolean;
  runtime_deployment?: string;
  runtime_always_on_status?: string;
  state_sync_macbook_off_capable?: boolean;
  mobile_client_available?: boolean;
}

interface PendingApproval {
  id: string;
  action_type: string;
  description?: string;
  tier?: number;
  created_at: string;
}

type AuthVerdict = 'NO_AUTH_KEY' | 'KEY_SET_BUT_AUTH_FAILED' | 'AUTHENTICATED' | 'NOT_TESTED';

interface EndpointFailure {
  path: string;
  status: number;
}

interface PanelLoads {
  registry: boolean;
  approvals: boolean;
  audit: boolean;
  workflow: boolean;
  routing: boolean;
  memory: boolean;
}

interface Plan9Registry {
  managers?: number;
  workers?: number;
  roles?: unknown[];
  summary?: { managers?: number; workers?: number };
}

interface ChatResult {
  success: boolean;
  response?: string;
  error?: string;
}

interface TaskResult {
  success: boolean;
  id?: string;
  error?: string;
}

interface Plan2SubsectionStatus {
  subsection: string;
  name: string;
  desktop_status: string;
  mobile_status: string;
  macbook_off_status: string;
  auth_status: string;
  blockers?: string[];
  notes?: string[];
}

interface Plan2ParityData {
  plan?: string;
  sprint?: string;
  version?: string;
  acceptance_target?: string;
  sprint_verdict?: string;
  summary?: {
    total_subsections: number;
    mobile_ready: number;
    macbook_off_ready: number;
    mobile_cloud_required: number;
    macbook_off_pending: number;
    parked: number;
  };
  global?: {
    api_key_configured: boolean;
    aws_configured: boolean;
    memory_bucket_configured: boolean;
    telegram_present: boolean;
    slack_present: boolean;
    local_db_accessible: boolean;
    macbook_off_global_blocker?: string;
  };
  subsections?: Plan2SubsectionStatus[];
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

const STATUS_COLOR: Record<string, string> = {
  ok: 'var(--color-success, #22c55e)',
  error: 'var(--color-error, #ef4444)',
  warn: 'var(--color-warn, #f59e0b)',
  info: 'var(--color-accent, #4fd1ff)',
};

function Dot({ color }: { color: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
      }}
    />
  );
}

function Card({
  title,
  children,
  borderColor,
  glow,
}: {
  title: string;
  children: React.ReactNode;
  borderColor?: string;
  glow?: boolean;
}) {
  return (
    <section
      style={{
        background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 90%, transparent)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: `1px solid ${borderColor ?? 'color-mix(in srgb, var(--color-border, #333) 70%, transparent)'}`,
        borderRadius: '14px',
        padding: '14px 16px',
        marginBottom: '10px',
        boxShadow: glow
          ? `0 0 24px -6px color-mix(in srgb, var(--color-accent, #22d3ee) 20%, transparent), 0 4px 16px -4px rgba(0,0,0,0.4)`
          : '0 2px 12px -4px rgba(0,0,0,0.35)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {glow && (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            background: 'linear-gradient(135deg, color-mix(in srgb, var(--color-accent, #22d3ee) 4%, transparent), transparent 60%)',
          }}
        />
      )}
      <h2
        style={{
          fontSize: '10px',
          fontWeight: 700,
          letterSpacing: '0.10em',
          textTransform: 'uppercase',
          color: 'var(--color-text-muted, #888)',
          marginBottom: '10px',
          fontFamily: 'var(--font-hud, monospace)',
          position: 'relative',
        }}
      >
        {title}
      </h2>
      <div style={{ position: 'relative' }}>{children}</div>
    </section>
  );
}

function Row({ label, value, dot }: { label: string; value: string; dot?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '8px',
        padding: '4px 0',
        fontSize: '13px',
        borderBottom: '1px solid color-mix(in srgb, var(--color-border, #333) 30%, transparent)',
      }}
    >
      <span style={{ color: 'var(--color-text-muted, #aaa)' }}>{label}</span>
      <span
        style={{
          color: 'var(--color-text, #eee)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '12px',
          fontFamily: 'monospace',
          textAlign: 'right',
          maxWidth: '60%',
          wordBreak: 'break-all',
        }}
      >
        {dot && <Dot color={dot} />}
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MobilePage() {
  const [backendUrl, setBackendUrl] = useState<string>(getStoredBackend);
  const [apiKey, setApiKey] = useState<string>(getStoredApiKey);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [memory, setMemory] = useState<MemoryStatus | null>(null);
  const [continuity, setContinuity] = useState<ContinuityStatus | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [authVerdict, setAuthVerdict] = useState<AuthVerdict>(() =>
    getStoredApiKey() ? 'NOT_TESTED' : 'NO_AUTH_KEY',
  );
  const [endpointFailures, setEndpointFailures] = useState<EndpointFailure[]>([]);
  const [testKeyResult, setTestKeyResult] = useState<string | null>(null);
  const [panelLoads, setPanelLoads] = useState<PanelLoads>({
    registry: false,
    approvals: false,
    audit: false,
    workflow: false,
    routing: false,
    memory: false,
  });
  const [registry, setRegistry] = useState<Plan9Registry | null>(null);
  const [auditData, setAuditData] = useState<unknown>(null);
  const [workflowData, setWorkflowData] = useState<unknown>(null);
  const [routingData, setRoutingData] = useState<unknown>(null);
  const [connectorsData, setConnectorsData] = useState<unknown>(null);
  const [plan2Parity, setPlan2Parity] = useState<Plan2ParityData | null>(null);
  const [scrollProof, setScrollProof] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [taskInput, setTaskInput] = useState('');
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [memoryWriteResult, setMemoryWriteResult] = useState<string | null>(null);
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [keyDraft, setKeyDraft] = useState('');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const isRemote = backendUrl.trim() !== '';
  const targetLabel = isRemote
    ? `AWS Full VANTA (HTTPS — ${backendUrl.replace(/^https?:\/\//, '').split('/')[0]})`
    : 'Local (MacBook)';

  const fetchAll = async (url?: string, key?: string) => {
    const base = url ?? backendUrl;
    const token = key ?? apiKey;
    setRefreshing(true);
    const failures: EndpointFailure[] = [];
    const loads: PanelLoads = {
      registry: false,
      approvals: false,
      audit: false,
      workflow: false,
      routing: false,
      memory: false,
    };

    // Public health first (no auth needed)
    try {
      const res = await backendFetch(base, '/health', '');
      if (res.ok) {
        const data = await res.json();
        setHealth((prev) => ({ ...prev, reachable: true, ...data }));
      } else {
        setHealth({ reachable: false });
      }
    } catch {
      setHealth({ reachable: false });
    }

    // Plan 2 parity status — public endpoint, no auth required
    try {
      const res = await backendFetch(base, '/v1/mobile-parity/status', '');
      if (res.ok) {
        const data = await res.json();
        setPlan2Parity(data as Plan2ParityData);
      }
    } catch { /* non-fatal */ }

    const authedGet = async (path: string, onOk: (data: unknown) => void) => {
      if (!token) return;
      try {
        const res = await backendFetch(base, path, token);
        if (res.status === 401 || res.status === 403) {
          failures.push({ path, status: res.status });
          return;
        }
        if (res.ok) {
          const data = await res.json();
          onOk(data);
        }
      } catch { /* non-fatal */ }
    };

    await authedGet('/v1/plan9/registry', (data) => {
      loads.registry = true;
      setRegistry(data as Plan9Registry);
    });
    await authedGet('/v1/memory/status', (data) => {
      loads.memory = true;
      setMemory(data as MemoryStatus);
    });
    await authedGet('/v1/mobile/continuity/status', (data) => {
      setContinuity(data as ContinuityStatus);
    });
    await authedGet('/v1/authority/approvals/pending', (data) => {
      loads.approvals = true;
      const d = data as { actions?: PendingApproval[]; pending?: PendingApproval[] };
      setApprovals(d.actions ?? d.pending ?? []);
    });
    await authedGet('/v1/authority/audit', (data) => {
      loads.audit = true;
      setAuditData(data);
    });
    await authedGet('/v1/coding/workflow/status', (data) => {
      loads.workflow = true;
      setWorkflowData(data);
    });
    await authedGet('/v1/model-routing/status', (data) => {
      loads.routing = true;
      setRoutingData(data);
    });
    await authedGet('/v1/connectors', (data) => {
      setConnectorsData(data);
    });

    setPanelLoads(loads);
    setEndpointFailures(failures);

    if (!token) {
      setAuthVerdict('NO_AUTH_KEY');
    } else if (loads.registry) {
      setAuthVerdict('AUTHENTICATED');
    } else if (failures.some((f) => f.path === '/v1/plan9/registry')) {
      setAuthVerdict('KEY_SET_BUT_AUTH_FAILED');
    } else if (failures.length > 0) {
      setAuthVerdict('KEY_SET_BUT_AUTH_FAILED');
    }

    setLastRefresh(new Date());
    setLoading(false);
    setRefreshing(false);
  };

  const testApiKey = async () => {
    if (!apiKey) {
      setTestKeyResult('No key stored — enter and Save first');
      setAuthVerdict('NO_AUTH_KEY');
      return;
    }
    const headerMode = 'Authorization: Bearer <hidden>';
    setTestKeyResult(`Testing GET /v1/plan9/registry…\nHeader: ${headerMode}`);
    try {
      const res = await backendFetch(backendUrl, '/v1/plan9/registry', apiKey);
      if (res.status === 200) {
        setTestKeyResult(`Test OK: GET /v1/plan9/registry → HTTP 200\nHeader: ${headerMode}`);
        setAuthVerdict('AUTHENTICATED');
        await fetchAll(undefined, apiKey);
      } else {
        setTestKeyResult(
          `Test FAILED: GET /v1/plan9/registry → HTTP ${res.status}\nHeader: ${headerMode}\nTip: raw cloud OPENJARVIS_API_KEY only (no Bearer prefix). Clear and re-enter if unsure.`,
        );
        setAuthVerdict('KEY_SET_BUT_AUTH_FAILED');
        setEndpointFailures([{ path: '/v1/plan9/registry', status: res.status }]);
      }
    } catch (e) {
      setTestKeyResult(`Test error: ${String(e).slice(0, 80)}\nHeader: ${headerMode}`);
      setAuthVerdict('KEY_SET_BUT_AUTH_FAILED');
    }
  };

  useEffect(() => {
    document.documentElement.classList.add('mobile-proof-scroll');
    return () => document.documentElement.classList.remove('mobile-proof-scroll');
  }, []);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry?.isIntersecting) setScrollProof(true); },
      { threshold: 0.25 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loading]);

  useEffect(() => {
    fetchAll();
    intervalRef.current = setInterval(fetchAll, 30000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendUrl, apiKey]);

  const switchBackend = (url: string) => {
    storeBackend(url);
    setBackendUrl(url);
    setLoading(true);
    setHealth(null); setMemory(null); setContinuity(null);
    setChatResult(null); setTaskResult(null); setMemoryWriteResult(null);
    setPlan2Parity(null);
  };

  const saveApiKey = () => {
    const k = keyDraft.trim();
    storeApiKey(k);
    setApiKey(k);
    setShowKeyInput(false);
    setKeyDraft('');
    setAuthVerdict(k ? 'NOT_TESTED' : 'NO_AUTH_KEY');
    setTestKeyResult(k ? 'Key saved (normalized) — tap Test API Key' : null);
    fetchAll(undefined, k);
  };

  const verdictColor =
    authVerdict === 'AUTHENTICATED' ? '#22c55e'
    : authVerdict === 'NOT_TESTED' ? '#f59e0b'
    : '#ef4444';

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    setChatLoading(true);
    setChatResult(null);
    try {
      const res = await backendFetch(backendUrl, '/v1/chat/completions', apiKey, {
        method: 'POST',
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [{ role: 'user', content: chatInput }],
          max_tokens: 150,
        }),
      });
      if (res.ok) {
        const d = await res.json();
        const content = d.choices?.[0]?.message?.content ?? JSON.stringify(d);
        setChatResult({ success: true, response: content });
      } else {
        const err = await res.json().catch(() => ({}));
        setChatResult({ success: false, error: `HTTP ${res.status}: ${JSON.stringify(err).slice(0, 100)}` });
      }
    } catch (e) {
      setChatResult({ success: false, error: String(e) });
    }
    setChatLoading(false);
  };

  const handleTask = async () => {
    if (!taskInput.trim()) return;
    setTaskLoading(true);
    setTaskResult(null);
    try {
      // Full Jarvis: POST /v1/company-org/task; Cloud runtime: POST /v1/tasks
      const route = isRemote && !backendUrl.includes(':8000') ? '/v1/tasks' : '/v1/company-org/task';
      const body = route === '/v1/tasks'
        ? { description: taskInput }
        : { task: taskInput };
      const res = await backendFetch(backendUrl, route, apiKey, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const d = await res.json();
        const id = d.task_id ?? d.id ?? '?';
        setTaskResult({ success: true, id });
      } else {
        const err = await res.json().catch(() => ({}));
        setTaskResult({ success: false, error: `HTTP ${res.status}: ${JSON.stringify(err).slice(0, 80)}` });
      }
    } catch (e) {
      setTaskResult({ success: false, error: String(e) });
    }
    setTaskLoading(false);
  };

  const handleMemoryWrite = async () => {
    try {
      const content = `Mobile proof: memory write at ${new Date().toISOString()} from ${isRemote ? 'AWS' : 'local'}`;
      const res = await backendFetch(backendUrl, '/v1/memory', apiKey, {
        method: 'POST',
        body: JSON.stringify({ content, namespace: 'mobile_proof' }),
      });
      if (res.ok) {
        const d = await res.json();
        setMemoryWriteResult(`Stored entry_id: ${d.entry?.entry_id ?? d.id ?? '?'}`);
      } else {
        setMemoryWriteResult(`Failed: HTTP ${res.status}`);
      }
    } catch (e) {
      setMemoryWriteResult(`Error: ${String(e).slice(0, 60)}`);
    }
  };

  const isReachable = health?.reachable ?? false;
  const memOS = health?.memory_os;

  return (
    <div
      className="mobile-proof-root"
      style={{
        maxWidth: '480px',
        margin: '0 auto',
        padding: '16px 12px calc(env(safe-area-inset-bottom, 0px) + 5rem)',
        minHeight: '100dvh',
        overflowY: 'auto',
        WebkitOverflowScrolling: 'touch',
        color: 'var(--color-text, #eee)',
        fontFamily: 'var(--font-sans, system-ui, sans-serif)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '14px',
          padding: '12px 14px',
          background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 85%, transparent)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid color-mix(in srgb, var(--color-accent, #22d3ee) 18%, var(--color-border, #333))',
          borderRadius: '14px',
          boxShadow: '0 0 24px -8px color-mix(in srgb, var(--color-accent, #22d3ee) 18%, transparent)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span
            style={{
              width: 9, height: 9, borderRadius: '50%', flexShrink: 0,
              background: isReachable ? STATUS_COLOR.ok : STATUS_COLOR.error,
              boxShadow: isReachable ? `0 0 8px ${STATUS_COLOR.ok}` : 'none',
            }}
          />
          <span style={{ fontSize: '16px', fontWeight: 700, letterSpacing: '-0.01em', fontFamily: 'var(--font-display, system-ui)' }}>
            JARVIS
          </span>
          <span
            style={{
              fontSize: '10px',
              background: 'color-mix(in srgb, var(--color-accent, #22d3ee) 12%, transparent)',
              color: 'var(--color-accent, #22d3ee)',
              border: '1px solid color-mix(in srgb, var(--color-accent, #22d3ee) 28%, transparent)',
              borderRadius: '4px',
              padding: '1px 6px',
              fontFamily: 'monospace',
              letterSpacing: '0.06em',
            }}
          >
            MOBILE
          </span>
        </div>
        <button
          onClick={() => fetchAll()}
          disabled={refreshing}
          style={{
            fontSize: '12px',
            padding: '6px 12px',
            background: 'color-mix(in srgb, var(--color-accent, #22d3ee) 10%, transparent)',
            color: 'var(--color-accent, #22d3ee)',
            border: '1px solid color-mix(in srgb, var(--color-accent, #22d3ee) 22%, transparent)',
            borderRadius: '8px',
            cursor: refreshing ? 'not-allowed' : 'pointer',
            opacity: refreshing ? 0.6 : 1,
            fontFamily: 'monospace',
          }}
        >
          {refreshing ? '…' : '↻'}
        </button>
      </div>

      {/* Backend selector */}
      <div
        style={{
          display: 'flex',
          gap: '6px',
          marginBottom: '16px',
          padding: '10px',
          background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 80%, transparent)',
          border: '1px solid color-mix(in srgb, var(--color-border, #333) 50%, transparent)',
          borderRadius: '10px',
        }}
      >
        <button
          onClick={() => switchBackend('')}
          style={{
            flex: 1,
            padding: '7px 0',
            fontSize: '12px',
            fontWeight: !isRemote ? 600 : 400,
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            background: !isRemote
              ? 'color-mix(in srgb, var(--color-accent, #4fd1ff) 18%, transparent)'
              : 'transparent',
            color: !isRemote ? 'var(--color-accent, #4fd1ff)' : 'var(--color-text-muted, #888)',
            transition: 'all 0.15s',
          }}
        >
          Local
        </button>
        <button
          onClick={() => switchBackend(AWS_BACKEND)}
          style={{
            flex: 1,
            padding: '7px 0',
            fontSize: '12px',
            fontWeight: isRemote ? 600 : 400,
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            background: isRemote
              ? 'color-mix(in srgb, #f59e0b 18%, transparent)'
              : 'transparent',
            color: isRemote ? '#f59e0b' : 'var(--color-text-muted, #888)',
            transition: 'all 0.15s',
          }}
        >
          AWS Always-On
        </button>
      </div>

      {/* Backend target badge + auth status */}
      <div
        style={{
          fontSize: '11px',
          color: 'var(--color-text-muted, #888)',
          marginBottom: '10px',
          fontFamily: 'monospace',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          flexWrap: 'wrap',
        }}
      >
        <span>Target:</span>
        <span style={{ color: isRemote ? '#f59e0b' : 'var(--color-text, #eee)' }}>
          {isRemote ? backendUrl : 'same origin'}
        </span>
        {isRemote && (
          <span
            style={{
              fontSize: '10px',
              background: 'color-mix(in srgb, #f59e0b 12%, transparent)',
              color: '#f59e0b',
              border: '1px solid color-mix(in srgb, #f59e0b 25%, transparent)',
              borderRadius: '3px',
              padding: '1px 5px',
            }}
          >
            HTTPS ✓
          </span>
        )}
        <span
          style={{
            fontSize: '10px',
            background: `color-mix(in srgb, ${verdictColor} 12%, transparent)`,
            color: verdictColor,
            border: `1px solid color-mix(in srgb, ${verdictColor} 25%, transparent)`,
            borderRadius: '3px',
            padding: '1px 5px',
            cursor: 'pointer',
            fontFamily: 'monospace',
          }}
          onClick={() => setShowKeyInput((x) => !x)}
        >
          {authVerdict}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--color-text-muted, #888)' }}>
          key: {apiKey ? 'set (hidden)' : 'none'}
        </span>
      </div>
      {endpointFailures.length > 0 && (
        <div style={{ fontSize: '10px', color: '#ef4444', marginBottom: '8px', fontFamily: 'monospace' }}>
          {endpointFailures.map((f) => (
            <div key={f.path}>{f.path} → HTTP {f.status}</div>
          ))}
        </div>
      )}

      {/* API key input */}
      {showKeyInput && (
        <div
          style={{
            marginBottom: '12px',
            padding: '10px',
            background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 90%, transparent)',
            border: '1px solid color-mix(in srgb, var(--color-border, #333) 60%, transparent)',
            borderRadius: '8px',
          }}
        >
          <div style={{ fontSize: '11px', color: 'var(--color-text-muted, #888)', marginBottom: '6px' }}>
            Raw OPENJARVIS_API_KEY (cloud Secrets Manager). No Bearer prefix. Stored in localStorage only.
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <input
              type="password"
              placeholder="Raw API key only (no Bearer prefix)"
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') saveApiKey(); }}
              style={{
                flex: 1, padding: '7px', fontSize: '12px', borderRadius: '5px',
                background: 'var(--color-surface, #1a1a1c)',
                color: 'var(--color-text, #eee)',
                border: '1px solid var(--color-border, #333)',
              }}
            />
            <button
              onClick={saveApiKey}
              style={{
                padding: '7px 12px', fontSize: '12px', borderRadius: '5px',
                background: 'color-mix(in srgb, #22c55e 15%, transparent)',
                color: '#22c55e', border: '1px solid color-mix(in srgb, #22c55e 30%, transparent)',
                cursor: 'pointer',
              }}
            >
              Save
            </button>
            <button
              onClick={testApiKey}
              style={{
                padding: '7px 12px', fontSize: '12px', borderRadius: '5px',
                background: 'color-mix(in srgb, var(--color-accent, #4fd1ff) 12%, transparent)',
                color: 'var(--color-accent, #4fd1ff)',
                border: '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 28%, transparent)',
                cursor: 'pointer',
              }}
            >
              Test API Key
            </button>
            {apiKey && (
              <button
                onClick={() => { storeApiKey(''); setApiKey(''); setShowKeyInput(false); }}
                style={{
                  padding: '7px 10px', fontSize: '12px', borderRadius: '5px',
                  background: 'color-mix(in srgb, #ef4444 12%, transparent)',
                  color: '#ef4444', border: '1px solid color-mix(in srgb, #ef4444 25%, transparent)',
                  cursor: 'pointer',
                }}
              >
                Clear
              </button>
            )}
          </div>
          {testKeyResult && (
            <div style={{ fontSize: '11px', color: 'var(--color-text-muted, #888)', marginTop: '6px', fontFamily: 'monospace' }}>
              {testKeyResult}
            </div>
          )}
        </div>
      )}

      {!loading && (
        <Card title="Mobile Proof Summary">
          <Row label="Physical iPhone" value="manual proof required" />
          <Row label="Cloud reachable" value={isReachable ? 'yes' : 'no'} dot={isReachable ? STATUS_COLOR.ok : STATUS_COLOR.error} />
          <Row label="Authenticated" value={authVerdict === 'AUTHENTICATED' ? 'yes' : 'no'} dot={authVerdict === 'AUTHENTICATED' ? STATUS_COLOR.ok : STATUS_COLOR.warn} />
          <Row label="Registry loaded" value={panelLoads.registry ? 'yes' : 'no'} />
          <Row label="Approvals loaded" value={panelLoads.approvals ? 'yes' : 'no'} />
          <Row label="Audit/workflow loaded" value={panelLoads.audit && panelLoads.workflow ? 'yes' : 'no'} />
          <Row label="Routing loaded" value={panelLoads.routing ? 'yes' : 'no'} />
          <Row label="Memory loaded" value={panelLoads.memory ? 'yes' : 'no'} />
          <Row label="Scroll proof (reach bottom)" value={scrollProof ? 'yes' : 'no'} />
        </Card>
      )}

      {loading ? (
        <div
          style={{
            textAlign: 'center',
            padding: '40px 0',
            color: 'var(--color-text-muted, #888)',
            fontSize: '14px',
          }}
        >
          Connecting to {targetLabel}…
        </div>
      ) : (
        <>
          {/* Backend Health */}
          <Card
            title="Backend"
            glow={isReachable}
            borderColor={
              isReachable
                ? 'color-mix(in srgb, var(--color-success, #22c55e) 28%, transparent)'
                : 'color-mix(in srgb, var(--color-error, #ef4444) 28%, transparent)'
            }
          >
            <Row
              label="Status"
              value={isReachable ? 'Reachable' : 'Unreachable'}
              dot={isReachable ? STATUS_COLOR.ok : STATUS_COLOR.error}
            />
            <Row label="Target" value={targetLabel} />
            {health?.version && <Row label="Version" value={health.version} />}
            {health?.uptime_seconds !== undefined && (
              <Row label="Uptime" value={`${Math.round(health.uptime_seconds)}s`} />
            )}
            {health?.runtime && (
              <Row
                label="MacBook-off"
                value={health.runtime.macbook_off_capable ? 'Yes (AWS)' : 'No (local only)'}
                dot={health.runtime.macbook_off_capable ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
            )}
            {memOS && (
              <>
                <Row label="Memory entries" value={String(memOS.total_entries ?? '—')} />
                <Row
                  label="Cloud sync"
                  value={memOS.cloud_sync_available ? (memOS.cloud_sync_backend ?? 'S3') : 'Local only'}
                  dot={memOS.cloud_sync_available ? STATUS_COLOR.ok : STATUS_COLOR.warn}
                />
                <Row
                  label="Vector search"
                  value={memOS.vector_search?.replace('ACTIVE_', '').replace('BLOCKED_', '⚠ ') ?? '—'}
                />
              </>
            )}
          </Card>

          {/* Plan 9 Registry */}
          <Card title="Plan 9 Registry (roles / managers / workers)">
            {!apiKey && (
              <div style={{ fontSize: '12px', color: '#f59e0b' }}>Set and test API key to load</div>
            )}
            {registry ? (
              <>
                <Row label="Managers" value={String(registry.managers ?? registry.summary?.managers ?? '—')} />
                <Row label="Workers" value={String(registry.workers ?? registry.summary?.workers ?? '—')} />
                <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--color-text-muted, #888)', marginTop: '6px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {JSON.stringify(registry.roles ?? registry, null, 2).slice(0, 600)}
                </div>
              </>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                {apiKey ? 'Not loaded or auth failed' : 'No API key'}
              </div>
            )}
          </Card>

          {/* Memory OS */}
          {memory && (
            <Card title="Memory OS">
              <Row
                label="Total entries"
                value={String(memory.memory_os?.total_entries ?? '—')}
              />
              <Row label="Distilled" value={String(memory.memory_os?.total_distilled ?? '—')} />
              <Row label="Ranker" value={memory.semantic_search?.active_ranker ?? '—'} />
              <Row
                label="Cloud sync"
                value={
                  memory.cloud_sync?.available
                    ? `${memory.cloud_sync.backend ?? 'S3'} ✓`
                    : 'Local only'
                }
                dot={memory.cloud_sync?.available ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
              <Row
                label="AI distillation"
                value={memory.ai_distillation?.ai_available ? 'Available' : 'Unavailable'}
                dot={memory.ai_distillation?.ai_available ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
            </Card>
          )}

          {/* Continuity */}
          {continuity && (
            <Card title="Cross-Device Continuity">
              {continuity.active_task_description ? (
                <>
                  <div
                    style={{
                      fontSize: '13px',
                      color: 'var(--color-text, #eee)',
                      marginBottom: '8px',
                      padding: '8px',
                      background:
                        'color-mix(in srgb, var(--color-accent, #4fd1ff) 5%, transparent)',
                      borderRadius: '6px',
                      border:
                        '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 15%, transparent)',
                    }}
                  >
                    {continuity.active_task_description}
                  </div>
                  <Row label="Task status" value={continuity.active_task_status ?? '—'} />
                </>
              ) : (
                <div
                  style={{
                    fontSize: '13px',
                    color: 'var(--color-text-muted, #888)',
                    padding: '4px 0',
                    marginBottom: '4px',
                  }}
                >
                  No active task
                </div>
              )}
              <Row
                label="Cross-device ready"
                value={continuity.cross_device_ready ? 'Yes (Gist)' : 'No'}
                dot={continuity.cross_device_ready ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
              <Row
                label="Runtime (MacBook-off)"
                value={
                  continuity.runtime_macbook_off_capable
                    ? `Yes — ${continuity.runtime_deployment ?? 'cloud'}`
                    : 'No — localhost only'
                }
                dot={
                  continuity.runtime_macbook_off_capable ? STATUS_COLOR.ok : STATUS_COLOR.warn
                }
              />
              <Row
                label="State sync (MacBook-off)"
                value={continuity.state_sync_macbook_off_capable ? 'Yes (Gist + S3)' : 'Partial'}
                dot={continuity.state_sync_macbook_off_capable ? STATUS_COLOR.ok : STATUS_COLOR.warn}
              />
              {continuity.backends?.map((b) => {
                const name = b.name ?? b.backend_name ?? 'backend';
                const avail = b.availability.replace('BackendAvailability.', '');
                return (
                  <Row
                    key={name}
                    label={name}
                    value={avail}
                    dot={
                      b.availability.includes('available') ? STATUS_COLOR.ok : STATUS_COLOR.warn
                    }
                  />
                );
              })}
              {continuity.runtime_always_on_status && (
                <div
                  style={{
                    fontSize: '11px',
                    color: 'var(--color-text-muted, #888)',
                    marginTop: '8px',
                    padding: '6px 8px',
                    background:
                      'color-mix(in srgb, var(--color-border, #333) 20%, transparent)',
                    borderRadius: '6px',
                    lineHeight: '1.4',
                  }}
                >
                  {continuity.runtime_always_on_status}
                </div>
              )}
            </Card>
          )}

          {/* Audit & Workflow */}
          <Card title="Audit & Workflow Status">
            {!panelLoads.audit && !panelLoads.workflow && (
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                {!apiKey ? 'No API key' : 'Not loaded'}
              </div>
            )}
            {auditData != null && (
              <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--color-text-muted, #888)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: '8px' }}>
                audit: {JSON.stringify(auditData, null, 2).slice(0, 400)}
              </div>
            )}
            {workflowData != null && (
              <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--color-text-muted, #888)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                workflow: {JSON.stringify(workflowData, null, 2).slice(0, 400)}
              </div>
            )}
          </Card>

          {/* Model Routing */}
          <Card title="Model Routing Status">
            {routingData != null ? (
              <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--color-text-muted, #888)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(routingData, null, 2).slice(0, 500)}
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                {!apiKey ? 'No API key' : 'Not loaded'}
              </div>
            )}
          </Card>

          {/* Chat (remote: real LLM) */}
          {isRemote && (
            <Card title="Chat — Real LLM (gpt-4o-mini via AWS)">
              <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                <input
                  placeholder="Message VANTA..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleChat(); }}
                  style={{
                    flex: 1, padding: '8px', fontSize: '13px', borderRadius: '6px',
                    background: 'var(--color-surface, #1a1a1c)',
                    color: 'var(--color-text, #eee)',
                    border: '1px solid var(--color-border, #333)',
                  }}
                />
                <button
                  onClick={handleChat}
                  disabled={chatLoading || !chatInput.trim()}
                  style={{
                    padding: '8px 14px', fontSize: '13px', borderRadius: '6px',
                    background: 'color-mix(in srgb, var(--color-accent, #4fd1ff) 15%, transparent)',
                    color: 'var(--color-accent, #4fd1ff)',
                    border: '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 30%, transparent)',
                    cursor: chatLoading ? 'not-allowed' : 'pointer',
                    opacity: chatLoading ? 0.6 : 1,
                  }}
                >
                  {chatLoading ? '…' : 'Send'}
                </button>
              </div>
              {chatResult && (
                <div
                  style={{
                    padding: '8px', borderRadius: '6px', fontSize: '13px',
                    background: chatResult.success
                      ? 'color-mix(in srgb, #22c55e 6%, transparent)'
                      : 'color-mix(in srgb, #ef4444 6%, transparent)',
                    border: `1px solid color-mix(in srgb, ${chatResult.success ? '#22c55e' : '#ef4444'} 20%, transparent)`,
                    color: 'var(--color-text, #eee)',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {chatResult.response ?? chatResult.error}
                </div>
              )}
            </Card>
          )}

          {/* Task creation */}
          <Card title={isRemote ? 'Create Task (AWS Cloud)' : 'Create Task (Local)'}>
            <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
              <input
                placeholder="Describe task..."
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleTask(); }}
                style={{
                  flex: 1, padding: '8px', fontSize: '13px', borderRadius: '6px',
                  background: 'var(--color-surface, #1a1a1c)',
                  color: 'var(--color-text, #eee)',
                  border: '1px solid var(--color-border, #333)',
                }}
              />
              <button
                onClick={handleTask}
                disabled={taskLoading || !taskInput.trim()}
                style={{
                  padding: '8px 14px', fontSize: '13px', borderRadius: '6px',
                  background: 'color-mix(in srgb, #22c55e 12%, transparent)',
                  color: '#22c55e',
                  border: '1px solid color-mix(in srgb, #22c55e 25%, transparent)',
                  cursor: taskLoading ? 'not-allowed' : 'pointer',
                  opacity: taskLoading ? 0.6 : 1,
                }}
              >
                {taskLoading ? '…' : 'Create'}
              </button>
            </div>
            {taskResult && (
              <div
                style={{
                  padding: '6px 8px', borderRadius: '5px', fontSize: '12px',
                  background: taskResult.success
                    ? 'color-mix(in srgb, #22c55e 6%, transparent)'
                    : 'color-mix(in srgb, #ef4444 6%, transparent)',
                  color: taskResult.success ? '#22c55e' : '#ef4444',
                  fontFamily: 'monospace',
                }}
              >
                {taskResult.success ? `Created task: ${taskResult.id}` : taskResult.error}
              </div>
            )}
          </Card>

          {/* Memory write proof */}
          <Card title="Memory Write (Plan 4 proof)">
            <div style={{ display: 'flex', gap: '6px', marginBottom: '6px' }}>
              <button
                onClick={handleMemoryWrite}
                style={{
                  flex: 1, padding: '8px', fontSize: '13px', borderRadius: '6px',
                  background: 'color-mix(in srgb, var(--color-accent, #4fd1ff) 10%, transparent)',
                  color: 'var(--color-accent, #4fd1ff)',
                  border: '1px solid color-mix(in srgb, var(--color-accent, #4fd1ff) 20%, transparent)',
                  cursor: 'pointer',
                }}
              >
                Write timestamp entry to {isRemote ? 'AWS S3 memory' : 'local memory'}
              </button>
            </div>
            {memoryWriteResult && (
              <div
                style={{
                  padding: '6px 8px', borderRadius: '5px', fontSize: '11px',
                  background: 'color-mix(in srgb, var(--color-border, #333) 25%, transparent)',
                  color: 'var(--color-text-muted, #888)',
                  fontFamily: 'monospace',
                }}
              >
                {memoryWriteResult}
              </div>
            )}
          </Card>

          {/* Approvals (auth-gated, works locally + remotely) */}
          <Card
            title={`Pending Approvals${approvals.length > 0 ? ` (${approvals.length})` : ''}`}
            borderColor={
              approvals.length > 0
                ? 'color-mix(in srgb, var(--color-warn, #f59e0b) 30%, transparent)'
                : undefined
            }
          >
            {!apiKey && (
              <div style={{ fontSize: '12px', color: '#f59e0b', marginBottom: '6px' }}>
                ⚠ Set API key to load approvals
              </div>
            )}
            {approvals.length === 0 ? (
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                No pending approvals
              </div>
            ) : (
              approvals.map((a) => (
                <div
                  key={a.id}
                  style={{
                    padding: '8px', marginBottom: '6px',
                    background: 'color-mix(in srgb, var(--color-warn, #f59e0b) 6%, transparent)',
                    border: '1px solid color-mix(in srgb, var(--color-warn, #f59e0b) 20%, transparent)',
                    borderRadius: '8px', fontSize: '13px',
                  }}
                >
                  <div style={{ fontWeight: 500, marginBottom: '2px' }}>{a.action_type}</div>
                  <div style={{ color: 'var(--color-text-muted, #aaa)', fontSize: '12px' }}>
                    {a.description}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted, #888)', marginTop: '4px' }}>
                    Tier: {a.tier} · {new Date(a.created_at).toLocaleTimeString()}
                  </div>
                </div>
              ))
            )}
          </Card>

          {/* Connector Status (live) */}
          <Card title="Connector Status">
            {connectorsData != null ? (
              <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--color-text-muted, #888)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(connectorsData, null, 2).slice(0, 800)}
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                {!apiKey ? 'No API key' : 'Not available or not loaded'}
              </div>
            )}
          </Card>

          {/* Plan 8B — Mobile Authority Cockpit */}
          <MobileAuthorityCockpit backendUrl={backendUrl} apiKey={apiKey} />

          {/* Plan 2 — MacBook-Off Parity Status */}
          <Card
            title="Plan 2 — MacBook-Off Parity Status"
            borderColor="color-mix(in srgb, #a78bfa 25%, var(--color-border, #333))"
          >
            {plan2Parity ? (
              <>
                <div
                  style={{
                    fontSize: '10px', fontFamily: 'monospace', color: '#a78bfa',
                    marginBottom: '8px', letterSpacing: '0.06em',
                  }}
                >
                  {plan2Parity.sprint ?? 'Plan 2A Foundation'} · v{plan2Parity.version ?? '?'}
                </div>
                {plan2Parity.summary && (
                  <div
                    style={{
                      display: 'grid', gridTemplateColumns: '1fr 1fr',
                      gap: '6px', marginBottom: '10px',
                    }}
                  >
                    {[
                      { label: 'Subsections', val: String(plan2Parity.summary.total_subsections) },
                      { label: 'Mobile ready', val: String(plan2Parity.summary.mobile_ready) },
                      { label: 'MacBook-off ready', val: String(plan2Parity.summary.macbook_off_ready) },
                      { label: 'Cloud required', val: String(plan2Parity.summary.mobile_cloud_required) },
                      { label: 'MacBook-off pending', val: String(plan2Parity.summary.macbook_off_pending) },
                    ].map(({ label, val }) => (
                      <div
                        key={label}
                        style={{
                          padding: '5px 7px', borderRadius: '6px', fontSize: '11px',
                          background: 'color-mix(in srgb, #a78bfa 5%, transparent)',
                          border: '1px solid color-mix(in srgb, #a78bfa 15%, transparent)',
                        }}
                      >
                        <div style={{ color: 'var(--color-text-muted, #888)', fontSize: '10px' }}>{label}</div>
                        <div style={{ color: '#a78bfa', fontWeight: 600, fontFamily: 'monospace' }}>{val}</div>
                      </div>
                    ))}
                  </div>
                )}
                {plan2Parity.subsections?.map((s) => {
                  const mobileColor =
                    s.mobile_status === 'READY' ? '#22c55e'
                    : s.mobile_status === 'CLOUD_REQUIRED' ? '#f59e0b'
                    : s.mobile_status === 'MACBOOK_OFF_PENDING' ? '#fb923c'
                    : s.mobile_status === 'NOT_CONFIGURED' ? '#64748b'
                    : s.mobile_status === 'PARKED' ? '#475569'
                    : '#ef4444';
                  const offColor =
                    s.macbook_off_status === 'READY' ? '#22c55e'
                    : s.macbook_off_status === 'CLOUD_REQUIRED' ? '#f59e0b'
                    : s.macbook_off_status === 'MACBOOK_OFF_PENDING' ? '#fb923c'
                    : '#64748b';
                  return (
                    <div
                      key={s.subsection}
                      style={{
                        marginBottom: '6px', padding: '7px 9px', borderRadius: '8px',
                        background: 'color-mix(in srgb, var(--color-surface, #1a1a1c) 60%, transparent)',
                        border: '1px solid color-mix(in srgb, var(--color-border, #333) 40%, transparent)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text, #eee)' }}>
                          {s.subsection} · {s.name}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '10px', fontFamily: 'monospace', color: mobileColor, background: 'color-mix(in srgb, currentColor 8%, transparent)', padding: '1px 5px', borderRadius: '3px', border: '1px solid color-mix(in srgb, currentColor 20%, transparent)' }}>
                          📱 {s.mobile_status}
                        </span>
                        <span style={{ fontSize: '10px', fontFamily: 'monospace', color: offColor, background: 'color-mix(in srgb, currentColor 8%, transparent)', padding: '1px 5px', borderRadius: '3px', border: '1px solid color-mix(in srgb, currentColor 20%, transparent)' }}>
                          ☁ {s.macbook_off_status}
                        </span>
                      </div>
                    </div>
                  );
                })}
                {plan2Parity.global?.macbook_off_global_blocker && (
                  <div
                    style={{
                      marginTop: '8px', padding: '7px 9px', borderRadius: '7px', fontSize: '11px',
                      background: 'color-mix(in srgb, #f59e0b 5%, transparent)',
                      border: '1px solid color-mix(in srgb, #f59e0b 20%, transparent)',
                      color: '#f59e0b', lineHeight: '1.5',
                    }}
                  >
                    ⚠ {plan2Parity.global.macbook_off_global_blocker}
                  </div>
                )}
                <div
                  style={{
                    marginTop: '8px', fontSize: '10px', fontFamily: 'monospace',
                    color: 'var(--color-text-muted, #666)', letterSpacing: '0.05em',
                  }}
                >
                  {plan2Parity.sprint_verdict}
                </div>
              </>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--color-text-muted, #888)' }}>
                Loading Plan 2 parity status…
              </div>
            )}
          </Card>

          <section
            ref={sentinelRef}
            style={{
              textAlign: 'center',
              padding: '24px 16px',
              marginTop: '12px',
              marginBottom: '24px',
              border: '2px dashed color-mix(in srgb, var(--color-border, #333) 70%, transparent)',
              borderRadius: '10px',
              color: 'var(--color-text-muted, #888)',
              fontSize: '13px',
              fontWeight: 700,
              letterSpacing: '0.08em',
              fontFamily: 'monospace',
            }}
          >
            END OF MOBILE PROOF
          </section>

          {/* Footer */}
          {lastRefresh && (
            <div
              style={{
                textAlign: 'center',
                fontSize: '11px',
                color: 'var(--color-text-muted, #666)',
                paddingTop: '8px',
                fontFamily: 'monospace',
              }}
            >
              {lastRefresh.toLocaleTimeString()} · auto 30s
            </div>
          )}
        </>
      )}
    </div>
  );
}
