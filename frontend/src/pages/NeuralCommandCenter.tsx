/**
 * NeuralCommandCenter.tsx
 * One-page Jarvis Neural Command Center layout components.
 * Imported by JarvisCockpitPage.tsx.
 */

import React from 'react';

// ─── Status Types ────────────────────────────────────────────────────────────

export type StatusDot = 'ok' | 'warn' | 'error' | 'unknown';
export type TurnPhase = 'idle' | 'thinking' | 'streaming' | 'waiting_for_silence' | 'error';

// ─── Data Interfaces ─────────────────────────────────────────────────────────

export interface ConnectorInfo {
  name: string;
  connected: boolean;
  endpoint?: string;
}

export interface MemoryStatus {
  total_entries?: number;
  cloud_sync?: { synced?: boolean; last_sync?: string };
}

export interface RoutingStatus {
  pa_front_door_model: string;
  provider_count: number;
}

export interface RegistryStatus {
  total_managers: number;
  total_workers: number;
  total_roles: number;
}

export interface FinalSmokeStatus {
  smoke_status: string;
  claimed_passed: boolean;
  installed_app_smoke: string;
  daily_driver: string;
  manual_proof_required: boolean;
}

export interface SigningStatus {
  signing_claimed: boolean;
  notarization_claimed: boolean;
  actual_signing_run: boolean;
  actual_notarization_run: boolean;
  public_release_ready: boolean;
}

export interface CompletionScore {
  core_os_completion: {
    completion_score_pct: number;
    plans_accepted: string[];
  };
  capability_coverage: {
    daily_driver_certified: boolean;
    installed_app_smoke_visual: boolean;
    macos_signed_notarized: boolean;
    ios_init_completed: boolean;
  };
}

export interface NccCoreProps {
  phase: TurnPhase;
  apiOk: boolean | null;
  pendingApprovals: number;
  approvalCount: number;
  connectors: ConnectorInfo[];
  memStatus: MemoryStatus | null;
  auditEntries: { action_type?: string; execution_status?: string }[];
  workflowStatus: { status?: string; workflow_id?: string } | null;
  finalSmoke: FinalSmokeStatus | null;
  signingStatus: SigningStatus | null;
  completionScore: CompletionScore | null;
  routingStatus: RoutingStatus | null;
  registry: RegistryStatus | null;
  plan9Gaps: number | null;
  connectorLive: number;
  connectorTotal: number;
  onExpandPanel: (id: string) => void;
}

// Re-export alias so callers can import NccProps for convenience
export type NccProps = NccCoreProps;

// ─── Helper: status dot element ──────────────────────────────────────────────

const DOT_COLORS: Record<StatusDot, string> = {
  ok: '#3ddc97',
  warn: '#f59e0b',
  error: '#ef4444',
  unknown: '#6b7280',
};

const DOT_SHADOWS: Record<StatusDot, string> = {
  ok: '0 0 4px #3ddc9780',
  warn: '0 0 4px #f59e0b80',
  error: '0 0 4px #ef444480',
  unknown: '0 0 2px #6b728040',
};

export function dot(s: StatusDot): React.ReactElement {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: DOT_COLORS[s],
        boxShadow: DOT_SHADOWS[s],
        flexShrink: 0,
      }}
    />
  );
}

// ─── CommandPanel ─────────────────────────────────────────────────────────────

interface CommandPanelProps {
  icon: string;
  label: string;
  statusDot: StatusDot;
  line1: string;
  line2?: string;
  onExpand: () => void;
  compact?: boolean;
}

export function CommandPanel({
  icon,
  label,
  statusDot,
  line1,
  line2,
  onExpand,
  compact = false,
}: CommandPanelProps): React.ReactElement {
  const [hovered, setHovered] = React.useState(false);
  const padding = compact ? '6px 9px' : '9px 11px';

  return (
    <div
      role="button"
      tabIndex={0}
      title={`${label} — expand in-page`}
      onClick={onExpand}
      onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) => {
        if (e.key === 'Enter' || e.key === ' ') onExpand();
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        flex: 1,
        textAlign: 'left',
        background: 'rgba(8,14,28,0.82)',
        border: `1px solid ${hovered ? 'rgba(34,211,238,0.22)' : 'rgba(34,211,238,0.09)'}`,
        borderRadius: 10,
        padding,
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        position: 'relative',
        transition: 'border-color 0.15s',
        minWidth: 0,
      }}
    >
      {/* Top row: icon + label + dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ fontSize: 13, lineHeight: 1 }}>{icon}</span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            textTransform: 'uppercase',
            color: 'rgba(160,200,240,0.8)',
            letterSpacing: '0.04em',
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </span>
        {dot(statusDot)}
      </div>

      {/* line1 */}
      <div
        style={{
          fontSize: 10,
          color: 'rgba(120,160,200,0.65)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {line1}
      </div>

      {/* line2 */}
      {line2 && (
        <div
          style={{
            fontSize: 9,
            color: 'rgba(100,140,180,0.45)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {line2}
        </div>
      )}

      {/* expand label */}
      <div
        style={{
          position: 'absolute',
          bottom: 5,
          right: 7,
          fontSize: 8,
          color: 'rgba(34,211,238,0.22)',
          pointerEvents: 'none',
          userSelect: 'none',
        }}
      >
        expand ↗
      </div>
    </div>
  );
}

// ─── StatusMiniCard ──────────────────────────────────────────────────────────

interface StatusMiniCardProps {
  label: string;
  value: string;
  color: string;
  subtext?: string;
}

export function StatusMiniCard({
  label,
  value,
  color,
  subtext,
}: StatusMiniCardProps): React.ReactElement {
  return (
    <div
      style={{
        background: 'rgba(8,14,28,0.70)',
        border: `1px solid ${color}18`,
        borderRadius: 8,
        padding: '6px 8px',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: 7,
          textTransform: 'uppercase',
          color: 'rgba(80,120,160,0.5)',
          letterSpacing: '0.05em',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          color,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {value}
      </div>
      {subtext && (
        <div
          style={{
            fontSize: 8,
            color: 'rgba(80,120,160,0.4)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {subtext}
        </div>
      )}
    </div>
  );
}

// ─── CommandInputStrip ────────────────────────────────────────────────────────

interface CommandInputStripProps {
  input: string;
  sending: boolean;
  apiOk: boolean | null;
  onInputChange: (v: string) => void;
  onSubmit: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  lastReply: string;
}

export function CommandInputStrip({
  input,
  sending,
  apiOk,
  onInputChange,
  onSubmit,
  onKeyDown,
  inputRef,
  lastReply,
}: CommandInputStripProps): React.ReactElement {
  const offline = apiOk === false;

  return (
    <div
      style={{
        background: 'rgba(4,8,20,0.82)',
        border: '1px solid rgba(34,211,238,0.15)',
        borderRadius: 10,
        padding: '7px 9px',
        display: 'flex',
        flexDirection: 'column',
        gap: 5,
      }}
    >
      {/* Last reply preview */}
      {lastReply && !offline && (
        <div
          style={{
            fontSize: 10,
            color: 'rgba(160,200,220,0.75)',
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            lineHeight: 1.4,
          }}
        >
          {lastReply}
        </div>
      )}

      {/* Input row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            fontSize: 10,
            color: 'rgba(34,211,238,0.6)',
            fontWeight: 700,
            flexShrink: 0,
            userSelect: 'none',
          }}
        >
          ↗ Jarvis:
        </span>

        {offline ? (
          <div
            style={{
              flex: 1,
              fontSize: 10,
              color: 'rgba(239,68,68,0.7)',
              fontStyle: 'italic',
            }}
          >
            API offline
          </div>
        ) : (
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              onInputChange(e.target.value)
            }
            onKeyDown={onKeyDown}
            disabled={sending}
            placeholder="Ask Jarvis…"
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'none',
              resize: 'none',
              fontSize: 11,
              color: 'rgba(180,220,255,0.85)',
              lineHeight: 1.4,
              fontFamily: 'inherit',
              padding: 0,
              opacity: sending ? 0.5 : 1,
            }}
          />
        )}

        <button
          onClick={onSubmit}
          disabled={sending || offline}
          style={{
            fontSize: 9,
            background: 'rgba(34,211,238,0.12)',
            border: '1px solid rgba(34,211,238,0.25)',
            borderRadius: 6,
            color: 'rgba(34,211,238,0.8)',
            padding: '3px 8px',
            cursor: sending || offline ? 'not-allowed' : 'pointer',
            flexShrink: 0,
            opacity: sending || offline ? 0.5 : 1,
            transition: 'opacity 0.15s',
          }}
        >
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </div>
  );
}

// ─── Shared extended props for Desktop + Mobile ───────────────────────────────

interface NccLayoutProps extends NccCoreProps {
  onMode: (m: string) => void;
  isNarrow: boolean;
  input: string;
  sending: boolean;
  lastReply: string;
  onInputChange: (v: string) => void;
  onSubmit: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  orbChildren?: React.ReactNode;
}

// ─── DesktopCommandCenter ─────────────────────────────────────────────────────

export function DesktopCommandCenter(props: NccLayoutProps): React.ReactElement {
  const {
    apiOk,
    pendingApprovals,
    approvalCount,
    connectors,
    memStatus,
    auditEntries,
    workflowStatus,
    finalSmoke,
    signingStatus,
    completionScore,
    routingStatus,
    connectorLive,
    connectorTotal,
    onExpandPanel,
    input,
    sending,
    lastReply,
    onInputChange,
    onSubmit,
    onKeyDown,
    inputRef,
    orbChildren,
  } = props;

  // Derive helper values
  const apiStatusDot: StatusDot = apiOk === null ? 'unknown' : apiOk ? 'ok' : 'error';
  const memStatusDot: StatusDot = memStatus ? 'ok' : 'unknown';
  const auditStatusDot: StatusDot = auditEntries.length > 0 ? 'ok' : 'unknown';
  const approvalStatusDot: StatusDot = approvalCount > 0 ? 'warn' : 'ok';

  let connectorStatusDot: StatusDot = 'unknown';
  if (connectorTotal > 0) {
    connectorStatusDot = connectorLive === connectorTotal ? 'ok' : 'warn';
  }

  const workflowStatusDot: StatusDot = workflowStatus ? 'ok' : 'unknown';

  let appleStatusDot: StatusDot = 'unknown';
  if (signingStatus) {
    appleStatusDot = signingStatus.actual_notarization_run ? 'ok' : 'warn';
  }

  // Routing model short label
  const routingModel: string = routingStatus
    ? (routingStatus.pa_front_door_model.split('/').pop() ?? routingStatus.pa_front_door_model).slice(0, 18)
    : '—';

  // Memory lines
  const memLine1: string = memStatus?.total_entries
    ? `${memStatus.total_entries} entries`
    : 'Memory store active';
  const memLine2: string = memStatus?.cloud_sync?.synced ? 'Cloud sync: live' : 'Cloud sync: pending';

  // Audit lines
  const auditLine1: string = auditEntries[0]
    ? `${auditEntries[0].action_type ?? 'action'} · ${auditEntries[0].execution_status ?? 'status'}`
    : 'System quiet';

  // Connector disconnected names
  const disconnectedNames: string = connectors
    .filter((c) => !c.connected)
    .slice(0, 2)
    .map((c) => c.name)
    .join(', ') || 'All connected';

  // Smoke card values
  const smokeValue: string = finalSmoke
    ? finalSmoke.claimed_passed
      ? 'CLAIMED'
      : 'PENDING'
    : '—';
  const smokeColor: string = finalSmoke?.claimed_passed ? '#f59e0b' : '#6b7280';

  const driverCertified: boolean = completionScore?.capability_coverage.daily_driver_certified ?? false;
  const driverValue: string = driverCertified ? 'CERTIFIED' : 'NEEDS PROOF';
  const driverColor: string = driverCertified ? '#3ddc97' : '#6b7280';

  const coreValue: string = completionScore
    ? `${completionScore.core_os_completion.completion_score_pct}%`
    : '—';
  const coreSubtext: string = completionScore
    ? `${completionScore.core_os_completion.plans_accepted.length} plans accepted`
    : 'loading...';

  // Apple/signing lines
  const appleSign = signingStatus;
  const appleLine1: string = appleSign
    ? appleSign.actual_notarization_run
      ? 'Notarized: accepted'
      : 'Notarize: pending'
    : 'Loading…';
  const appleLine2: string = appleSign
    ? appleSign.actual_signing_run
      ? 'Signed: Developer ID'
      : 'Not signed'
    : '';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '210px 1fr 210px',
        gap: 8,
        padding: '8px 10px',
        overflow: 'hidden',
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* ── LEFT COLUMN ── */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          overflowY: 'auto',
        }}
      >
        <CommandPanel
          icon="🎯"
          label="Mission / Goals"
          statusDot={apiStatusDot}
          line1="Jarvis PA — cloud-first · PA front door"
          line2={routingModel}
          onExpand={() => onExpandPanel('mission')}
        />
        <CommandPanel
          icon="🧠"
          label="Memory OS"
          statusDot={memStatusDot}
          line1={memLine1}
          line2={memLine2}
          onExpand={() => onExpandPanel('memory')}
        />
        <CommandPanel
          icon="📋"
          label="Tasks / Follow-Ups"
          statusDot="ok"
          line1="Follow-up center · PA-tracked"
          line2="B1 accepted · delegation active"
          onExpand={() => onExpandPanel('mission')}
        />
        <CommandPanel
          icon="📜"
          label="Audit / Safety"
          statusDot={auditStatusDot}
          line1={auditLine1}
          line2="Hard gates: active · OMNIX: decoupled"
          onExpand={() => onExpandPanel('logs')}
        />
      </div>

      {/* ── CENTER COLUMN ── */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          gap: 8,
        }}
      >
        {/* Orb area */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          {orbChildren}
        </div>

        {/* Input strip */}
        <div style={{ flexShrink: 0 }}>
          <CommandInputStrip
            input={input}
            sending={sending}
            apiOk={apiOk}
            onInputChange={onInputChange}
            onSubmit={onSubmit}
            onKeyDown={onKeyDown}
            inputRef={inputRef}
            lastReply={lastReply}
          />
        </div>

        {/* Bottom status row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3,1fr)',
            gap: 6,
            flexShrink: 0,
          }}
        >
          <StatusMiniCard
            label="Final Smoke"
            value={smokeValue}
            color={smokeColor}
            subtext="needs Bryan visual proof"
          />
          <StatusMiniCard
            label="Daily Driver"
            value={driverValue}
            color={driverColor}
            subtext="usage sessions required"
          />
          <StatusMiniCard
            label="Core OS"
            value={coreValue}
            color="#3ddc97"
            subtext={coreSubtext}
          />
        </div>
      </div>

      {/* ── RIGHT COLUMN ── */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          overflowY: 'auto',
        }}
      >
        <CommandPanel
          icon="✅"
          label="Approvals / Auth"
          statusDot={approvalStatusDot}
          line1={approvalCount > 0 ? `${approvalCount} pending Bryan approval` : 'Queue empty'}
          line2="Hard gates: active · authority enforced"
          onExpand={() => onExpandPanel('authority')}
        />
        <CommandPanel
          icon="🔌"
          label="Connectors"
          statusDot={connectorStatusDot}
          line1={connectorTotal > 0 ? `${connectorLive}/${connectorTotal} connected` : '0 connectors'}
          line2={disconnectedNames}
          onExpand={() => onExpandPanel('connectors')}
        />
        <CommandPanel
          icon="🔧"
          label="Workbench"
          statusDot={workflowStatusDot}
          line1={workflowStatus ? `Last: ${workflowStatus.status ?? 'unknown'}` : 'No workflow run'}
          line2="Local coding · git · testing · lint"
          onExpand={() => onExpandPanel('workbench')}
        />
        <CommandPanel
          icon="📱"
          label="Apple / iOS / Cloud"
          statusDot={appleStatusDot}
          line1={appleLine1}
          line2={appleLine2}
          onExpand={() => onExpandPanel('plan9')}
        />

        {/* Phase badges */}
        <div style={{ display: 'flex', gap: 4, paddingTop: 4, flexWrap: 'wrap' }}>
          <div
            style={{
              fontSize: 8,
              padding: '2px 6px',
              background: '#3ddc9714',
              border: '1px solid #3ddc9730',
              borderRadius: 4,
              color: '#3ddc97',
            }}
          >
            Phase B ACCEPTED_ON_HOLD
          </div>
          <div
            style={{
              fontSize: 8,
              padding: '2px 6px',
              background: '#3ddc9714',
              border: '1px solid #3ddc9730',
              borderRadius: 4,
              color: '#3ddc97',
            }}
          >
            Phase C ACCEPTED
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── MobileCommandCenter ──────────────────────────────────────────────────────

export function MobileCommandCenter(props: NccLayoutProps): React.ReactElement {
  const {
    apiOk,
    approvalCount,
    connectors,
    memStatus,
    auditEntries,
    workflowStatus,
    finalSmoke,
    signingStatus,
    completionScore,
    routingStatus,
    connectorLive,
    connectorTotal,
    onExpandPanel,
    input,
    sending,
    lastReply,
    onInputChange,
    onSubmit,
    onKeyDown,
    inputRef,
    orbChildren,
  } = props;

  // Derive same helper values as desktop
  const apiStatusDot: StatusDot = apiOk === null ? 'unknown' : apiOk ? 'ok' : 'error';
  const memStatusDot: StatusDot = memStatus ? 'ok' : 'unknown';
  const auditStatusDot: StatusDot = auditEntries.length > 0 ? 'ok' : 'unknown';
  const approvalStatusDot: StatusDot = approvalCount > 0 ? 'warn' : 'ok';

  let connectorStatusDot: StatusDot = 'unknown';
  if (connectorTotal > 0) {
    connectorStatusDot = connectorLive === connectorTotal ? 'ok' : 'warn';
  }

  const workflowStatusDot: StatusDot = workflowStatus ? 'ok' : 'unknown';

  let appleStatusDot: StatusDot = 'unknown';
  if (signingStatus) {
    appleStatusDot = signingStatus.actual_notarization_run ? 'ok' : 'warn';
  }

  const routingModel: string = routingStatus
    ? (routingStatus.pa_front_door_model.split('/').pop() ?? routingStatus.pa_front_door_model).slice(0, 18)
    : '—';

  const memLine1: string = memStatus?.total_entries
    ? `${memStatus.total_entries} entries`
    : 'Memory store active';
  const memLine2: string = memStatus?.cloud_sync?.synced ? 'Cloud sync: live' : 'Cloud sync: pending';

  const auditLine1: string = auditEntries[0]
    ? `${auditEntries[0].action_type ?? 'action'} · ${auditEntries[0].execution_status ?? 'status'}`
    : 'System quiet';

  const disconnectedNames: string = connectors
    .filter((c) => !c.connected)
    .slice(0, 2)
    .map((c) => c.name)
    .join(', ') || 'All connected';

  const smokeValue: string = finalSmoke
    ? finalSmoke.claimed_passed
      ? 'CLAIMED'
      : 'PENDING'
    : '—';
  const smokeColor: string = finalSmoke?.claimed_passed ? '#f59e0b' : '#6b7280';

  const driverCertified: boolean = completionScore?.capability_coverage.daily_driver_certified ?? false;
  const driverValue: string = driverCertified ? 'CERTIFIED' : 'NEEDS PROOF';
  const driverColor: string = driverCertified ? '#3ddc97' : '#6b7280';

  const coreValue: string = completionScore
    ? `${completionScore.core_os_completion.completion_score_pct}%`
    : '—';
  const coreSubtext: string = completionScore
    ? `${completionScore.core_os_completion.plans_accepted.length} plans accepted`
    : 'loading...';

  const appleSign = signingStatus;
  const appleLine1: string = appleSign
    ? appleSign.actual_notarization_run
      ? 'Notarized: accepted'
      : 'Notarize: pending'
    : 'Loading…';
  const appleLine2: string = appleSign
    ? appleSign.actual_signing_run
      ? 'Signed: Developer ID'
      : 'Not signed'
    : '';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        padding: '8px 10px',
        gap: 8,
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Compact orb */}
      <div
        style={{
          height: 140,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        {orbChildren}
      </div>

      {/* Input strip */}
      <div style={{ flexShrink: 0 }}>
        <CommandInputStrip
          input={input}
          sending={sending}
          apiOk={apiOk}
          onInputChange={onInputChange}
          onSubmit={onSubmit}
          onKeyDown={onKeyDown}
          inputRef={inputRef}
          lastReply={lastReply}
        />
      </div>

      {/* Panels grid 2-col */}
      <div
        style={{
          overflowY: 'auto',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 5,
        }}
      >
        <CommandPanel
          icon="🎯"
          label="Mission / Goals"
          statusDot={apiStatusDot}
          line1="Jarvis PA — cloud-first"
          line2={routingModel}
          onExpand={() => onExpandPanel('mission')}
          compact
        />
        <CommandPanel
          icon="✅"
          label="Approvals / Auth"
          statusDot={approvalStatusDot}
          line1={approvalCount > 0 ? `${approvalCount} pending` : 'Queue empty'}
          line2="Hard gates: active"
          onExpand={() => onExpandPanel('authority')}
          compact
        />
        <CommandPanel
          icon="🧠"
          label="Memory OS"
          statusDot={memStatusDot}
          line1={memLine1}
          line2={memLine2}
          onExpand={() => onExpandPanel('memory')}
          compact
        />
        <CommandPanel
          icon="🔌"
          label="Connectors"
          statusDot={connectorStatusDot}
          line1={connectorTotal > 0 ? `${connectorLive}/${connectorTotal} live` : '0 connectors'}
          line2={disconnectedNames}
          onExpand={() => onExpandPanel('connectors')}
          compact
        />
        <CommandPanel
          icon="📋"
          label="Tasks / Follow-Ups"
          statusDot="ok"
          line1="Follow-up center · PA"
          line2="B1 accepted"
          onExpand={() => onExpandPanel('mission')}
          compact
        />
        <CommandPanel
          icon="🔧"
          label="Workbench"
          statusDot={workflowStatusDot}
          line1={workflowStatus ? `Last: ${workflowStatus.status ?? 'unknown'}` : 'No workflow'}
          line2="git · testing · lint"
          onExpand={() => onExpandPanel('workbench')}
          compact
        />
        <CommandPanel
          icon="📜"
          label="Audit / Safety"
          statusDot={auditStatusDot}
          line1={auditLine1}
          line2="Hard gates: active"
          onExpand={() => onExpandPanel('logs')}
          compact
        />
        <CommandPanel
          icon="📱"
          label="Apple / iOS"
          statusDot={appleStatusDot}
          line1={appleLine1}
          line2={appleLine2}
          onExpand={() => onExpandPanel('plan9')}
          compact
        />
      </div>

      {/* Bottom status row */}
      <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
        <StatusMiniCard
          label="Final Smoke"
          value={smokeValue}
          color={smokeColor}
          subtext="needs Bryan visual proof"
        />
        <StatusMiniCard
          label="Daily Driver"
          value={driverValue}
          color={driverColor}
          subtext="usage sessions required"
        />
        <StatusMiniCard
          label="Core OS"
          value={coreValue}
          color="#3ddc97"
          subtext={coreSubtext}
        />
      </div>
    </div>
  );
}
