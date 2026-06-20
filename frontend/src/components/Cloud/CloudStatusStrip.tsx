/**
 * CloudStatusChip — compact cloud status indicator for the TopBar.
 *
 * Shows a minimal status dot + label. Expands to a small popover with
 * detail when clicked. Does NOT hijack the main canvas.
 *
 * Error details are accessible via the diagnostics drawer (⌘I), not
 * by dominating the work surface.
 */

import { useState } from 'react';
import { Cloud, X } from 'lucide-react';
import { useCloudStatus } from './useCloudStatus';

export function CloudStatusChip() {
  const { nodeStatus, bundle, error } = useCloudStatus();
  const [expanded, setExpanded] = useState(false);

  const isOnline = nodeStatus === 'online';
  const isChecking = nodeStatus === 'checking';

  const dotColor = isOnline
    ? 'var(--p2-mint, #22c55e)'
    : isChecking
    ? 'var(--color-text-tertiary)'
    : 'var(--p2-amber, #f59e0b)';

  const label = isOnline ? 'Cloud' : isChecking ? '…' : 'Cloud';

  return (
    <div className="relative">
      {/* Compact chip */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 rounded-full cursor-pointer transition-all"
        style={{
          padding: '3px 8px 3px 6px',
          background: 'var(--color-bg-secondary)',
          border: `1px solid ${isOnline ? 'var(--color-border)' : 'color-mix(in srgb, ' + dotColor + ' 35%, var(--color-border))'}`,
          color: 'var(--color-text-tertiary)',
        }}
        title={isOnline ? 'Cloud Active' : isChecking ? 'Checking cloud…' : 'Cloud unreachable'}
      >
        {/* Status dot */}
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${isOnline ? 'p2-status-pulse' : ''}`}
          style={{ background: dotColor }}
        />
        <Cloud size={11} style={{ color: dotColor }} />
        <span className="text-[10px] font-medium hidden sm:inline" style={{ color: dotColor }}>{label}</span>
      </button>

      {/* Detail popover — shown when clicked */}
      {expanded && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setExpanded(false)}
          />
          <div
            className="absolute right-0 top-full mt-1.5 z-50 rounded-xl overflow-hidden"
            style={{
              width: '260px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              boxShadow: 'var(--p2-elev-3)',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-3 py-2"
              style={{ borderBottom: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${isOnline ? 'p2-status-pulse' : ''}`}
                  style={{ background: dotColor }}
                />
                <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                  {isOnline ? 'Cloud Active' : isChecking ? 'Checking…' : 'Cloud Unreachable'}
                </span>
              </div>
              <button
                onClick={() => setExpanded(false)}
                className="p-0.5 rounded cursor-pointer"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                <X size={12} />
              </button>
            </div>

            {/* Body */}
            <div className="px-3 py-2.5 space-y-1.5">
              {isOnline && bundle && (
                <>
                  <Row label="Runtime" value={bundle.runtime ?? 'Active'} />
                  <Row label="Storage" value={bundle.storage ?? 'Cloud Primary'} />
                  <Row label="Action Gate" value={bundle.action_gate ?? 'Token Required'} />
                  <Row label="Tailscale" value={bundle.tailscale ?? 'Connected'} />
                </>
              )}
              {nodeStatus === 'offline' && (
                <p className="text-xs" style={{ color: 'var(--p2-amber)' }}>
                  {error || 'Cloud unreachable — ensure Tailnet is active.'}
                </p>
              )}
              {isChecking && (
                <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  Polling cloud node…
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
      <span className="text-[10px] font-medium truncate max-w-[160px] text-right" style={{ color: 'var(--color-text-secondary)' }}>{value}</span>
    </div>
  );
}

/**
 * CloudStatusStrip — legacy name kept so existing imports don't break.
 * Now renders nothing — status moved to TopBar chip.
 */
export function CloudStatusStrip() {
  return null;
}
