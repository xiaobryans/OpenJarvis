/**
 * Plan 4-6 — VANTA Capabilities / Roadmap / Status Panel
 *
 * Route: /capabilities
 * Shows:
 *   - Jarvis identity and live system status
 *   - Capability inventory with honest partial/parked/not-started status
 *   - Plan roadmap (Plan 1–6 accurate state, Plan 3 voice parked honestly)
 *   - Mobile / iOS / PWA productization status
 *
 * All data from real /v1/jarvis/* and /v1/productization/* routes.
 * No fake claims. Plan 3 voice is honestly parked.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Smartphone,
  Globe,
  Apple,
  Layers,
  Map,
  Zap,
  Info,
} from 'lucide-react';
import type {
  CapabilitiesResponse,
  JarvisStatus,
  RoadmapResponse,
  ProductizationStatus,
  SystemStatusResponse,
} from '../lib/jarvis-api';
import {
  fetchCapabilities,
  fetchJarvisStatus,
  fetchRoadmap,
  fetchProductizationStatus,
  fetchSystemStatus,
} from '../lib/jarvis-api';

// ---------------------------------------------------------------------------
// Style tokens
// ---------------------------------------------------------------------------
const C = {
  text: 'var(--color-text)',
  textSec: 'var(--color-text-secondary)',
  textTert: 'var(--color-text-tertiary)',
  border: 'var(--color-border)',
  surface: 'var(--color-bg-secondary)',
  surfaceAlt: 'var(--color-bg-tertiary)',
  accent: 'var(--color-accent)',
  success: 'var(--color-success, #a6e3a1)',
  warning: 'var(--color-warning, #f9e2af)',
  error: 'var(--color-error, #f38ba8)',
};

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function CapBadge({ status }: { status: string }) {
  const cfg: Record<string, { bg: string; color: string; icon: React.ReactNode }> = {
    available: { bg: 'rgba(166,227,161,0.12)', color: C.success, icon: <CheckCircle size={11} /> },
    partial: { bg: 'rgba(249,226,175,0.1)', color: C.warning, icon: <Clock size={11} /> },
    parked: { bg: 'rgba(166,173,200,0.1)', color: C.textSec, icon: <Clock size={11} /> },
    not_started: { bg: 'rgba(166,173,200,0.08)', color: C.textTert, icon: <XCircle size={11} /> },
    implemented: { bg: 'rgba(166,227,161,0.12)', color: C.success, icon: <CheckCircle size={11} /> },
    scaffold_ready: { bg: 'rgba(249,226,175,0.1)', color: C.warning, icon: <Info size={11} /> },
    not_submitted: { bg: 'rgba(166,173,200,0.08)', color: C.textTert, icon: <XCircle size={11} /> },
    PASS: { bg: 'rgba(166,227,161,0.12)', color: C.success, icon: <CheckCircle size={11} /> },
    EXTERNAL_GATE: { bg: 'rgba(249,226,175,0.1)', color: C.warning, icon: <AlertTriangle size={11} /> },
    NOT_STARTED: { bg: 'rgba(166,173,200,0.08)', color: C.textTert, icon: <XCircle size={11} /> },
  };
  const style = cfg[status] ?? { bg: C.surfaceAlt, color: C.textSec, icon: <Info size={11} /> };
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono"
      style={{ background: style.bg, color: style.color }}
    >
      {style.icon}
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({
  title,
  icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className="rounded-lg overflow-hidden mb-4"
      style={{ background: C.surface, border: `1px solid ${C.border}` }}
    >
      <button
        className="flex items-center gap-2 w-full px-4 py-3 text-left cursor-pointer"
        style={{ color: C.text }}
        onClick={() => setOpen(!open)}
      >
        <span style={{ color: C.accent }}>{icon}</span>
        <span className="text-sm font-medium">{title}</span>
        <span className="ml-auto" style={{ color: C.textTert }}>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>
      {open && (
        <div style={{ borderTop: `1px solid ${C.border}` }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Jarvis status header
// ---------------------------------------------------------------------------

function StatusHeader({ status }: { status: JarvisStatus }) {
  return (
    <div className="mb-6">
      <div
        className="rounded-lg px-5 py-4"
        style={{ background: C.surface, border: `1px solid ${C.border}` }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-semibold text-base" style={{ color: C.text }}>
              {status.name}
            </div>
            <div className="text-xs mt-0.5" style={{ color: C.textSec }}>
              {status.identity}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  background: status.fake_claims ? C.error : C.success,
                  boxShadow: status.fake_claims ? `0 0 6px ${C.error}` : `0 0 6px ${C.success}`,
                }}
              />
              <span className="text-xs" style={{ color: C.textSec }}>
                {status.fake_claims ? 'Fake claims detected' : 'No fake claims'}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
          <div style={{ color: C.textSec }}>
            <span style={{ color: C.textTert }}>Capabilities: </span>
            {status.capability_summary.available}/{status.capability_summary.total} available
          </div>
          <div style={{ color: C.textSec }}>
            <span style={{ color: C.textTert }}>Text-first: </span>
            <span style={{ color: status.text_first ? C.success : C.textSec }}>
              {status.text_first ? 'yes' : 'no'}
            </span>
          </div>
          <div style={{ color: C.textSec }}>
            <span style={{ color: C.textTert }}>Voice: </span>
            <span style={{ color: status.voice_parked ? C.warning : C.success }}>
              {status.voice_parked ? 'parked (Plan 3 — not started)' : 'active'}
            </span>
          </div>
          <div style={{ color: C.textSec }}>
            <span style={{ color: C.textTert }}>Mobile parity: </span>
            {status.mobile_parity}
          </div>
          <div style={{ color: C.textSec }}>
            <span style={{ color: C.textTert }}>Approval gates: </span>
            {status.approval_gates}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Capabilities list
// ---------------------------------------------------------------------------

function CapabilityList({ data }: { data: CapabilitiesResponse }) {
  const { summary } = data;

  return (
    <Section title="Capabilities" icon={<Zap size={14} />}>
      <div className="px-4 py-3">
        {/* Summary row */}
        <div className="flex flex-wrap gap-3 mb-4 text-xs">
          {[
            { label: 'Available', value: summary.available, color: C.success },
            { label: 'Partial', value: summary.partial, color: C.warning },
            { label: 'Parked', value: summary.parked, color: C.textSec },
            { label: 'Not started', value: summary.not_started, color: C.textTert },
          ].map((s) => (
            <div
              key={s.label}
              className="px-3 py-1.5 rounded"
              style={{ background: C.surfaceAlt, border: `1px solid ${C.border}` }}
            >
              <span style={{ color: s.color, fontWeight: 600 }}>{s.value}</span>
              <span style={{ color: C.textTert }}> {s.label}</span>
            </div>
          ))}
        </div>

        {/* Capability rows */}
        <div className="space-y-1">
          {data.capabilities.map((cap) => (
            <div
              key={cap.id}
              className="flex items-start gap-3 py-2 rounded px-2"
              style={{ borderBottom: `1px solid ${C.border}` }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm" style={{ color: C.text }}>{cap.name}</span>
                  <CapBadge status={cap.status} />
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                    style={{ background: C.surfaceAlt, color: C.textTert }}
                  >
                    {cap.plan}
                  </span>
                </div>
                {cap.description && (
                  <div className="text-xs mt-0.5" style={{ color: C.textSec }}>{cap.description}</div>
                )}
                {cap.blocker && (
                  <div className="text-xs mt-0.5 flex items-center gap-1" style={{ color: C.warning }}>
                    <AlertTriangle size={10} /> {cap.blocker}
                  </div>
                )}
                {cap.external_gate && (
                  <div className="text-xs mt-0.5 flex items-center gap-1" style={{ color: C.textTert }}>
                    <Info size={10} /> External: {cap.external_gate}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Voice is always parked */}
        <div
          className="mt-4 px-3 py-2 rounded text-xs flex items-start gap-2"
          style={{ background: 'rgba(249,226,175,0.06)', border: `1px solid rgba(249,226,175,0.15)`, color: C.warning }}
        >
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          <span>Voice / wake word / TTS: parked for Plan 3. Not started. No ETA yet.</span>
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Roadmap
// ---------------------------------------------------------------------------

const PLAN_STATUS_COLORS: Record<string, string> = {
  accepted: C.success,
  complete: C.success,
  in_progress: 'var(--color-accent)',
  partial: C.warning,
  parked: C.textSec,
  not_started: C.textTert,
  pending: C.warning,
};

function RoadmapSection({ data }: { data: RoadmapResponse }) {
  return (
    <Section title="Plan Roadmap" icon={<Map size={14} />} defaultOpen={false}>
      <div className="px-4 py-3">
        <div className="text-xs mb-3" style={{ color: C.textTert }}>
          Active sprint: <span style={{ color: C.accent }}>{data.active_sprint}</span>
        </div>
        <div className="space-y-2">
          {data.roadmap.map((entry) => (
            <div
              key={entry.plan}
              className="flex items-center gap-3 py-2 rounded px-2"
              style={{ borderBottom: `1px solid ${C.border}` }}
            >
              <span
                className="text-[10px] font-mono px-2 py-0.5 rounded shrink-0"
                style={{ background: C.surfaceAlt, color: C.textTert }}
              >
                {entry.plan}
              </span>
              <span className="text-sm flex-1" style={{ color: C.text }}>{entry.name}</span>
              <span
                className="text-[10px] font-mono px-2 py-0.5 rounded"
                style={{
                  background: `color-mix(in srgb, ${PLAN_STATUS_COLORS[entry.status] ?? C.textSec} 10%, transparent)`,
                  color: PLAN_STATUS_COLORS[entry.status] ?? C.textSec,
                }}
              >
                {entry.status}
              </span>
            </div>
          ))}
        </div>
        <div className="text-xs mt-3 italic" style={{ color: C.textTert }}>{data.note}</div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Productization / mobile / iOS
// ---------------------------------------------------------------------------

function GateRow({ gate, evidence }: { gate: string; status: string; evidence: string }) {
  return (
    <div className="flex items-center gap-2 py-1.5 text-xs" style={{ borderBottom: `1px solid ${C.border}` }}>
      <span className="flex-1" style={{ color: C.textSec }}>{gate.replace(/_/g, ' ')}</span>
      <span style={{ color: C.textTert, fontStyle: 'italic' }}>{evidence}</span>
    </div>
  );
}

function ProductizationSection({ data }: { data: ProductizationStatus }) {
  const { summary } = data;

  return (
    <Section title="Mobile / iOS / Productization" icon={<Smartphone size={14} />} defaultOpen={false}>
      <div className="px-4 py-3">
        {/* Summary grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <div className="rounded-lg px-3 py-2 text-center" style={{ background: C.surfaceAlt, border: `1px solid ${C.border}` }}>
            <Globe size={16} className="mx-auto mb-1" style={{ color: summary.pwa_ready ? C.success : C.textSec }} />
            <div className="text-xs font-medium" style={{ color: summary.pwa_ready ? C.success : C.textSec }}>
              {summary.pwa_ready ? 'PWA Ready' : 'PWA Not ready'}
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: C.textTert }}>{data.mobile_web_pwa.status}</div>
          </div>
          <div className="rounded-lg px-3 py-2 text-center" style={{ background: C.surfaceAlt, border: `1px solid ${C.border}` }}>
            <Apple size={16} className="mx-auto mb-1" style={{ color: summary.ios_scaffold_ready ? C.warning : C.textSec }} />
            <div className="text-xs font-medium" style={{ color: summary.ios_scaffold_ready ? C.warning : C.textSec }}>
              {summary.ios_scaffold_ready ? 'iOS Scaffold' : 'No iOS Scaffold'}
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: C.textTert }}>{data.native_ios.status}</div>
          </div>
          <div className="rounded-lg px-3 py-2 text-center" style={{ background: C.surfaceAlt, border: `1px solid ${C.border}` }}>
            <Layers size={16} className="mx-auto mb-1" style={{ color: summary.app_store_ready ? C.success : C.textTert }} />
            <div className="text-xs font-medium" style={{ color: C.textTert }}>
              App Store
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: C.textTert }}>{data.app_store.status}</div>
          </div>
        </div>

        {/* Gate table */}
        <div className="mb-3">
          <div className="text-xs mb-2 flex items-center justify-between" style={{ color: C.textTert }}>
            <span>Productization gates ({summary.gates_total} total)</span>
            <span>
              <span style={{ color: C.success }}>{summary.gates_pass} pass</span>
              {' · '}
              <span style={{ color: C.warning }}>{summary.gates_external} external</span>
              {' · '}
              <span style={{ color: C.textTert }}>{summary.gates_not_started} not started</span>
            </span>
          </div>
          {data.gates.map((g) => (
            <div key={g.gate} className="flex items-center gap-2 py-1.5 text-xs" style={{ borderBottom: `1px solid ${C.border}` }}>
              <CapBadge status={g.status} />
              <span className="flex-1" style={{ color: C.textSec }}>{g.gate.replace(/_/g, ' ')}</span>
              <span style={{ color: C.textTert, fontStyle: 'italic' }}>{g.evidence}</span>
            </div>
          ))}
        </div>

        {/* iOS details */}
        {data.native_ios.scaffold_status === 'present' && (
          <div className="text-xs mb-2" style={{ color: C.textTert }}>
            iOS scaffold: <span style={{ color: C.textSec, fontFamily: 'monospace' }}>{data.native_ios.scaffold_path}</span>
          </div>
        )}

        {/* Fake-claim guard */}
        {!summary.fake_claims && (
          <div
            className="text-xs flex items-center gap-1.5 mt-2"
            style={{ color: C.success }}
          >
            <CheckCircle size={11} />
            No fake App Store or distribution claims — all statuses are honest.
          </div>
        )}

        {/* Next steps */}
        {data.next_steps.length > 0 && (
          <div className="mt-3">
            <div className="text-xs mb-1" style={{ color: C.textTert }}>Next steps</div>
            <ul className="list-disc list-inside text-xs space-y-0.5" style={{ color: C.textSec }}>
              {data.next_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// System / connector status
// ---------------------------------------------------------------------------

const STATUS_LABEL_CFG: Record<string, { color: string }> = {
  configured: { color: 'var(--color-success, #a6e3a1)' },
  partial: { color: 'var(--color-warning, #f9e2af)' },
  not_configured: { color: 'var(--color-text-tertiary)' },
  external_gate: { color: 'var(--color-warning, #f9e2af)' },
  not_started: { color: 'var(--color-text-tertiary)' },
  unknown: { color: 'var(--color-text-tertiary)' },
  implemented: { color: 'var(--color-success, #a6e3a1)' },
};

function StatusDot({ status }: { status: string }) {
  const cfg = STATUS_LABEL_CFG[status] ?? { color: C.textSec };
  const isDot = ['configured', 'implemented'].includes(status);
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-mono"
      style={{ color: cfg.color }}
    >
      {isDot && <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: cfg.color }} />}
      {status}
    </span>
  );
}

function SystemStatusSection({ data }: { data: SystemStatusResponse }) {
  const connectorEntries = Object.entries(data.connectors);
  const systemEntries = Object.entries(data.system);
  const { summary } = data;

  return (
    <Section title="System & Connector Status" icon={<Globe size={14} />} defaultOpen={false}>
      <div className="px-4 py-3">
        {/* Safety note */}
        <div
          className="text-[10px] mb-3 px-2 py-1.5 rounded flex items-center gap-1.5"
          style={{ background: 'rgba(137,180,250,0.06)', color: C.textTert, border: `1px solid rgba(137,180,250,0.12)` }}
        >
          <Info size={11} />
          {data.safety}
        </div>

        {/* Summary badges */}
        <div className="flex flex-wrap gap-2 mb-4 text-xs">
          <div className="px-2 py-1 rounded" style={{ background: C.surfaceAlt }}>
            <span style={{ color: C.success }}>{summary.connectors_configured}</span>
            <span style={{ color: C.textTert }}> configured</span>
          </div>
          <div className="px-2 py-1 rounded" style={{ background: C.surfaceAlt }}>
            <span style={{ color: C.warning }}>{summary.connectors_partial}</span>
            <span style={{ color: C.textTert }}> partial</span>
          </div>
          <div className="px-2 py-1 rounded" style={{ background: C.surfaceAlt }}>
            <span style={{ color: C.textTert }}>{summary.connectors_not_configured}</span>
            <span style={{ color: C.textTert }}> not configured</span>
          </div>
        </div>

        {/* Connectors table */}
        <div className="text-xs mb-1 font-medium" style={{ color: C.textTert }}>Connectors</div>
        <div className="mb-4 space-y-0">
          {connectorEntries.map(([name, info]) => (
            <div
              key={name}
              className="flex items-center gap-3 py-1.5 text-xs"
              style={{ borderBottom: `1px solid ${C.border}` }}
            >
              <span className="w-24 shrink-0 font-mono capitalize" style={{ color: C.textSec }}>
                {name.replace(/_/g, ' ')}
              </span>
              <StatusDot status={info.status} />
              <span className="flex-1 truncate italic" style={{ color: C.textTert }}>{info.note}</span>
            </div>
          ))}
        </div>

        {/* System table */}
        <div className="text-xs mb-1 font-medium" style={{ color: C.textTert }}>System</div>
        <div className="space-y-0">
          {systemEntries.map(([name, info]) => (
            <div
              key={name}
              className="flex items-center gap-3 py-1.5 text-xs"
              style={{ borderBottom: `1px solid ${C.border}` }}
            >
              <span className="w-32 shrink-0 font-mono" style={{ color: C.textSec }}>
                {name.replace(/_/g, ' ')}
              </span>
              <StatusDot status={info.status} />
              <span className="flex-1 truncate italic" style={{ color: C.textTert }}>{String(info.note ?? '')}</span>
            </div>
          ))}
        </div>

        {/* Fake-claim guard */}
        {!summary.fake_claims && (
          <div className="mt-3 flex items-center gap-1.5 text-xs" style={{ color: C.success }}>
            <CheckCircle size={11} /> No fake status claims — all reports are presence-only.
          </div>
        )}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type PageData = {
  capabilities: CapabilitiesResponse | null;
  status: JarvisStatus | null;
  roadmap: RoadmapResponse | null;
  productization: ProductizationStatus | null;
  systemStatus: SystemStatusResponse | null;
};

export function JarvisCapabilitiesPage() {
  const [data, setData] = useState<PageData>({
    capabilities: null,
    status: null,
    roadmap: null,
    productization: null,
    systemStatus: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [capabilities, status, roadmap, productization, systemStatus] = await Promise.all([
        fetchCapabilities().catch(() => null),
        fetchJarvisStatus().catch(() => null),
        fetchRoadmap().catch(() => null),
        fetchProductizationStatus().catch(() => null),
        fetchSystemStatus().catch(() => null),
      ]);
      setData({ capabilities, status, roadmap, productization, systemStatus });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold" style={{ color: C.text }}>
              VANTA Capabilities &amp; Status
            </h1>
            <button
              onClick={load}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: C.textSec }}
              title="Refresh"
              onMouseEnter={(e) => (e.currentTarget.style.background = C.surface)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
          <p className="text-sm mt-1" style={{ color: C.textSec }}>
            Honest capability inventory, plan roadmap, and productization status.
            All data from{' '}
            <code style={{ fontFamily: 'monospace', fontSize: 11, color: C.textTert }}>/v1/jarvis/*</code>
            {' and '}
            <code style={{ fontFamily: 'monospace', fontSize: 11, color: C.textTert }}>/v1/productization/*</code>.
          </p>
        </header>

        {error && (
          <div
            className="rounded-lg px-4 py-3 mb-4 flex items-center gap-2 text-sm"
            style={{ background: 'rgba(243,139,168,0.1)', color: C.error, border: `1px solid rgba(243,139,168,0.2)` }}
          >
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {loading && (
          <div className="text-sm text-center py-12" style={{ color: C.textTert }}>
            Loading status…
          </div>
        )}

        {!loading && data.status && <StatusHeader status={data.status} />}
        {!loading && data.capabilities && <CapabilityList data={data.capabilities} />}
        {!loading && data.roadmap && <RoadmapSection data={data.roadmap} />}
        {!loading && data.productization && <ProductizationSection data={data.productization} />}
        {!loading && data.systemStatus && <SystemStatusSection data={data.systemStatus} />}

        {!loading && !data.status && !error && (
          <div
            className="rounded-lg px-4 py-10 text-center"
            style={{ background: C.surface, border: `1px solid ${C.border}` }}
          >
            <div className="text-sm" style={{ color: C.textTert }}>
              No data available — backend server may not be running.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
