/**
 * OrgChainPanel — VANTA Organisation Chain Visualization
 *
 * Consumes GET /v1/plan9/org-hierarchy and renders:
 *   1. Canonical execution chain: Bryan → PA → COS/GM → Managers → Workers → Reviewer → PA → Bryan
 *   2. Approval chain: Worker/Manager → Manager validates → Reviewer checks risk
 *      → COS/GM escalates → VANTA asks Bryan → Bryan approves/denies → COS/GM routes back
 *   3. Node table by layer
 *   4. Loop-state legend (intake → done/blocked/failed/approval-needed)
 *
 * Design invariants (enforced visually):
 *   - Bryan only interacts through VANTA.
 *   - Workers/managers/COS/GM never appear as direct user-facing chat participants.
 *   - Reviewer is independent — self-verify blocked.
 *   - No fake live activity. Real data from backend or honest unavailable state.
 */

import React from 'react';

// ---------------------------------------------------------------------------
// Types (mirrors /v1/plan9/org-hierarchy response)
// ---------------------------------------------------------------------------

export interface OrgNode {
  node_id: string;
  display_name: string;
  layer: string;
  reports_to: string | null;
  ownership: string;
  scope: string;
  acceptance_criteria: string;
  evidence_requirements: string;
  model_tier_ref: string;
  report_format: string;
  children: string[];
}

export interface OrgHierarchyData {
  canonical_chain: string;
  approval_chain: string;
  user_facing_only: string;
  user_interacts_only_through: string;
  pa_layer: Record<string, unknown>;
  brain_layer: Record<string, unknown>;
  nodes: OrgNode[];
  node_count: number;
  reviewer_independent: boolean;
  reviewer_self_verify_blocked: boolean;
}

export interface OrgChainFetchState {
  status: 'loading' | 'ok' | 'error' | 'idle';
  httpStatus?: number;
  detail?: string;
}

// ---------------------------------------------------------------------------
// Layer styling
// ---------------------------------------------------------------------------

const LAYER_META: Record<string, { color: string; icon: string; label: string }> = {
  jarvis_pa:  { color: '#22d3ee', icon: '🔷', label: 'VANTA' },
  cos_gm:     { color: '#a78bfa', icon: '🎛', label: 'COS / GM' },
  manager:    { color: '#34d399', icon: '📋', label: 'Manager' },
  worker:     { color: '#60a5fa', icon: '⚙️', label: 'Worker' },
  reviewer:   { color: '#fb923c', icon: '🔍', label: 'Reviewer' },
  tester:     { color: '#fb923c', icon: '🧪', label: 'Tester' },
  validator:  { color: '#fbbf24', icon: '✅', label: 'Validator' },
};

function layerMeta(layer: string) {
  return LAYER_META[layer] ?? { color: '#9ca3af', icon: '◦', label: layer };
}

// ---------------------------------------------------------------------------
// Tiny helpers
// ---------------------------------------------------------------------------

const S = {
  row: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
    padding: '4px 0',
    borderBottom: '1px solid rgba(34,211,238,0.05)',
  } as React.CSSProperties,
  labelCol: {
    fontSize: 10,
    color: 'rgba(120,160,200,0.5)',
    minWidth: 110,
    flexShrink: 0,
  } as React.CSSProperties,
  valueCol: {
    fontSize: 11,
    color: 'rgba(190,220,255,0.85)',
    flex: 1,
    wordBreak: 'break-word',
  } as React.CSSProperties,
  sectionHead: {
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: '0.08em',
    color: 'rgba(34,211,238,0.4)',
    textTransform: 'uppercase' as const,
    marginTop: 12,
    marginBottom: 6,
  },
  chip: (color: string): React.CSSProperties => ({
    display: 'inline-block',
    fontSize: 9,
    padding: '1px 6px',
    borderRadius: 4,
    background: `${color}22`,
    color: color,
    border: `1px solid ${color}44`,
    marginRight: 4,
    flexShrink: 0,
  }),
} as const;

function SmallRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={S.row}>
      <span style={S.labelCol}>{label}</span>
      <span style={S.valueCol}>{value}</span>
    </div>
  );
}

function Sec({ children }: { children: React.ReactNode }) {
  return <div style={S.sectionHead}>{children}</div>;
}

// ---------------------------------------------------------------------------
// Chain arrow row
// ---------------------------------------------------------------------------

function ChainRow({ steps }: { steps: Array<{ label: string; layer: string; note?: string }> }) {
  return (
    <div style={{ overflowX: 'auto', paddingBottom: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap', rowGap: 6 }}>
        {steps.map((step, i) => {
          const meta = layerMeta(step.layer);
          const isLast = i === steps.length - 1;
          return (
            <React.Fragment key={i}>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  padding: '4px 6px',
                  borderRadius: 6,
                  background: `${meta.color}14`,
                  border: `1px solid ${meta.color}33`,
                  minWidth: 64,
                  maxWidth: 90,
                }}
              >
                <span style={{ fontSize: 12 }}>{meta.icon}</span>
                <span style={{ fontSize: 9, color: meta.color, fontWeight: 600, textAlign: 'center', lineHeight: 1.3 }}>
                  {step.label}
                </span>
                {step.note && (
                  <span style={{ fontSize: 8, color: 'rgba(160,180,210,0.45)', textAlign: 'center', lineHeight: 1.2 }}>
                    {step.note}
                  </span>
                )}
              </div>
              {!isLast && (
                <span style={{ fontSize: 10, color: 'rgba(100,140,180,0.4)', padding: '0 2px', flexShrink: 0 }}>→</span>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loop-state legend
// ---------------------------------------------------------------------------

const LOOP_STATES: Array<{ state: string; color: string; desc: string }> = [
  { state: 'intake',           color: '#60a5fa', desc: 'Bryan request received by VANTA' },
  { state: 'decomposition',    color: '#a78bfa', desc: 'COS/GM plans activation: managers, workers' },
  { state: 'assignment',       color: '#34d399', desc: 'Domain managers assigned per task type' },
  { state: 'worker_execution', color: '#60a5fa', desc: 'Workers execute (dry-run safe by default)' },
  { state: 'manager_review',   color: '#34d399', desc: 'Domain manager reviews worker outputs' },
  { state: 'verifier_check',   color: '#fb923c', desc: 'Independent reviewer/tester gate (when required)' },
  { state: 'cos_gm_integrate', color: '#a78bfa', desc: 'COS/GM integrates all results' },
  { state: 'pa_summary',       color: '#22d3ee', desc: 'VANTA summarises and reports to Bryan' },
  { state: 'done',             color: '#3ddc97', desc: 'Complete — no further action needed' },
  { state: 'blocked',          color: '#f59e0b', desc: 'Stopped — blocker reported, Bryan informed' },
  { state: 'failed',           color: '#ef4444', desc: 'Failed — fix list surfaced via VANTA' },
  { state: 'approval_needed',  color: '#fbbf24', desc: 'Bryan must approve/deny through VANTA' },
];

function LoopStateLegend() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {LOOP_STATES.map(ls => (
        <div key={ls.state} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={S.chip(ls.color)}>{ls.state}</span>
          <span style={{ fontSize: 10, color: 'rgba(140,180,210,0.6)', flex: 1 }}>{ls.desc}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Node table by layer
// ---------------------------------------------------------------------------

const LAYER_ORDER = ['jarvis_pa', 'cos_gm', 'manager', 'worker', 'reviewer', 'tester', 'validator'];

function NodesByLayer({ nodes }: { nodes: OrgNode[] }) {
  const byLayer = LAYER_ORDER.reduce<Record<string, OrgNode[]>>((acc, l) => {
    acc[l] = nodes.filter(n => n.layer === l);
    return acc;
  }, {});

  return (
    <>
      {LAYER_ORDER.map(layer => {
        const group = byLayer[layer];
        if (!group || group.length === 0) return null;
        const meta = layerMeta(layer);
        return (
          <div key={layer}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
              color: meta.color,
              textTransform: 'uppercase',
              marginTop: 10, marginBottom: 4,
            }}>
              <span>{meta.icon}</span>
              <span>{meta.label} ({group.length})</span>
              {layer === 'reviewer' && (
                <span style={S.chip('#fb923c')}>independent · self-verify blocked</span>
              )}
            </div>
            {group.map(n => (
              <div key={n.node_id} style={{
                padding: '4px 8px', marginBottom: 3,
                background: `${meta.color}08`,
                border: `1px solid ${meta.color}20`,
                borderRadius: 6,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: n.ownership ? 2 : 0 }}>
                  <span style={{ fontSize: 11, color: meta.color, fontWeight: 600 }}>{n.display_name}</span>
                  {n.reports_to && (
                    <span style={{ fontSize: 9, color: 'rgba(120,160,200,0.4)' }}>
                      → reports to: {n.reports_to}
                    </span>
                  )}
                </div>
                {n.ownership && (
                  <div style={{ fontSize: 9, color: 'rgba(140,170,200,0.55)', lineHeight: 1.4 }}>
                    {n.ownership}
                  </div>
                )}
                {n.children.length > 0 && (
                  <div style={{ fontSize: 9, color: 'rgba(100,140,180,0.4)', marginTop: 2 }}>
                    children: {n.children.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface OrgChainPanelProps {
  data: OrgHierarchyData | null;
  fetchState: OrgChainFetchState;
  apiTarget: string;
}

export function OrgChainPanel({ data, fetchState, apiTarget }: OrgChainPanelProps) {
  if (fetchState.status === 'loading') {
    return (
      <div style={{ fontSize: 11, color: 'rgba(140,180,210,0.5)', padding: '12px 0' }}>
        Loading org hierarchy from /v1/plan9/org-hierarchy…
      </div>
    );
  }

  if (fetchState.status === 'error' || !data) {
    return (
      <div>
        <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 6 }}>
          ⚠ /v1/plan9/org-hierarchy unavailable
        </div>
        <div style={{ fontSize: 10, color: 'rgba(140,180,210,0.5)' }}>
          Target: {apiTarget || 'localhost:8000'}
          {fetchState.httpStatus != null && ` · HTTP ${fetchState.httpStatus}`}
          {fetchState.detail && ` · ${fetchState.detail}`}
        </div>
        <div style={{ marginTop: 12, fontSize: 10, color: 'rgba(120,160,200,0.5)', lineHeight: 1.7 }}>
          <div>Canonical chain (static fallback):</div>
          <div style={{ fontFamily: 'monospace', color: 'rgba(160,200,240,0.5)', fontSize: 9 }}>
            Bryan → VANTA → COS/GM → Domain Managers → Worker Teams
          </div>
          <div style={{ fontFamily: 'monospace', color: 'rgba(160,200,240,0.5)', fontSize: 9 }}>
            → Reviewer/Tester/Verifier (independent) → COS/GM → VANTA → Bryan
          </div>
        </div>
      </div>
    );
  }

  const canonicalSteps = [
    { label: 'Bryan', layer: 'jarvis_pa', note: 'owner' },
    { label: 'VANTA', layer: 'jarvis_pa', note: 'only user-facing' },
    { label: 'COS / GM', layer: 'cos_gm', note: 'coordinator' },
    { label: 'Domain Managers', layer: 'manager', note: 'domain owners' },
    { label: 'Worker Teams', layer: 'worker', note: 'execution cells' },
    { label: 'Reviewer', layer: 'reviewer', note: 'independent gate' },
    { label: 'COS / GM', layer: 'cos_gm', note: 'integrate' },
    { label: 'VANTA', layer: 'jarvis_pa', note: 'summary/approval' },
    { label: 'Bryan', layer: 'jarvis_pa', note: 'response' },
  ];

  const approvalSteps = [
    { label: 'Worker / Manager', layer: 'worker', note: 'requests action' },
    { label: 'Domain Manager', layer: 'manager', note: 'validates need' },
    { label: 'Reviewer', layer: 'reviewer', note: 'checks risk' },
    { label: 'COS / GM', layer: 'cos_gm', note: 'escalates' },
    { label: 'VANTA', layer: 'jarvis_pa', note: 'asks Bryan' },
    { label: 'Bryan', layer: 'jarvis_pa', note: 'approves/denies' },
    { label: 'COS / GM', layer: 'cos_gm', note: 'routes back down' },
  ];

  return (
    <div>
      {/* Design invariant banner */}
      <div style={{
        padding: '6px 10px', marginBottom: 12,
        background: 'rgba(34,211,238,0.07)',
        border: '1px solid rgba(34,211,238,0.18)',
        borderRadius: 8,
        fontSize: 10, color: 'rgba(140,210,240,0.75)', lineHeight: 1.6,
      }}>
        <span style={{ color: '#22d3ee', fontWeight: 600 }}>Design invariant: </span>
        Bryan only interacts through <span style={{ color: '#22d3ee' }}>VANTA</span>.
        Workers, managers, reviewer, and COS/GM are not direct Bryan chat participants.
        <span style={{ marginLeft: 8, color: data.reviewer_self_verify_blocked ? '#3ddc97' : '#ef4444' }}>
          {data.reviewer_self_verify_blocked ? '✓' : '✗'} reviewer self-verify blocked
        </span>
      </div>

      <Sec>Canonical Execution Chain</Sec>
      <ChainRow steps={canonicalSteps} />

      <Sec>Approval Chain</Sec>
      <ChainRow steps={approvalSteps} />

      <Sec>Key Properties</Sec>
      <SmallRow label="User-facing only" value={
        <span style={{ color: '#22d3ee', fontWeight: 600 }}>{data.user_facing_only}</span>
      } />
      <SmallRow label="Bryan interacts via" value={data.user_interacts_only_through} />
      <SmallRow label="Reviewer independent" value={
        data.reviewer_independent
          ? <span style={{ color: '#3ddc97' }}>✓ independent — not a manager child</span>
          : <span style={{ color: '#ef4444' }}>✗ not set</span>
      } />
      <SmallRow label="Self-verify blocked" value={
        data.reviewer_self_verify_blocked
          ? <span style={{ color: '#3ddc97' }}>✓ permanently blocked</span>
          : <span style={{ color: '#ef4444' }}>✗ not set</span>
      } />
      <SmallRow label="Node count" value={data.node_count} />

      <Sec>Organisation Nodes</Sec>
      <NodesByLayer nodes={data.nodes} />

      <Sec>Execution Loop States</Sec>
      <LoopStateLegend />

      <Sec>Endpoint</Sec>
      <SmallRow
        label="Source"
        value={<code style={{ fontSize: 9, color: 'rgba(140,200,240,0.6)' }}>GET /v1/plan9/org-hierarchy</code>}
      />
      <SmallRow label="Target" value={apiTarget || 'localhost:8000'} />
    </div>
  );
}

export default OrgChainPanel;
