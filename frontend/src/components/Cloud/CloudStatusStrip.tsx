import { Cloud } from 'lucide-react';
import { useCloudStatus } from './useCloudStatus';

export function CloudStatusStrip() {
  const { nodeStatus, bundle, lastChecked } = useCloudStatus();

  const isOnline = nodeStatus === 'online';
  const isChecking = nodeStatus === 'checking';

  const dotColor = isOnline
    ? 'var(--color-success, #22c55e)'
    : isChecking
    ? 'var(--color-text-tertiary, #888)'
    : 'var(--color-error, #ef4444)';

  return (
    <div
      className="mx-4 mb-2 shrink-0 flex items-center gap-3 px-3 py-2 rounded-lg text-xs"
      style={{
        background: isOnline
          ? 'color-mix(in srgb, var(--color-success, #22c55e) 6%, var(--color-surface))'
          : 'color-mix(in srgb, var(--color-error, #ef4444) 6%, var(--color-surface))',
        border: `1px solid color-mix(in srgb, ${dotColor} 25%, var(--color-border))`,
      }}
    >
      <Cloud size={13} style={{ color: dotColor, flexShrink: 0 }} />

      <span
        className="font-semibold shrink-0"
        style={{ color: 'var(--color-text)' }}
      >
        Mission Control
      </span>

      <span
        className="px-1.5 py-0.5 rounded font-medium shrink-0"
        style={{
          color: dotColor,
          background: `color-mix(in srgb, ${dotColor} 12%, transparent)`,
        }}
      >
        {isOnline ? 'Cloud Active' : isChecking ? 'Checking…' : 'Cloud Unreachable'}
      </span>

      {isOnline && bundle && (
        <>
          <span style={{ color: 'var(--color-text-tertiary)' }}>·</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>
            Cloud Runtime Active
          </span>
          <span style={{ color: 'var(--color-text-tertiary)' }}>·</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>
            Storage: {bundle.storage ?? 'Cloud Primary'}
          </span>
          <span style={{ color: 'var(--color-text-tertiary)' }}>·</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>
            Action Gate: {bundle.action_gate ?? 'Token Required'}
          </span>
        </>
      )}

      {nodeStatus === 'offline' && (
        <>
          <span style={{ color: 'var(--color-text-tertiary)' }}>·</span>
          <span style={{ color: 'var(--color-error, #ef4444)' }}>
            Cloud Unreachable — ensure Tailnet is active
          </span>
        </>
      )}

      <span className="ml-auto shrink-0" style={{ color: 'var(--color-text-tertiary)' }}>
        100.118.81.37 · {lastChecked}
      </span>
    </div>
  );
}
