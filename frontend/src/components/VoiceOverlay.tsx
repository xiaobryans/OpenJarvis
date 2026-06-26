/**
 * VoiceOverlay — manual-command-first voice UI.
 *
 * Uses the new deterministic VoiceTurnEngine (useVoiceTurn hook).
 * No wake-word for commands. No background recording. No session loop.
 *
 * States shown:
 *   Voice off          → mic button shows MicOff
 *   idle (enabled)     → "Ready — press Speak now"
 *   recording          → "Recording" + pulse + End & send + Cancel
 *   waiting_for_silence→ "Waiting for silence" + pulse + End & send + Cancel
 *   transcribing       → "Transcribing" + spinner
 *   thinking           → "Thinking" + spinner
 *   speaking           → "Speaking" + bounce
 *   error              → "Error" + reason
 *   cancelled          → "Cancelled"
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Mic,
  MicOff,
  Loader2,
  Volume2,
  Brain,
  ChevronUp,
  ChevronDown,
  MessageSquare,
  AlertTriangle,
  Play,
  X,
  Square,
} from 'lucide-react';
import { useVoiceTurn, type TurnPhase } from '../hooks/useVoiceTurn';

// ---------------------------------------------------------------------------
// State → label
// ---------------------------------------------------------------------------

const TURN_LABEL: Record<TurnPhase, string> = {
  idle: 'Ready — press Speak now',
  recording: 'Recording',
  waiting_for_silence: 'Waiting for silence',
  follow_up_listening: 'Listening for follow-up…',
  transcribing: 'Transcribing',
  thinking: 'Thinking',
  speaking: 'Speaking',
  error: 'Error',
  cancelled: 'Cancelled',
};

// ---------------------------------------------------------------------------
// StateIcon
// ---------------------------------------------------------------------------

function StateIcon({ phase, enabled }: { phase: TurnPhase; enabled: boolean }) {
  const cls = 'w-4 h-4';
  if (!enabled) return <MicOff className={cls} style={{ color: 'var(--color-text-tertiary)' }} />;
  switch (phase) {
    case 'recording':
    case 'waiting_for_silence':
      return <Mic className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    case 'transcribing':
    case 'thinking':
      return <Brain className={cls} style={{ color: 'var(--color-accent)' }} />;
    case 'speaking':
      return <Volume2 className={cls} style={{ color: 'var(--color-success, #22c55e)' }} />;
    case 'error':
      return <AlertTriangle className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    default:
      return <Mic className={cls} style={{ color: 'var(--color-text-secondary)' }} />;
  }
}

function statePulse(phase: TurnPhase): string {
  switch (phase) {
    case 'recording':
    case 'waiting_for_silence':
      return 'animate-pulse';
    case 'transcribing':
    case 'thinking':
      return 'animate-spin';
    case 'speaking':
      return 'animate-bounce';
    default:
      return '';
  }
}

// ---------------------------------------------------------------------------
// DiagRow
// ---------------------------------------------------------------------------

function DiagRow({ label, value }: { label: string; value?: string | number }) {
  if (value == null) return null;
  return (
    <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
      <span>{label}</span>
      <span className="font-mono">{typeof value === 'number' ? value.toFixed(1) : value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Active-turn phases
// ---------------------------------------------------------------------------

const ACTIVE_PHASES: TurnPhase[] = [
  'recording',
  'waiting_for_silence',
  'transcribing',
  'thinking',
  'speaking',
];

// ---------------------------------------------------------------------------
// VoiceOverlay
// ---------------------------------------------------------------------------

export function VoiceOverlay() {
  const {
    voiceEnabled,
    phase,
    transcript,
    response,
    lastError,
    lastVad,
    routeInfo,
    enableVoice,
    disableVoice,
    startTurn,
    cancelTurn,
    endRecordingNow,
  } = useVoiceTurn();

  const [expanded, setExpanded] = useState(false);
  const [showDiag, setShowDiag] = useState(false);

  // Auto-expand when a turn becomes active
  useEffect(() => {
    if (ACTIVE_PHASES.includes(phase)) {
      setExpanded(true);
    }
    // Auto-collapse 30 s after returning to idle (turn complete)
    if (phase === 'idle' && voiceEnabled) {
      const t = setTimeout(() => setExpanded(false), 30_000);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [phase, voiceEnabled]);

  // Auto-expand on error
  useEffect(() => {
    if (phase === 'error') setExpanded(true);
  }, [phase]);

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  const handleMicClick = useCallback(async () => {
    if (voiceEnabled) {
      await disableVoice();
      setExpanded(false);
    } else {
      enableVoice();
      setExpanded(true);
    }
  }, [voiceEnabled, enableVoice, disableVoice]);

  const handleSpeakNow = useCallback(async () => {
    const result = await startTurn();
    if (result.ok) setExpanded(true);
  }, [startTurn]);

  const handleEndRecording = useCallback(() => {
    endRecordingNow();
  }, [endRecordingNow]);

  const handleCancel = useCallback(() => {
    cancelTurn();
  }, [cancelTurn]);

  // ------------------------------------------------------------------
  // Derived display
  // ------------------------------------------------------------------

  const isActiveTurn = ACTIVE_PHASES.includes(phase);
  const isRecording = phase === 'recording' || phase === 'waiting_for_silence';

  const badgeLabel = (() => {
    if (!voiceEnabled) return 'Voice off';
    if (phase === 'idle') return 'Ready — press Speak now';
    return TURN_LABEL[phase] ?? phase;
  })();

  const badgeDotColor = (() => {
    if (!voiceEnabled) return 'var(--color-text-tertiary)';
    if (phase === 'error') return 'var(--color-error, #ef4444)';
    if (phase === 'recording' || phase === 'waiting_for_silence') return 'var(--color-error, #ef4444)';
    if (phase === 'speaking') return 'var(--color-success, #22c55e)';
    if (isActiveTurn) return 'var(--color-accent)';
    return 'var(--color-success, #22c55e)';
  })();

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2"
      role="region"
      aria-label="VANTA voice"
    >
      {/* Expanded conversation panel */}
      {expanded && (
        <div
          className="w-80 rounded-xl shadow-2xl overflow-hidden"
          style={{
            background: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-3 py-2"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className={voiceEnabled ? statePulse(phase) : ''}>
                <StateIcon phase={phase} enabled={voiceEnabled} />
              </div>
              <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                {!voiceEnabled ? 'Voice off' : TURN_LABEL[phase] ?? phase}
              </span>
              {routeInfo && (
                <span
                  className="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wide shrink-0"
                  style={{
                    background: 'color-mix(in srgb, var(--color-accent) 12%, transparent)',
                    color: 'var(--color-accent)',
                    border: '1px solid color-mix(in srgb, var(--color-accent) 25%, transparent)',
                  }}
                  title={`Provider: ${routeInfo.provider ?? '?'} · Model: ${routeInfo.model ?? '?'} · Tier: ${routeInfo.tier ?? '?'}`}
                >
                  {routeInfo.provider ?? 'ai'}
                </span>
              )}
            </div>
            <button
              onClick={() => setExpanded(false)}
              className="p-1 rounded transition-colors shrink-0"
              style={{ color: 'var(--color-text-tertiary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              aria-label="Collapse voice panel"
            >
              <ChevronDown size={14} />
            </button>
          </div>

          {/* Body */}
          <div className="px-3 py-2 space-y-2 max-h-64 overflow-y-auto">
            {/* Error */}
            {phase === 'error' && lastError && (
              <div
                className="text-xs px-2 py-2 rounded space-y-1"
                style={{
                  background: 'color-mix(in srgb, var(--color-error, #ef4444) 10%, transparent)',
                  color: 'var(--color-error, #ef4444)',
                  border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 25%, transparent)',
                }}
              >
                <div className="font-medium flex items-center gap-1">
                  <AlertTriangle size={11} />
                  Turn failed
                </div>
                <div className="font-mono text-[10px] break-all">{lastError}</div>
              </div>
            )}

            {/* Transcript */}
            {transcript && (
              <div className="space-y-0.5">
                <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                  You
                </div>
                <div
                  className="text-sm px-2 py-1.5 rounded-lg"
                  style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-text)' }}
                  aria-live="polite"
                >
                  {transcript}
                </div>
              </div>
            )}

            {/* Jarvis response */}
            {response && (
              <div className="space-y-0.5">
                <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>VANTA</div>
                <div
                  className="text-sm px-2 py-1.5 rounded-lg"
                  style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text)' }}
                  aria-live="polite"
                >
                  {response}
                </div>
              </div>
            )}

            {/* "Speak now" — shown when voice is enabled and idle */}
            {voiceEnabled && phase === 'idle' && (
              <button
                onClick={handleSpeakNow}
                className="w-full py-2.5 rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition-opacity hover:opacity-90 active:opacity-75"
                style={{ background: 'var(--color-success, #22c55e)', color: '#fff' }}
                title="Start one recording turn (manual-command-first)"
                aria-label="Start voice command — speak after clicking"
              >
                <Play size={15} />
                Speak now
              </button>
            )}

            {/* Recording hint */}
            {phase === 'recording' && (
              <div className="text-xs text-center py-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                Recording — ends automatically on silence
              </div>
            )}
            {phase === 'waiting_for_silence' && (
              <div className="text-xs text-center py-0.5 animate-pulse" style={{ color: 'var(--color-text-secondary)' }}>
                Silence detected — endpointing…
              </div>
            )}

            {/* "End & send" + "Cancel" during recording */}
            {isRecording && (
              <div className="flex gap-2">
                <button
                  onClick={handleEndRecording}
                  className="flex-1 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-opacity hover:opacity-90"
                  style={{
                    background: 'color-mix(in srgb, var(--color-accent) 15%, transparent)',
                    color: 'var(--color-accent)',
                    border: '1px solid color-mix(in srgb, var(--color-accent) 30%, transparent)',
                  }}
                  title="Force-end recording and send audio to STT now"
                  aria-label="End recording and send"
                >
                  <Square size={11} />
                  End &amp; send
                </button>
                <button
                  onClick={handleCancel}
                  className="px-3 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-1 transition-opacity hover:opacity-90"
                  style={{
                    background: 'color-mix(in srgb, var(--color-error, #ef4444) 10%, transparent)',
                    color: 'var(--color-error, #ef4444)',
                    border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 25%, transparent)',
                  }}
                  title="Discard current recording"
                  aria-label="Cancel and discard"
                >
                  <X size={11} />
                  Cancel
                </button>
              </div>
            )}

            {/* Cancel during STT/thinking/speaking */}
            {isActiveTurn && !isRecording && (
              <button
                onClick={handleCancel}
                className="w-full py-1.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-opacity hover:opacity-90"
                style={{
                  background: 'color-mix(in srgb, var(--color-error, #ef4444) 8%, transparent)',
                  color: 'var(--color-error, #ef4444)',
                  border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 20%, transparent)',
                }}
                title="Cancel current turn"
                aria-label="Cancel current turn"
              >
                <X size={11} />
                Cancel
              </button>
            )}
          </div>

          {/* Footer: diagnostics */}
          {lastVad && (
            <div className="px-3 py-1.5" style={{ borderTop: '1px solid var(--color-border)' }}>
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                  VAD diagnostics
                </span>
                <button
                  onClick={() => setShowDiag((v) => !v)}
                  className="text-[10px] flex items-center gap-0.5"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  {showDiag ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                </button>
              </div>
              {showDiag && (
                <div className="mt-1 space-y-0.5">
                  <DiagRow label="Stop reason" value={lastVad.stop_reason} />
                  <DiagRow label="Duration (s)" value={lastVad.duration_s} />
                  <DiagRow label="Silence window (ms)" value={lastVad.silence_stop_ms} />
                  <DiagRow label="Noise floor RMS" value={lastVad.noise_floor_rms} />
                  <DiagRow label="Effective threshold" value={lastVad.effective_threshold} />
                </div>
              )}
            </div>
          )}

          {/* Footer: text fallback */}
          <div
            className="px-3 pb-2 pt-1 flex items-center justify-between"
            style={{ borderTop: '1px solid var(--color-border)' }}
          >
            <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
              {voiceEnabled ? 'Click mic to turn off' : 'Click mic to enable voice'}
            </span>
            <a
              href="/"
              className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded transition-colors"
              style={{ color: 'var(--color-accent)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              title="Use text chat instead of voice"
            >
              <MessageSquare size={10} />
              Text mode
            </a>
          </div>
        </div>
      )}

      {/* Mic button row — always visible */}
      <div className="flex items-center gap-2">
        {!expanded && (
          <button
            onClick={() => setExpanded(true)}
            className="text-xs px-2 py-1 rounded-full flex items-center gap-1.5"
            style={{
              background: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${phase === 'recording' || phase === 'waiting_for_silence' ? 'animate-pulse' : ''}`}
              style={{ background: badgeDotColor }}
            />
            {badgeLabel}
            <ChevronUp size={10} />
          </button>
        )}

        <button
          onClick={handleMicClick}
          className="w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-all"
          style={{
            background: voiceEnabled ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            color: voiceEnabled ? '#fff' : 'var(--color-text-secondary)',
          }}
          title={voiceEnabled ? 'Turn off voice' : 'Turn on voice'}
          aria-label={voiceEnabled ? 'Turn off VANTA voice' : 'Turn on VANTA voice'}
        >
          {voiceEnabled ? <Mic size={20} /> : <MicOff size={20} />}
        </button>
      </div>
    </div>
  );
}
