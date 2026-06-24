import { useEffect } from 'react';
import { X, History } from 'lucide-react';
import { useAppStore } from '../lib/store';
import { HistoryViewer } from './Chat/HistoryViewer';

/**
 * Cmd+K history viewer panel.
 *
 * Read-only chat/session history with search. Does NOT submit messages
 * or generate model responses — chat input lives in the main cockpit only.
 * Cmd+Shift+K opens the command palette instead.
 */
export function TextFallbackPanel() {
  const setTextFallbackOpen = useAppStore((s) => s.setTextFallbackOpen);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setTextFallbackOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setTextFallbackOpen]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={() => setTextFallbackOpen(false)}
    >
      <div className="fixed inset-0" style={{ background: 'rgba(0,0,0,0.55)' }} />

      <div
        className="relative w-full max-w-2xl h-[80vh] rounded-xl overflow-hidden flex flex-col"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-lg)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2 px-4 py-3 shrink-0"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <History size={16} style={{ color: 'var(--color-accent)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Chat History
          </span>
          <span className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
            view &amp; search · ⌘K / Esc to close
          </span>
          <button
            onClick={() => setTextFallbackOpen(false)}
            className="ml-auto p-1 rounded cursor-pointer"
            style={{ color: 'var(--color-text-tertiary)' }}
            title="Close (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body — read-only history viewer, no chat input */}
        <div className="flex-1 min-h-0">
          <HistoryViewer />
        </div>
      </div>
    </div>
  );
}
