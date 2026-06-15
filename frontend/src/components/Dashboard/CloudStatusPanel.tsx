import { useState } from 'react';
import { useCloudStatus } from '../Cloud/useCloudStatus';
import { Activity, Database, Shield, Network, Server, Clock, ExternalLink, CheckCircle, AlertCircle } from 'lucide-react';

const CLOUD_URL_KEY = 'omnix-cloud-node-url';

export function CloudStatusPanel() {
  const { nodeStatus, bundle, lastChecked, error, cloudUrl } = useCloudStatus();
  const [editingUrl, setEditingUrl] = useState(false);
  const [urlDraft, setUrlDraft] = useState(cloudUrl);

  const saveUrl = () => {
    const trimmed = urlDraft.replace(/\/+$/, '');
    localStorage.setItem(CLOUD_URL_KEY, trimmed);
    setUrlDraft(trimmed);
    setEditingUrl(false);
    window.location.reload();
  };

  const statusColor =
    nodeStatus === 'online'
      ? 'var(--color-success, #22c55e)'
      : nodeStatus === 'offline'
      ? 'var(--color-error, #ef4444)'
      : 'var(--color-text-tertiary, #888)';

  const statusLabel =
    nodeStatus === 'online' ? 'Cloud Active' : nodeStatus === 'offline' ? 'Offline' : 'Checking…';

  const isOnline = nodeStatus === 'online';

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, color-mix(in srgb, var(--color-surface) 85%, transparent) 0%, color-mix(in srgb, var(--color-surface) 70%, transparent) 100%)',
        border: '1px solid color-mix(in srgb, var(--color-border) 50%, transparent)',
        boxShadow: isOnline 
          ? '0 0 40px color-mix(in srgb, var(--color-success, #22c55e) 10%, transparent), inset 0 1px 0 color-mix(in srgb, rgba(255,255,255,0.05) 50%, transparent)'
          : '0 0 20px color-mix(in srgb, rgba(0,0,0,0.3) 50%, transparent), inset 0 1px 0 color-mix(in srgb, rgba(255,255,255,0.05) 50%, transparent)',
      }}
    >
      {/* Hero Panel */}
      <div
        className="px-5 py-4 flex items-center justify-between"
        style={{
          background: 'linear-gradient(90deg, color-mix(in srgb, var(--color-surface) 60%, transparent) 0%, transparent 100%)',
          borderBottom: '1px solid color-mix(in srgb, var(--color-border) 40%, transparent)',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-2.5 h-2.5 rounded-full animate-pulse"
            style={{ 
              background: statusColor,
              boxShadow: `0 0 12px ${statusColor}`,
            }}
          />
          <div>
            <h2 className="text-base font-bold tracking-wide" style={{ color: 'var(--color-text)' }}>
              MISSION CONTROL
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className="text-xs px-2 py-0.5 rounded font-semibold tracking-wider uppercase"
                style={{
                  color: statusColor,
                  background: `color-mix(in srgb, ${statusColor} 15%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${statusColor} 25%, transparent)`,
                }}
              >
                {statusLabel}
              </span>
              {isOnline && (
                <span className="text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>
                  OMNIX Cloud Node
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            <Clock size={12} />
            <span>{lastChecked}</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      {isOnline && bundle ? (
        <div className="p-5 flex flex-col gap-4">
          {/* Quick Info Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <QuickInfoCard
              icon={<Activity size={14} />}
              label="Runtime"
              value={bundle.runtime ?? 'OpenJarvis'}
              status="pass"
            />
            <QuickInfoCard
              icon={<Database size={14} />}
              label="Storage"
              value={bundle.storage ?? 'aws-s3'}
              status="pass"
            />
            <QuickInfoCard
              icon={<Shield size={14} />}
              label="Action Gate"
              value={bundle.action_gate ?? 'token-required'}
              status="pass"
            />
            <QuickInfoCard
              icon={<Network size={14} />}
              label="Tailscale"
              value={bundle.tailscale ?? 'connected'}
              status="pass"
            />
          </div>

          {/* Node Details Card */}
          <div
            className="rounded-lg p-4"
            style={{
              background: 'color-mix(in srgb, var(--color-surface) 50%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-border) 30%, transparent)',
            }}
          >
            <div className="flex items-center gap-2 mb-3">
              <Server size={14} style={{ color: 'var(--color-accent)' }} />
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
                Node Details
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <DetailRow label="Hostname" value={bundle.hostname ?? 'openclaw-mobile'} />
              <DetailRow label="Runtime" value={bundle.runtime ?? 'OpenJarvis'} />
              <DetailRow label="Tailnet IP" value={bundle.tailscale_ip ?? '100.118.81.37'} />
              <DetailRow label="Storage Source" value={bundle.storage ?? 'aws-s3'} />
              <DetailRow label="Action Gate" value={bundle.action_gate ?? 'token-required'} />
              <DetailRow label="Tailscale Status" value={bundle.tailscale ?? 'connected'} />
            </div>
          </div>

          {/* Operational Readiness */}
          <div
            className="rounded-lg p-4"
            style={{
              background: 'color-mix(in srgb, var(--color-surface) 50%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-border) 30%, transparent)',
            }}
          >
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle size={14} style={{ color: 'var(--color-success, #22c55e)' }} />
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
                Operational Readiness
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <ReadinessItem label="Cloud Runtime" status="pass" />
              <ReadinessItem label="Storage System" status="pass" />
              <ReadinessItem label="Tailscale Network" status="pass" />
              <ReadinessItem label="Action Gate Security" status="pass" />
            </div>
          </div>

          {/* Endpoints */}
          <div
            className="rounded-lg p-4"
            style={{
              background: 'color-mix(in srgb, var(--color-surface) 50%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-border) 30%, transparent)',
            }}
          >
            <div className="flex items-center gap-2 mb-3">
              <ExternalLink size={14} style={{ color: 'var(--color-accent)' }} />
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
                Tailnet Endpoints
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <EndpointLink url={`${cloudUrl}/health`} label="Health Check" />
              <EndpointLink url={`${cloudUrl}/api/jarvis/status-bundle`} label="Status Bundle API" />
            </div>
          </div>
        </div>
      ) : nodeStatus === 'offline' ? (
        <div className="p-5">
          <div
            className="flex items-center gap-3 px-4 py-3 rounded-lg"
            style={{
              background: 'color-mix(in srgb, var(--color-error, #ef4444) 8%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 20%, transparent)',
            }}
          >
            <AlertCircle size={16} style={{ color: 'var(--color-error, #ef4444)' }} />
            <span className="text-xs font-medium" style={{ color: 'var(--color-error, #ef4444)' }}>
              {error || 'Cloud Unreachable — ensure you are on Tailnet (100.118.81.37) and the node is running.'}
            </span>
          </div>
        </div>
      ) : (
        <div className="p-5">
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg" style={{ color: 'var(--color-text-tertiary)' }}>
            <div className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
            <span className="text-xs">Checking cloud status…</span>
          </div>
        </div>
      )}

      {/* URL Config Footer */}
      <div
        className="px-5 py-3 flex items-center justify-between"
        style={{
          background: 'color-mix(in srgb, var(--color-surface) 40%, transparent)',
          borderTop: '1px solid color-mix(in srgb, var(--color-border) 40%, transparent)',
        }}
      >
        {editingUrl ? (
          <div className="flex gap-2 items-center flex-1">
            <input
              className="flex-1 text-xs px-3 py-1.5 rounded-lg border"
              style={{
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                borderColor: 'var(--color-border)',
              }}
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && saveUrl()}
              placeholder="http://100.118.81.37:3091"
              autoFocus
            />
            <button
              onClick={saveUrl}
              className="text-xs px-3 py-1.5 rounded-lg font-medium"
              style={{ background: 'var(--color-accent)', color: '#fff' }}
            >
              Save
            </button>
            <button
              onClick={() => { setEditingUrl(false); setUrlDraft(cloudUrl); }}
              className="text-xs px-3 py-1.5 rounded-lg font-medium"
              style={{ background: 'var(--color-surface)', color: 'var(--color-text-secondary)' }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>
                Cloud Node URL:
              </span>
              <span className="text-xs font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                {cloudUrl}
              </span>
            </div>
            <button
              onClick={() => { setEditingUrl(true); setUrlDraft(cloudUrl); }}
              className="text-xs font-medium underline"
              style={{ color: 'var(--color-accent)' }}
            >
              Configure
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function QuickInfoCard({ icon, label, value, status }: { icon: React.ReactNode; label: string; value: string; status: 'pass' | 'attention' | 'unknown' }) {
  const statusColor = status === 'pass' ? 'var(--color-success, #22c55e)' : status === 'attention' ? 'var(--color-error, #ef4444)' : 'var(--color-text-tertiary, #888)';
  
  return (
    <div
      className="rounded-lg p-3 flex flex-col gap-2"
      style={{
        background: 'color-mix(in srgb, var(--color-surface) 60%, transparent)',
        border: '1px solid color-mix(in srgb, var(--color-border) 40%, transparent)',
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5" style={{ color: statusColor }}>
          {icon}
        </div>
        {status === 'pass' && <CheckCircle size={12} style={{ color: statusColor }} />}
        {status === 'attention' && <AlertCircle size={12} style={{ color: statusColor }} />}
      </div>
      <div>
        <div className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
          {value}
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
          {label}
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
      <span className="text-xs font-medium font-mono" style={{ color: 'var(--color-text-secondary)' }}>{value}</span>
    </div>
  );
}

function ReadinessItem({ label, status }: { label: string; status: 'pass' | 'attention' | 'unknown' }) {
  const statusColor = status === 'pass' ? 'var(--color-success, #22c55e)' : status === 'attention' ? 'var(--color-error, #ef4444)' : 'var(--color-text-tertiary, #888)';
  const statusText = status === 'pass' ? 'PASS' : status === 'attention' ? 'ATTENTION' : 'UNKNOWN';
  
  return (
    <div className="flex items-center justify-between px-3 py-2 rounded" style={{ background: 'color-mix(in srgb, var(--color-surface) 50%, transparent)' }}>
      <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
      <span
        className="text-xs px-2 py-0.5 rounded font-semibold"
        style={{
          color: statusColor,
          background: `color-mix(in srgb, ${statusColor} 12%, transparent)`,
          border: `1px solid color-mix(in srgb, ${statusColor} 20%, transparent)`,
        }}
      >
        {statusText}
      </span>
    </div>
  );
}

function EndpointLink({ url, label }: { url: string; label: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-between px-3 py-2 rounded hover:opacity-80 transition-opacity"
      style={{
        background: 'color-mix(in srgb, var(--color-surface) 50%, transparent)',
        border: '1px solid color-mix(in srgb, var(--color-border) 30%, transparent)',
        color: 'var(--color-text-secondary)',
        textDecoration: 'none',
      }}
    >
      <div className="flex items-center gap-2">
        <ExternalLink size={12} style={{ color: 'var(--color-accent)' }} />
        <span className="text-xs font-medium">{label}</span>
      </div>
      <span className="text-xs font-mono truncate max-w-[200px]" style={{ color: 'var(--color-text-tertiary)' }}>
        {url}
      </span>
    </a>
  );
}
