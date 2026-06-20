/**
 * ChatArea — voice-first canvas for Plan 2F.
 *
 * Default: transparent canvas that lets the JarvisOrb show through.
 * Shows:
 *   • "Speak or ⌘K" hint when idle
 *   • Live voice captions (transcript + reply) at bottom while voice active
 *   • Speak / Stop buttons for voice control without requiring Cmd+K
 *   • Message history visible when Cmd+K is open (via UniversalComposer)
 * No chat list by default — messages are accessed via Cmd+K panel.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Mic, MicOff, Square, Command } from 'lucide-react';
import { useAppStore } from '../../lib/store';
import { getBase, authHeaders } from '../../lib/api';

// ---------------------------------------------------------------------------
// Live caption overlay — shows transcript + Jarvis reply at the bottom
// ---------------------------------------------------------------------------

function VoiceCaptionOverlay() {
  const { transcript, response, phase } = useAppStore((s) => s.voiceCaptionState);
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);

  const isActive = phase !== 'idle' && phase !== 'error' && phase !== 'cancelled';
  const hasCaption = isActive && (transcript || response);

  if (!hasCaption) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 flex flex-col items-center gap-2 px-6 pb-8 pointer-events-none"
      style={{ zIndex: 50 }}
    >
      {/* Phase label */}
      <div
        className="text-[10px] tracking-[0.14em] uppercase font-medium"
        style={{ color: 'var(--p2-teal)', fontFamily: 'var(--font-hud)', opacity: 0.8 }}
      >
        {phase === 'recording' ? 'Listening' :
         phase === 'waiting_for_silence' ? 'Detecting silence…' :
         phase === 'transcribing' ? 'Transcribing' :
         phase === 'thinking' ? 'Thinking' :
         phase === 'speaking' ? 'Speaking' : phase}
      </div>

      {/* Caption card */}
      <div
        className="rounded-2xl px-5 py-3.5 text-center pointer-events-auto max-w-[min(560px,90vw)]"
        style={{
          background: 'rgba(0,0,0,0.72)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        {/* Bryan's transcript */}
        {transcript && (
          <p className="text-sm mb-1" style={{ color: 'rgba(255,255,255,0.7)' }}>
            <span style={{ color: 'var(--p2-teal-dim)', fontWeight: 500 }}>You: </span>
            {transcript}
          </p>
        )}
        {/* Jarvis reply */}
        {response && (
          <p className="text-sm" style={{ color: 'rgba(255,255,255,0.95)' }}>
            <span style={{ color: 'var(--p2-teal)', fontWeight: 500 }}>Jarvis: </span>
            {response}
          </p>
        )}
      </div>

      {/* View full in Cmd+K hint */}
      <button
        className="text-[10px] pointer-events-auto cursor-pointer"
        style={{ color: 'rgba(255,255,255,0.3)' }}
        onClick={() => setComposerOpen(true)}
      >
        ⌘K to view full transcript
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Idle voice-first hint — shown when no caption and voice not active
// ---------------------------------------------------------------------------

function VoiceHint({ onOpenComposer }: { onOpenComposer: () => void }) {
  const { phase } = useAppStore((s) => s.voiceCaptionState);
  const isActive = phase !== 'idle' && phase !== 'error' && phase !== 'cancelled';
  if (isActive) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 flex items-center justify-center pb-8 gap-3 pointer-events-none"
      style={{ zIndex: 50 }}
    >
      <span
        className="text-[11px] tracking-[0.08em] pointer-events-auto"
        style={{ color: 'rgba(255,255,255,0.22)', fontFamily: 'var(--font-hud)' }}
      >
        SPEAK NATURALLY · OR
      </span>
      <button
        onClick={onOpenComposer}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs pointer-events-auto cursor-pointer transition-all"
        style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.12)',
          color: 'rgba(255,255,255,0.45)',
        }}
      >
        <Command size={11} />
        <span>⌘K</span>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Voice status / control strip — shown at bottom right for quick access
// ---------------------------------------------------------------------------

function VoiceControlStrip() {
  const { phase } = useAppStore((s) => s.voiceCaptionState);
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);
  const [wakeActive, setWakeActive] = useState(false);
  const [tapBusy, setTapBusy] = useState(false);
  const isActive = phase !== 'idle' && phase !== 'error' && phase !== 'cancelled';
  const isSpeaking = phase === 'speaking';

  // Check wake-word diagnostics once on mount
  useEffect(() => {
    fetch(`${getBase()}/v1/voice/diagnostics`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => setWakeActive(Boolean(d?.wake_phrase_active)))
      .catch(() => {});
  }, []);

  // Cancel voice turn via backend API (no Cmd+K needed)
  const handleCancel = useCallback(async () => {
    try {
      await fetch(`${getBase()}/v1/voice/turn/cancel`, {
        method: 'POST',
        headers: authHeaders(),
      });
    } catch {}
  }, []);

  // Tap to speak: start a voice turn without Cmd+K
  const handleTapSpeak = useCallback(async () => {
    if (tapBusy || isActive) return;
    setTapBusy(true);
    try {
      await fetch(`${getBase()}/v1/voice/turn/start`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: 'en' }),
      });
    } catch {}
    setTapBusy(false);
  }, [tapBusy, isActive]);

  return (
    <div
      className="fixed bottom-6 right-6 flex flex-col items-end gap-2"
      style={{ zIndex: 60, pointerEvents: 'none' }}
    >
      {/* Stop button during speaking — calls backend cancel, no Cmd+K needed */}
      {isSpeaking && (
        <button
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all"
          style={{
            background: 'rgba(244,63,94,0.15)',
            border: '1px solid rgba(244,63,94,0.4)',
            color: 'rgba(244,63,94,0.9)',
            backdropFilter: 'blur(12px)',
            pointerEvents: 'auto',
          }}
          onClick={handleCancel}
          title="Stop Jarvis speaking"
        >
          <Square size={13} />
          Stop speaking
        </button>
      )}

      {/* Tap to speak — visible when idle and no wake word */}
      {!isActive && !wakeActive && (
        <button
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all"
          style={{
            background: tapBusy ? 'rgba(34,211,238,0.2)' : 'rgba(34,211,238,0.1)',
            border: '1px solid rgba(34,211,238,0.3)',
            color: 'rgba(34,211,238,0.85)',
            backdropFilter: 'blur(12px)',
            pointerEvents: 'auto',
            opacity: tapBusy ? 0.6 : 1,
          }}
          onClick={handleTapSpeak}
          title="Tap to speak — start voice turn"
          disabled={tapBusy}
        >
          <Mic size={13} />
          {tapBusy ? 'Starting…' : 'Tap to speak'}
        </button>
      )}

      {/* Active mic status indicator */}
      {isActive && (
        <button
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs cursor-pointer transition-all"
          style={{
            background: 'rgba(34,211,238,0.12)',
            border: '1px solid rgba(34,211,238,0.3)',
            color: 'var(--p2-teal)',
            backdropFilter: 'blur(12px)',
            pointerEvents: 'auto',
          }}
          onClick={() => setComposerOpen(true)}
          title="Open ⌘K voice controls"
        >
          <Mic size={12} />
          <span style={{ fontFamily: 'var(--font-hud)', letterSpacing: '0.04em' }}>
            {phase === 'recording' ? 'listening' :
             phase === 'waiting_for_silence' ? 'endpointing' :
             phase === 'transcribing' ? 'transcribing' :
             phase === 'thinking' ? 'thinking' :
             phase === 'speaking' ? 'speaking' : phase}
          </span>
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component — intentionally minimal, lets orb show through
// ---------------------------------------------------------------------------

export function ChatArea() {
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);
  const messages = useAppStore((s) => s.messages);
  const latestRef = useRef<HTMLDivElement>(null);

  // Auto-open composer briefly when there are new messages to acknowledge
  // (voice turns push messages; user may want to review them)
  const prevMsgCount = useRef(messages.length);
  useEffect(() => {
    prevMsgCount.current = messages.length;
  }, [messages.length]);

  const openComposer = () => setComposerOpen(true);

  return (
    <>
      {/* Transparent canvas — orb from Layout shows through */}
      <div
        className="flex flex-col h-full"
        style={{ background: 'transparent', position: 'relative' }}
      >
        {/* Latest message peek — compact, shown when there's conversation history */}
        {messages.length > 0 && (
          <div
            ref={latestRef}
            className="absolute top-4 left-1/2 -translate-x-1/2 max-w-[min(480px,88vw)] w-full px-4"
            style={{ zIndex: 10 }}
          >
            <button
              onClick={openComposer}
              className="w-full text-left px-4 py-3 rounded-xl text-xs cursor-pointer transition-all"
              style={{
                background: 'rgba(0,0,0,0.55)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.65)',
              }}
            >
              <span style={{ color: 'rgba(255,255,255,0.35)', marginRight: 8 }}>
                {messages.length} message{messages.length !== 1 ? 's' : ''} ·
              </span>
              {(() => {
                const last = messages[messages.length - 1];
                const preview = last?.content?.slice(0, 80) ?? '';
                return preview.length < last?.content?.length ? preview + '…' : preview;
              })()}
              <span style={{ color: 'var(--p2-teal)', marginLeft: 8, opacity: 0.7 }}>⌘K to view</span>
            </button>
          </div>
        )}
      </div>

      {/* Live voice captions — bottom subtitle overlay */}
      <VoiceCaptionOverlay />

      {/* Idle hint — "speak naturally or ⌘K" */}
      <VoiceHint onOpenComposer={openComposer} />

      {/* Voice status strip — bottom right */}
      <VoiceControlStrip />
    </>
  );
}
