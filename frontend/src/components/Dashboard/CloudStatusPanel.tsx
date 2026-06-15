import { useEffect, useState, useCallback } from 'react';

const DEFAULT_CLOUD_URL = 'http://100.118.81.37:3091';
const CLOUD_URL_KEY = 'omnix-cloud-node-url';
const POLL_INTERVAL = 30000;

interface HealthData {
  status: string;
  hostname: string;
  runtime: string;
}

interface StatusBundleData {
  hostname: string;
  runtime: string;
  tailscale: string;
  storage: string;
  action_gate?: string;
  tailscale_ip?: string;
}

type NodeStatus = 'online' | 'offline' | 'checking';

export function CloudStatusPanel() {
  const [cloudUrl, setCloudUrl] = useState<string>(
    () => localStorage.getItem(CLOUD_URL_KEY) || DEFAULT_CLOUD_URL
  );
  const [editingUrl, setEditingUrl] = useState(false);
  const [urlDraft, setUrlDraft] = useState(cloudUrl);

  const [nodeStatus, setNodeStatus] = useState<NodeStatus>('checking');
  const [health, setHealth] = useState<HealthData | null>(null);
  const [bundle, setBundle] = useState<StatusBundleData | null>(null);
  const [lastChecked, setLastChecked] = useState<string>('—');
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
    setNodeStatus('checking');
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const [hRes, sRes] = await Promise.all([
        fetch(`${cloudUrl}/health`, { signal: controller.signal }),
        fetch(`${cloudUrl}/api/jarvis/status-bundle`, { signal: controller.signal }),
      ]);
      clearTimeout(timeout);
      const hData: HealthData = await hRes.json();
      const sData: StatusBundleData = await sRes.json();
      setHealth(hData);
      setBundle(sData);
      setNodeStatus('online');
      setError(null);
    } catch (e) {
      setNodeStatus('offline');
      setHealth(null);
      setBundle(null);
      setError('Cloud node unreachable');
    }
    setLastChecked(new Date().toLocaleTimeString());
  }, [cloudUrl]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [poll]);

  const saveUrl = () => {
    const trimmed = urlDraft.replace(/\/+$/, '');
    setCloudUrl(trimmed);
    localStorage.setItem(CLOUD_URL_KEY, trimmed);
    setEditingUrl(false);
  };

  const dot = (color: string) => (
    <span
      className="w-2 h-2 rounded-full shrink-0 inline-block"
      style={{ background: color }}
    />
  );

  const statusColor =
    nodeStatus === 'online'
      ? 'var(--color-success, #22c55e)'
      : nodeStatus === 'offline'
      ? 'var(--color-error, #ef4444)'
      : 'var(--color-text-tertiary, #888)';

  const statusLabel =
    nodeStatus === 'online' ? 'Online' : nodeStatus === 'offline' ? 'Offline' : 'Checking…';

  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-3"
      style={{
        background: 'color-mix(in srgb, var(--color-surface) 80%, transparent)',
        border: '1px solid color-mix(in srgb, var(--color-border) 60%, transparent)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {dot(statusColor)}
          <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            Mission Control
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded font-medium"
            style={{
              color: statusColor,
              background: `color-mix(in srgb, ${statusColor} 12%, transparent)`,
            }}
          >
            {nodeStatus === 'online' ? 'Cloud Active' : statusLabel}
          </span>
          {nodeStatus === 'online' && (
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              OMNIX Cloud Node
            </span>
          )}
        </div>
        <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {lastChecked}
        </span>
      </div>

      {/* Node details */}
      {nodeStatus === 'online' && health && bundle && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
          <Row label="Status" value="Cloud Runtime Active" highlight />
          <Row label="Storage" value={bundle.storage ?? 'Cloud Primary'} />
          <Row label="Action Gate" value={bundle.action_gate ?? 'Token Required'} />
          <Row label="Tailscale" value={bundle.tailscale} />
          <Row label="Hostname" value={health.hostname} />
          <Row label="Runtime" value={health.runtime} />
        </div>
      )}

      {/* Endpoint links */}
      {nodeStatus === 'online' && (
        <div className="flex flex-col gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          <span className="font-medium" style={{ color: 'var(--color-text-tertiary)' }}>
            Tailnet Endpoints
          </span>
          <a
            href={`${cloudUrl}/health`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline truncate"
            style={{ color: 'var(--color-accent)' }}
          >
            {cloudUrl}/health
          </a>
          <a
            href={`${cloudUrl}/api/jarvis/status-bundle`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline truncate"
            style={{ color: 'var(--color-accent)' }}
          >
            {cloudUrl}/api/jarvis/status-bundle
          </a>
        </div>
      )}

      {/* Offline error */}
      {nodeStatus === 'offline' && (
        <div
          className="text-xs px-2 py-1.5 rounded font-medium"
          style={{
            background: 'color-mix(in srgb, var(--color-error, #ef4444) 8%, transparent)',
            color: 'var(--color-error, #ef4444)',
            border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 20%, transparent)',
          }}
        >
          Cloud Unreachable — ensure you are on Tailnet (100.118.81.37) and the node is running.
        </div>
      )}

      {/* Cloud node URL config */}
      <div className="mt-1 border-t pt-2" style={{ borderColor: 'color-mix(in srgb, var(--color-border) 40%, transparent)' }}>
        {editingUrl ? (
          <div className="flex gap-2 items-center">
            <input
              className="flex-1 text-xs px-2 py-1 rounded border"
              style={{
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                borderColor: 'var(--color-border)',
              }}
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && saveUrl()}
              autoFocus
            />
            <button
              onClick={saveUrl}
              className="text-xs px-2 py-1 rounded"
              style={{ background: 'var(--color-accent)', color: '#fff' }}
            >
              Save
            </button>
            <button
              onClick={() => { setEditingUrl(false); setUrlDraft(cloudUrl); }}
              className="text-xs px-2 py-1 rounded"
              style={{ background: 'var(--color-surface)', color: 'var(--color-text-secondary)' }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-xs truncate max-w-[200px]" style={{ color: 'var(--color-text-tertiary)' }}>
              {cloudUrl}
            </span>
            <button
              onClick={() => { setEditingUrl(true); setUrlDraft(cloudUrl); }}
              className="text-xs underline shrink-0"
              style={{ color: 'var(--color-accent)' }}
            >
              Change
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <>
      <span style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
      <span
        style={{
          color: highlight ? 'var(--color-success, #22c55e)' : 'var(--color-text-secondary)',
          fontWeight: highlight ? 600 : 400,
        }}
      >
        {value}
      </span>
    </>
  );
}
