import { useRef, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { MessageBubble } from './MessageBubble';
import { StreamingDots } from './StreamingDots';
import { useAppStore } from '../../lib/store';
import {
  Command, Search, Code2, Bot, Database, Zap, ArrowRight,
  Loader2, SquareArrowOutUpRight,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Greeting
// ---------------------------------------------------------------------------

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return 'Working late';
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  if (hour < 21) return 'Good evening';
  return 'Good night';
}

// ---------------------------------------------------------------------------
// Quick-launch suggestions shown on idle home state
// ---------------------------------------------------------------------------

interface Suggestion {
  label: string;
  icon: React.ReactNode;
  prompt?: string;
  action?: () => void;
}

function QuickSuggestions({
  onPick,
  navigate,
}: {
  onPick: (prompt: string) => void;
  navigate: (path: string) => void;
}) {
  const suggestions: Suggestion[] = [
    { label: 'Deep research', icon: <Search size={13} />, prompt: '/research ' },
    { label: 'Plan in Workbench', icon: <Code2 size={13} />, prompt: '/workbench ' },
    { label: 'View agents', icon: <Bot size={13} />, action: () => navigate('/agents') },
    { label: 'Connect data', icon: <Database size={13} />, action: () => navigate('/data-sources') },
  ];

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {suggestions.map((s) => (
        <button
          key={s.label}
          onClick={() => s.action ? s.action() : onPick(s.prompt ?? '')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer transition-all"
          style={{
            background: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-tertiary)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--p2-teal-dim)';
            e.currentTarget.style.borderColor = 'var(--p2-teal)';
            e.currentTarget.style.color = 'var(--p2-teal)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--color-bg-secondary)';
            e.currentTarget.style.borderColor = 'var(--color-border)';
            e.currentTarget.style.color = 'var(--color-text-tertiary)';
          }}
        >
          <span style={{ color: 'inherit' }}>{s.icon}</span>
          {s.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Idle / home state
// ---------------------------------------------------------------------------

function IdleHome({
  onOpen,
  navigate,
}: {
  onOpen: (prefill?: string) => void;
  navigate: (path: string) => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div className="flex flex-col items-center justify-center h-full px-6 select-none" style={{ paddingBottom: '8vh' }}>

      {/* Identity label */}
      <div
        className="mb-8 tracking-[0.22em] text-[10px] font-medium uppercase"
        style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-hud)', letterSpacing: '0.22em' }}
      >
        JARVIS
      </div>

      {/* Greeting */}
      <h2
        className="text-[1.6rem] font-semibold mb-1.5 text-center"
        style={{ color: 'var(--color-text)', fontFamily: 'var(--font-display)', letterSpacing: '-0.01em' }}
      >
        {getGreeting()}
      </h2>
      <p className="text-sm text-center mb-10 max-w-[260px]" style={{ color: 'var(--color-text-tertiary)' }}>
        Ask, research, plan, automate.
      </p>

      {/* Primary CTA — the front door */}
      <button
        onClick={() => onOpen()}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className="relative flex items-center gap-3 rounded-2xl cursor-pointer transition-all mb-8"
        style={{
          padding: '14px 28px',
          background: hovered ? 'var(--p2-teal)' : 'var(--color-bg-secondary)',
          border: `1px solid ${hovered ? 'var(--p2-teal)' : 'var(--color-border)'}`,
          color: hovered ? '#fff' : 'var(--color-text-secondary)',
          boxShadow: hovered ? 'var(--p2-glow-teal)' : 'var(--p2-elev-1)',
          transform: hovered ? 'translateY(-2px)' : 'none',
          transition: 'all var(--p2-dur-base) var(--p2-ease-spring)',
          minWidth: '220px',
          justifyContent: 'center',
        }}
      >
        <Command size={16} />
        <span className="text-sm font-medium">Open composer</span>
        <kbd
          className="text-[10px] px-1.5 py-0.5 rounded font-mono ml-1"
          style={{
            background: hovered ? 'rgba(255,255,255,0.15)' : 'var(--color-bg-tertiary)',
            color: hovered ? 'rgba(255,255,255,0.8)' : 'var(--color-text-tertiary)',
            border: `1px solid ${hovered ? 'rgba(255,255,255,0.2)' : 'var(--color-border)'}`,
          }}
        >
          ⌘K
        </kbd>
        {hovered && (
          <ArrowRight
            size={14}
            className="absolute right-4"
            style={{ color: 'rgba(255,255,255,0.7)', transition: 'opacity var(--p2-dur-fast)' }}
          />
        )}
      </button>

      {/* Quick-launch suggestions */}
      <QuickSuggestions onPick={(p) => onOpen(p)} navigate={navigate} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Streaming progress indicator
// ---------------------------------------------------------------------------

function StreamingBanner({ phase }: { phase?: string }) {
  return (
    <div
      className="flex items-center gap-2 px-4 py-2 mx-auto mb-4 rounded-xl text-xs"
      style={{
        background: 'var(--p2-indigo-dim)',
        border: '1px solid var(--p2-indigo)',
        color: 'var(--p2-indigo)',
        maxWidth: 'var(--chat-max-width)',
        width: '100%',
      }}
    >
      <Loader2 size={12} className="animate-spin shrink-0" />
      <span>{phase || 'Generating…'}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Composer-bar — shown at bottom when there are messages
// ---------------------------------------------------------------------------

function ComposerBar({ onClick, isStreaming }: { onClick: () => void; isStreaming: boolean }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="shrink-0 px-4 py-3 flex justify-center"
      style={{ borderTop: '1px solid var(--color-border-subtle)' }}
    >
      <button
        onClick={onClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className="flex items-center gap-2.5 rounded-xl cursor-pointer transition-all"
        style={{
          padding: '9px 20px',
          width: '100%',
          maxWidth: 'var(--chat-max-width)',
          background: hovered ? 'var(--p2-teal-dim)' : 'var(--color-bg-secondary)',
          border: `1px solid ${hovered ? 'var(--p2-teal)' : 'var(--color-border)'}`,
          color: hovered ? 'var(--p2-teal)' : 'var(--color-text-tertiary)',
          boxShadow: hovered ? 'var(--p2-elev-1)' : 'none',
          transition: 'all var(--p2-dur-base) var(--p2-ease-smooth)',
          justifyContent: 'space-between',
        }}
      >
        <div className="flex items-center gap-2">
          <Command size={13} />
          <span className="text-sm">
            {isStreaming ? 'Generating response…' : 'Reply or command…'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {isStreaming ? (
            <Loader2 size={12} className="animate-spin" style={{ color: 'var(--p2-teal)' }} />
          ) : (
            <kbd
              className="text-[10px] px-1.5 py-0.5 rounded font-mono"
              style={{
                background: 'var(--color-bg-tertiary)',
                color: 'var(--color-text-tertiary)',
                border: '1px solid var(--color-border)',
              }}
            >
              ⌘K
            </kbd>
          )}
        </div>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ChatArea() {
  const messages = useAppStore((s) => s.messages);
  const streamState = useAppStore((s) => s.streamState);
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  // Prefill composer and open it
  const openComposer = (prefill?: string) => {
    if (prefill) {
      // Store prefill in sessionStorage; composer reads it on mount
      sessionStorage.setItem('composer-prefill', prefill);
    }
    setComposerOpen(true);
  };

  useEffect(() => {
    if (shouldAutoScroll.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, streamState.content]);

  const handleScroll = () => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    shouldAutoScroll.current = scrollHeight - scrollTop - clientHeight < 100;
  };

  const isEmpty = messages.length === 0 && !streamState.isStreaming;

  return (
    <div className="flex flex-col h-full">
      <div
        ref={listRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {isEmpty ? (
          <IdleHome onOpen={openComposer} navigate={navigate} />
        ) : (
          <div
            className="max-w-[var(--chat-max-width)] mx-auto px-4 pt-6 pb-4"
            style={{ animation: 'p2-mode-b-in var(--p2-dur-slow) var(--p2-ease-smooth)' }}
          >
            {messages.map((msg, i) => {
              const isLastAssistant = i === messages.length - 1 && msg.role === 'assistant';
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isLive={isLastAssistant && streamState.isStreaming}
                />
              );
            })}
            {(() => {
              if (!streamState.isStreaming || streamState.content !== '') return null;
              const last = messages[messages.length - 1];
              if (last?.role === 'assistant' && last.isResearch) return null;
              return (
                <div className="flex justify-start mb-4">
                  <StreamingDots phase={streamState.phase} />
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* Streaming banner — narrow indicator above composer bar */}
      {streamState.isStreaming && streamState.content === '' && (
        <div className="px-4 shrink-0">
          <StreamingBanner phase={streamState.phase} />
        </div>
      )}

      {/* Composer bar — shows when there are messages */}
      {!isEmpty && (
        <ComposerBar onClick={() => setComposerOpen(true)} isStreaming={streamState.isStreaming} />
      )}
    </div>
  );
}
