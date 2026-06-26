import { useState, useRef, useEffect } from 'react';
import { Search, X, Clock } from 'lucide-react';
import { useAppStore } from '../../lib/store';
import { MessageBubble } from './MessageBubble';

/**
 * Read-only chat/session history viewer — bound to Cmd+K.
 *
 * Shows the current conversation history with search/filter.
 * Does NOT submit messages or call any model/completion endpoint.
 * The only Jarvis chat input is in the main cockpit.
 */
export function HistoryViewer() {
  const messages = useAppStore((s) => s.messages);
  const [query, setQuery] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus search box on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Scroll to bottom on mount so latest messages are visible
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? messages.filter((m) => m.content.toLowerCase().includes(q))
    : messages;

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div
        className="px-4 py-2 shrink-0"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg"
          style={{
            background: 'var(--color-input-bg)',
            border: '1px solid var(--color-input-border)',
          }}
        >
          <Search size={14} style={{ color: 'var(--color-text-tertiary)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search this conversation…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: 'var(--color-text)' }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="p-0.5 cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)', background: 'none', border: 'none' }}
              title="Clear search"
            >
              <X size={12} />
            </button>
          )}
        </div>
        {q && (
          <p className="text-[11px] mt-1 pl-1" style={{ color: 'var(--color-text-tertiary)' }}>
            {filtered.length === 0
              ? 'No matches'
              : `${filtered.length} message${filtered.length !== 1 ? 's' : ''} matching "${query}"`}
          </p>
        )}
      </div>

      {/* Message list */}
      <div ref={listRef} className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center gap-2">
            <Clock size={28} style={{ color: 'var(--color-text-tertiary)', opacity: 0.5 }} />
            <p className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
              No conversation history yet
            </p>
            <p className="text-[12px]" style={{ color: 'var(--color-text-tertiary)' }}>
              Messages from the main cockpit will appear here.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full px-6">
            <p className="text-sm text-center" style={{ color: 'var(--color-text-tertiary)' }}>
              No messages match &ldquo;{query}&rdquo;
            </p>
          </div>
        ) : (
          <div
            className="mx-auto px-4 py-4"
            style={{ maxWidth: 'var(--chat-max-width, 680px)' }}
          >
            {filtered.map((msg) => (
              <MessageBubble key={msg.id} message={msg} isLive={false} />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        className="px-4 py-2 text-center text-[11px] shrink-0"
        style={{
          borderTop: '1px solid var(--color-border)',
          color: 'var(--color-text-tertiary)',
        }}
      >
        Read-only history &middot; talk to VANTA in the main cockpit &middot;{' '}
        <kbd className="font-mono">Esc</kbd> to close
      </div>
    </div>
  );
}
