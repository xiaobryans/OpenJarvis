import { useState, useEffect } from 'react';
import { Lightbulb, XCircle, AlertTriangle, Shield } from 'lucide-react';
import {
  fetchProactiveSuggestions,
  fetchStaleItems,
  fetchNextActions,
  type ProactiveSuggestion,
  type ProactiveSuggestionsResponse,
  type StaleItem,
  type NextAction,
} from '../lib/jarvis-api';

type Tab = 'suggestions' | 'stale' | 'next-actions';

function PriorityChip({ priority }: { priority: string }) {
  const map: Record<string, { color: string }> = {
    high:   { color: 'var(--color-danger, #f38ba8)' },
    medium: { color: 'var(--color-warning, #f9e2af)' },
    low:    { color: 'var(--color-info, #89dceb)' },
  };
  const s = map[priority?.toLowerCase()] ?? { color: 'var(--color-text-tertiary)' };
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ color: s.color, border: `1px solid ${s.color}`, opacity: 0.85 }}>
      {priority}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}>
      {type}
    </span>
  );
}

function SuggestionCard({ s }: { s: ProactiveSuggestion }) {
  return (
    <div
      className="rounded-xl px-4 py-4 space-y-2"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <TypeBadge type={s.type} />
        <PriorityChip priority={s.priority} />
        <span className="font-medium text-sm" style={{ color: 'var(--color-text)' }}>{s.title}</span>
      </div>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>{s.description}</p>
      {s.approval_route && (
        <div className="flex items-center gap-1.5 pt-1">
          <Shield size={11} style={{ color: 'var(--color-warning, #f9e2af)' }} />
          <code className="text-[10px] font-mono" style={{ color: 'var(--color-text-tertiary)' }}>{s.approval_route}</code>
        </div>
      )}
      {s.action_type && !s.approval_route && (
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>action: {s.action_type}</p>
      )}
    </div>
  );
}

function StaleItemRow({ item }: { item: StaleItem }) {
  return (
    <div
      className="rounded-xl px-4 py-3 flex flex-wrap items-center gap-3"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <span
        className="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
        style={{ background: 'color-mix(in srgb, var(--color-warning, #f9e2af) 15%, transparent)', color: 'var(--color-warning, #f9e2af)' }}
      >
        {item.age_days}d old
      </span>
      <span className="flex-1 text-sm font-medium" style={{ color: 'var(--color-text)' }}>{item.title}</span>
      <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{item.status}</span>
    </div>
  );
}

function NextActionRow({ action }: { action: NextAction }) {
  return (
    <div
      className="rounded-xl px-4 py-4 space-y-1.5"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}>
          #{action.rank}
        </span>
        <PriorityChip priority={action.priority} />
        {action.approval_required && (
          <span className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--color-warning, #f9e2af)' }}>
            <Shield size={10} />approval required
          </span>
        )}
      </div>
      <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{action.action}</p>
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{action.reason}</p>
    </div>
  );
}

export function ProactiveOperatorPage() {
  const [tab, setTab] = useState<Tab>('suggestions');
  const [suggestionsData, setSuggestionsData] = useState<ProactiveSuggestionsResponse | null>(null);
  const [staleItems, setStaleItems] = useState<StaleItem[]>([]);
  const [nextActions, setNextActions] = useState<NextAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchProactiveSuggestions(),
      fetchStaleItems(),
      fetchNextActions(),
    ])
      .then(([s, stale, next]) => {
        setSuggestionsData(s);
        setStaleItems(stale.stale_tasks ?? []);
        setNextActions(next.next_actions ?? []);
      })
      .catch((e) => setError(e?.message ?? 'Failed to load proactive data'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        <span className="text-sm">Loading proactive suggestions...</span>
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

  const suggestions = suggestionsData?.suggestions ?? [];

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'suggestions', label: 'Suggestions', count: suggestions.length },
    { id: 'stale', label: 'Stale Items', count: staleItems.length },
    { id: 'next-actions', label: 'Next Actions', count: nextActions.length },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Lightbulb size={22} style={{ color: 'var(--color-accent)' }} />
        <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>Proactive Operator</h1>
      </div>

      {/* Important banner */}
      <div
        className="flex items-start gap-2 rounded-xl px-4 py-3"
        style={{ background: 'color-mix(in srgb, var(--color-info, #89dceb) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-info, #89dceb) 20%, transparent)' }}
      >
        <AlertTriangle size={14} style={{ color: 'var(--color-info, #89dceb)', flexShrink: 0, marginTop: 1 }} />
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Suggestions only — no action is taken automatically. Approval required for any execution.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
            style={{
              background: tab === t.id ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
              color: tab === t.id ? 'var(--color-text)' : 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
          >
            {t.label}
            <span
              className="px-1.5 py-0.5 rounded-full text-[10px]"
              style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
            >
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'suggestions' && (
        suggestions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Lightbulb size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No suggestions at this time.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {suggestions.map((s, i) => (
              <SuggestionCard key={s.source_id ?? i} s={s} />
            ))}
          </div>
        )
      )}

      {tab === 'stale' && (
        staleItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Lightbulb size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No stale items found.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {staleItems.map((item) => (
              <StaleItemRow key={item.task_id} item={item} />
            ))}
          </div>
        )
      )}

      {tab === 'next-actions' && (
        nextActions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Lightbulb size={32} style={{ color: 'var(--color-text-tertiary)' }} />
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No next actions available.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {nextActions.map((a) => (
              <NextActionRow key={a.rank} action={a} />
            ))}
          </div>
        )
      )}
    </div>
  );
}
