import { useState, useEffect } from 'react';
import { Package, CheckCircle, XCircle, MinusCircle, Clock } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { fetchSkillsCatalogSummary, type SkillsCatalogSummary } from '../lib/jarvis-api';

interface Skill {
  id: string;
  name: string;
  description: string;
  status: string;
  safety_level: string;
  enabled: boolean;
  source?: string;
  tags?: string[];
}

interface SkillsListResponse {
  skills: Skill[];
  count: number;
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    available: { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)', label: 'Available' },
    enabled:   { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)', label: 'Enabled' },
    disabled:  { bg: 'color-mix(in srgb, var(--color-text-tertiary) 12%, transparent)', color: 'var(--color-text-tertiary)', label: 'Disabled' },
    blocked:   { bg: 'color-mix(in srgb, var(--color-danger, #f38ba8) 15%, transparent)', color: 'var(--color-danger, #f38ba8)', label: 'Blocked' },
    planned:   { bg: 'color-mix(in srgb, var(--color-info, #89dceb) 15%, transparent)', color: 'var(--color-info, #89dceb)', label: 'Planned' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)', label: status };
  return (
    <span
      className="text-[10px] px-2 py-0.5 rounded-full font-medium"
      style={{ background: s.bg, color: s.color }}
    >
      {s.label}
    </span>
  );
}

function SafetyBadge({ level }: { level: string }) {
  const map: Record<string, { color: string }> = {
    low:      { color: 'var(--color-success, #a6e3a1)' },
    medium:   { color: 'var(--color-warning, #f9e2af)' },
    high:     { color: 'var(--color-danger, #f38ba8)' },
    critical: { color: 'var(--color-danger, #f38ba8)' },
  };
  const s = map[level?.toLowerCase()] ?? { color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ color: s.color, border: `1px solid ${s.color}`, opacity: 0.85 }}>
      safety:{level ?? 'unknown'}
    </span>
  );
}

export function SkillsPluginsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [catalog, setCatalog] = useState<SkillsCatalogSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<Record<string, boolean>>({});
  const [confirmation, setConfirmation] = useState<Record<string, string>>({});

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/skills').then((r) => r.json() as Promise<SkillsListResponse>),
      fetchSkillsCatalogSummary(),
    ])
      .then(([skillsData, catalogData]) => {
        setSkills(skillsData.skills ?? []);
        setCatalog(catalogData);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load skills'))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (skill: Skill) => {
    const action = skill.enabled ? 'disable' : 'enable';
    setToggling((t) => ({ ...t, [skill.id]: true }));
    try {
      await apiFetch(`/v1/skills/${encodeURIComponent(skill.id)}/${action}`, { method: 'POST' });
      setSkills((prev) => prev.map((s) => s.id === skill.id ? { ...s, enabled: !s.enabled } : s));
      setConfirmation((c) => ({ ...c, [skill.id]: action === 'enable' ? 'Enabled' : 'Disabled' }));
      setTimeout(() => setConfirmation((c) => { const n = { ...c }; delete n[skill.id]; return n; }), 2500);
    } catch {
      setConfirmation((c) => ({ ...c, [skill.id]: 'Failed' }));
      setTimeout(() => setConfirmation((c) => { const n = { ...c }; delete n[skill.id]; return n; }), 2500);
    } finally {
      setToggling((t) => { const n = { ...t }; delete n[skill.id]; return n; });
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading skills...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <XCircle size={32} className="mx-auto mb-2" style={{ color: 'var(--color-danger, #f38ba8)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Package size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Skills &amp; Plugins</h1>
      </div>

      {/* Stats strip */}
      {catalog && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Total', value: catalog.total, icon: Package },
            { label: 'Available', value: catalog.available, icon: CheckCircle, color: 'var(--color-success, #a6e3a1)' },
            { label: 'Blocked / Disabled', value: (catalog.blocked ?? 0) + (catalog.disabled ?? 0), icon: XCircle, color: 'var(--color-danger, #f38ba8)' },
            { label: 'Planned', value: catalog.planned ?? 0, icon: Clock, color: 'var(--color-info, #89dceb)' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              className="rounded-xl px-4 py-3 flex flex-col gap-1"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center gap-1.5">
                <Icon size={13} style={{ color: color ?? 'var(--color-text-tertiary)' }} />
                <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</span>
              </div>
              <span className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Skills list */}
      {skills.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Package size={32} style={{ color: 'var(--color-text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No skills found</p>
        </div>
      ) : (
        <div className="space-y-3">
          {skills.map((skill) => (
            <div
              key={skill.id}
              className="rounded-xl px-4 py-4 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
            >
              <div className="flex-1 min-w-0 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{skill.name}</span>
                  <StatusChip status={skill.status} />
                  <SafetyBadge level={skill.safety_level} />
                </div>
                <p className="text-xs leading-relaxed line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>
                  {skill.description || 'No description available.'}
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {confirmation[skill.id] && (
                  <span className="text-xs" style={{ color: confirmation[skill.id] === 'Failed' ? 'var(--color-danger, #f38ba8)' : 'var(--color-success, #a6e3a1)' }}>
                    {confirmation[skill.id]}
                  </span>
                )}
                <button
                  onClick={() => handleToggle(skill)}
                  disabled={toggling[skill.id]}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
                  style={{
                    background: skill.enabled
                      ? 'color-mix(in srgb, var(--color-danger, #f38ba8) 12%, transparent)'
                      : 'color-mix(in srgb, var(--color-success, #a6e3a1) 12%, transparent)',
                    color: skill.enabled ? 'var(--color-danger, #f38ba8)' : 'var(--color-success, #a6e3a1)',
                    border: `1px solid ${skill.enabled ? 'color-mix(in srgb, var(--color-danger, #f38ba8) 25%, transparent)' : 'color-mix(in srgb, var(--color-success, #a6e3a1) 25%, transparent)'}`,
                  }}
                >
                  {toggling[skill.id] ? (
                    <MinusCircle size={12} className="animate-spin" />
                  ) : skill.enabled ? (
                    <XCircle size={12} />
                  ) : (
                    <CheckCircle size={12} />
                  )}
                  {skill.enabled ? 'Disable' : 'Enable'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Intake section */}
      <div
        className="rounded-xl px-4 py-4"
        style={{ background: 'var(--color-bg-tertiary)', border: '1px solid var(--color-border)' }}
      >
        <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-secondary)' }}>Third-party plugin intake</p>
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          Manual review required. No automated marketplace.
        </p>
      </div>
    </div>
  );
}
