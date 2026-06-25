import { useState, useEffect } from 'react';
import { BookOpen, XCircle, AlertTriangle } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface ResearchSection {
  name: string;
  status: string;
  description: string;
  source_route?: string;
  live_web_retrieval?: boolean;
}

interface ResearchTemplate {
  name: string;
  description: string;
  fields: string[];
}

interface ResearchDashboard {
  sections: ResearchSection[];
}

interface ResearchTemplatesResponse {
  templates: ResearchTemplate[];
}

type Tab = 'sections' | 'templates';

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    available: { bg: 'color-mix(in srgb, var(--color-success, #a6e3a1) 15%, transparent)', color: 'var(--color-success, #a6e3a1)' },
    partial:   { bg: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' },
    planned:   { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' },
  };
  const s = map[status?.toLowerCase()] ?? { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

function SectionCard({ section }: { section: ResearchSection }) {
  return (
    <div
      className="rounded-xl p-4 space-y-2"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{section.name}</span>
        <StatusChip status={section.status} />
        {section.live_web_retrieval === false && (
          <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'color-mix(in srgb, var(--color-danger, #f38ba8) 12%, transparent)', color: 'var(--color-danger, #f38ba8)' }}>
            no live web
          </span>
        )}
      </div>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>{section.description}</p>
      {section.source_route && (
        <code className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)', fontFamily: 'monospace' }}>
          {section.source_route}
        </code>
      )}
    </div>
  );
}

function TemplateCard({ tpl }: { tpl: ResearchTemplate }) {
  return (
    <div
      className="rounded-xl p-4 space-y-2"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{tpl.name}</span>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>{tpl.description}</p>
      {tpl.fields && tpl.fields.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {tpl.fields.map((f, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}>
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ResearchOSPage() {
  const [dashboard, setDashboard] = useState<ResearchDashboard | null>(null);
  const [templates, setTemplates] = useState<ResearchTemplate[]>([]);
  const [tab, setTab] = useState<Tab>('sections');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/v1/research-os/dashboard').then((r) => r.json()),
      apiFetch('/v1/research-os/templates').then((r) => r.json()),
    ])
      .then(([d, t]: [ResearchDashboard, ResearchTemplatesResponse]) => {
        setDashboard(d);
        setTemplates(t?.templates ?? []);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load Research OS'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading Research OS...</span>
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

  const sections = dashboard?.sections ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BookOpen size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Research, Learning & Company OS</h1>
      </div>

      {/* Honesty banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, #f97316 8%, transparent)', border: '1px solid color-mix(in srgb, #f97316 25%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: '#f97316', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          No live web retrieval. All research linked to local tasks/goals/memory.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {(['sections', 'templates'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{
              background: tab === t ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
              color: tab === t ? '#fff' : 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Sections tab */}
      {tab === 'sections' && (
        sections.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <BookOpen size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No sections found.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sections.map((s, i) => <SectionCard key={i} section={s} />)}
          </div>
        )
      )}

      {/* Templates tab */}
      {tab === 'templates' && (
        templates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <BookOpen size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No templates found.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {templates.map((t, i) => <TemplateCard key={i} tpl={t} />)}
          </div>
        )
      )}

      {/* Provenance footer */}
      <p className="text-[10px] pt-2" style={{ color: 'var(--color-text-tertiary)' }}>
        Source: /v1/research-os/dashboard · Phase B14 · No fake data
      </p>
    </div>
  );
}
