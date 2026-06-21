/**
 * ConnectorStatusBar — compact horizontal HUD strip.
 *
 * Shows live/blocked/parked status for every connector and system gate.
 * Fetches GitHub connector state from /v1/connectors; all other statuses are
 * derived from the known checkpoint state (truthful, not assumed).
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { apiFetch } from '../lib/api';

type ChipStatus = 'live' | 'blocked' | 'parked' | 'pending' | 'checking';

interface ConnectorChip {
  id: string;
  label: string;
  status: ChipStatus;
  tooltip: string;
  route?: string;
}

const STATIC_CHIPS: ConnectorChip[] = [
  {
    id: 'gmail',
    label: 'Gmail',
    status: 'blocked',
    tooltip: 'BLOCKED — OAuth credentials required.',
    route: '/data-sources',
  },
  {
    id: 'gcalendar',
    label: 'Calendar',
    status: 'blocked',
    tooltip: 'BLOCKED — OAuth credentials required.',
    route: '/data-sources',
  },
  {
    id: 'slack',
    label: 'Slack',
    status: 'blocked',
    tooltip: 'BLOCKED — xoxp token required.',
    route: '/data-sources',
  },
  {
    id: 'telegram',
    label: 'Telegram',
    status: 'blocked',
    tooltip: 'BLOCKED — bot token required.',
    route: '/data-sources',
  },
  {
    id: 'voice',
    label: 'Voice',
    status: 'parked',
    tooltip: 'PARKED — US13 Voice is unsafe/parked. Requires dedicated safety sprint.',
  },
  {
    id: 'apple_signing',
    label: 'Apple Signing',
    status: 'pending',
    tooltip: 'PENDING — Apple Developer enrollment in progress. Updater blocked.',
  },
  {
    id: 'plan8',
    label: 'Plan 8',
    status: 'parked',
    tooltip: 'NOT STARTED — Trusted Delegation. Begins after Bryan review.',
  },
];

const STATUS_CHIP_CLASS: Record<ChipStatus, string> = {
  live: 'neon-chip neon-chip-live',
  blocked: 'neon-chip neon-chip-blocked',
  pending: 'neon-chip neon-chip-pending',
  parked: 'neon-chip neon-chip-parked',
  checking: 'neon-chip neon-chip-parked',
};

function StatusDot({ status }: { status: ChipStatus }) {
  if (status === 'live') return <span className="status-dot-live" />;
  if (status === 'blocked') return <span className="status-dot-blocked" />;
  return <span className="status-dot-parked" />;
}

interface ChipProps {
  chip: ConnectorChip;
  onClick?: () => void;
}

function Chip({ chip, onClick }: ChipProps) {
  const cls = STATUS_CHIP_CLASS[chip.status];
  return (
    <span
      className={cls}
      title={chip.tooltip}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      <StatusDot status={chip.status} />
      {chip.label}
      {chip.status === 'live' && (
        <span style={{ fontSize: 9, opacity: 0.75, marginLeft: 1 }}>LIVE</span>
      )}
    </span>
  );
}

export function ConnectorStatusBar() {
  const navigate = useNavigate();
  const [githubStatus, setGithubStatus] = useState<ChipStatus>('checking');
  const [githubTooltip, setGithubTooltip] = useState('GitHub — checking…');

  const checkGitHub = useCallback(async () => {
    // GitHub live status comes from the /v1/tools registry — the gh CLI keyring connector
    // registers github.connector_status with is_available=true when configured.
    // There is no 'github' entry in /v1/connectors (that endpoint covers OAuth connectors).
    try {
      const resp = await apiFetch('/v1/tools');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json() as { tools?: Array<{ tool_id: string; is_available: boolean; blocker?: string }> };
      const ghTool = (data.tools ?? []).find(t => t.tool_id === 'github.connector_status');
      if (ghTool?.is_available) {
        setGithubStatus('live');
        setGithubTooltip('GitHub LIVE — gh CLI keyring authenticated; github.connector_status available.');
      } else if (ghTool) {
        setGithubStatus('blocked');
        setGithubTooltip(`GitHub — tool registered but unavailable: ${ghTool.blocker || 'no blocker detail'}`);
      } else {
        setGithubStatus('blocked');
        setGithubTooltip('GitHub — tool not registered. Backend may be offline.');
      }
    } catch {
      setGithubStatus('blocked');
      setGithubTooltip('GitHub — backend unreachable.');
    }
  }, []);

  useEffect(() => {
    checkGitHub();
    const id = setInterval(checkGitHub, 60_000);
    return () => clearInterval(id);
  }, [checkGitHub]);

  const githubChip: ConnectorChip = {
    id: 'github',
    label: 'GitHub',
    status: githubStatus,
    tooltip: githubTooltip,
    route: '/data-sources',
  };

  return (
    <div
      className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 overflow-x-auto"
      style={{
        background: 'var(--color-bg-secondary)',
        borderBottom: '1px solid var(--color-border-subtle)',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      }}
      aria-label="Connector and system status"
    >
      <span
        className="text-[10px] font-mono shrink-0 mr-1"
        style={{ color: 'var(--color-text-tertiary)', letterSpacing: '0.06em' }}
      >
        CONNECTORS
      </span>

      <Chip chip={githubChip} onClick={() => navigate('/data-sources')} />

      {STATIC_CHIPS.map(chip => (
        <Chip
          key={chip.id}
          chip={chip}
          onClick={chip.route ? () => navigate(chip.route!) : undefined}
        />
      ))}
    </div>
  );
}
