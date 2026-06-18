import { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Loader2,
  Volume2,
  Brain,
  Radio,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import { useVoiceSession, VOICE_STATE_LABEL, type VoiceState } from '../hooks/useVoiceSession';

// ---------------------------------------------------------------------------
// State → icon + colour
// ---------------------------------------------------------------------------

function StateIcon({ state }: { state: VoiceState }) {
  const cls = 'w-4 h-4';
  switch (state) {
    case 'recording':
      return <Mic className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    case 'transcribing':
    case 'thinking':
      return <Brain className={cls} style={{ color: 'var(--color-accent)' }} />;
    case 'speaking':
      return <Volume2 className={cls} style={{ color: 'var(--color-success, #22c55e)' }} />;
    case 'wake_detected':
    case 'acknowledging':
      return <Radio className={cls} style={{ color: 'var(--color-accent)' }} />;
    case 'active_conversation':
    case 'follow_up_listening':
      return <Mic className={cls} style={{ color: 'var(--color-accent)' }} />;
    case 'listening':
    case 'wake_listening':
      return <Mic className={cls} style={{ color: 'var(--color-text-secondary)' }} />;
    case 'error':
      return <MicOff className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    default:
      return <MicOff className={cls} style={{ color: 'var(--color-text-tertiary)' }} />;
  }
}

function statePulse(state: VoiceState): string {
  switch (state) {
    case 'recording':
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

function stateRing(state: VoiceState): string {
  switch (state) {
    case 'recording':
      return 'ring-2 ring-red-500/60';
    case 'thinking':
    case 'transcribing':
      return 'ring-2 ring-accent/60';
    case 'speaking':
      return 'ring-2 ring-green-500/60';
    case 'wake_detected':
    case 'acknowledging':
    case 'active_conversation':
    case 'follow_up_listening':
      return 'ring-2 ring-accent/40';
    default:
      return '';
  }
}

// ---------------------------------------------------------------------------
// Latency row
// ---------------------------------------------------------------------------

function LatencyRow({ label, ms }: { label: string; ms?: number }) {
  if (ms === undefined) return null;
  return (
    <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
      <span>{label}</span>
      <span className="font-mono">{ms.toFixed(0)} ms</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// States that mean Jarvis is actively processing (not just background-listening)
// ---------------------------------------------------------------------------

const ACTIVE_CONV_STATES: VoiceState[] = [
  'wake_detected',
  'acknowledging',
  'active_conversation',
  'recording',
  'transcribing',
  'thinking',
  'speaking',
  'follow_up_listening',
];

// ---------------------------------------------------------------------------
// Main overlay component
// ---------------------------------------------------------------------------

export function VoiceOverlay() {
  const {
    voiceState,
    interimTranscript,
    finalTranscript,
    jarvisResponse,
    latency,
    error,
    turnsCompleted,
    isActive,
    start,
    stop,
  } = useVoiceSession();

  const [expanded, setExpanded] = useState(false);
  const [showLatency, setShowLatency] = useState(false);
  const autoStarted = useRef(false);

  // ── 1. AUTO-START: begin wake-word listening when the app loads ──────────
  // This is the primary user path. The user does NOT need to click the mic
  // button. Saying "Hey Jarvis" wakes the assistant automatically.
  // Uses silent=true so a missing wake-worker venv does not flash any error.
  useEffect(() => {
    if (autoStarted.current) return;
    autoStarted.current = true;

    let mounted = true;

    const tryAutoStart = async () => {
      if (!mounted) return;
      await start({ silent: true });
    };

    // First attempt after 1.5 s — gives backend time to be ready after Tauri launch
    const t1 = setTimeout(tryAutoStart, 1500);
    // Retry at 5 s in case the server was still starting
    const t2 = setTimeout(async () => {
      if (!mounted || isActive) return;
      await start({ silent: true });
    }, 5000);

    return () => {
      mounted = false;
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 2. AUTO-EXPAND: show overlay panel when Jarvis wakes/starts a turn ──
  useEffect(() => {
    if (ACTIVE_CONV_STATES.includes(voiceState)) {
      setExpanded(true);
    }
    // Auto-collapse after session returns to background wake-listening
    if (voiceState === 'listening' || voiceState === 'wake_listening') {
      // Keep expanded briefly after session so Bryan can read the last response
      const t = setTimeout(() => setExpanded(false), 8000);
      return () => clearTimeout(t);
    }
  }, [voiceState]);

  const isRunning = isActive && voiceState !== 'idle' && voiceState !== 'stopped';
  const isWakeListening = isRunning && (voiceState === 'listening' || voiceState === 'wake_listening');
  const hasConversation = !!finalTranscript || !!jarvisResponse;

  // Mic button: stop session (if running) or manually force-start (fallback)
  const handleMicClick = async () => {
    if (isRunning) {
      await stop();
      setExpanded(false);
    } else {
      // Manual / fallback start — show UI feedback
      await start();
      setExpanded(true);
    }
  };

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2"
      role="region"
      aria-label="Jarvis voice conversation"
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
            <div className="flex items-center gap-2">
              <div className={statePulse(voiceState)}>
                <StateIcon state={voiceState} />
              </div>
              <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                {VOICE_STATE_LABEL[voiceState] ?? voiceState}
              </span>
            </div>
            <button
              onClick={() => setExpanded(false)}
              className="p-1 rounded transition-colors"
              style={{ color: 'var(--color-text-tertiary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              aria-label="Collapse voice panel"
            >
              <ChevronDown size={14} />
            </button>
          </div>

          {/* Conversation body */}
          <div className="px-3 py-2 space-y-2 max-h-64 overflow-y-auto">
            {/* Error */}
            {error && (
              <div
                className="text-xs px-2 py-1.5 rounded"
                style={{
                  background: 'color-mix(in srgb, var(--color-error, #ef4444) 10%, transparent)',
                  color: 'var(--color-error, #ef4444)',
                }}
              >
                {error}
              </div>
            )}

            {/* Interim transcript (recording / transcribing state) */}
            {interimTranscript && !finalTranscript && (
              <div
                className="text-xs italic"
                style={{ color: 'var(--color-text-secondary)' }}
                aria-live="polite"
              >
                {interimTranscript}
              </div>
            )}

            {/* Final transcript */}
            {finalTranscript && (
              <div className="space-y-0.5">
                <div
                  className="text-[10px] uppercase tracking-wide"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  You
                </div>
                <div
                  className="text-sm px-2 py-1.5 rounded-lg"
                  style={{
                    background: 'var(--color-accent-subtle)',
                    color: 'var(--color-text)',
                  }}
                  aria-live="polite"
                >
                  {finalTranscript}
                </div>
              </div>
            )}

            {/* Jarvis response */}
            {jarvisResponse && (
              <div className="space-y-0.5">
                <div
                  className="text-[10px] uppercase tracking-wide"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  Jarvis
                </div>
                <div
                  className="text-sm px-2 py-1.5 rounded-lg"
                  style={{
                    background: 'var(--color-bg-tertiary)',
                    color: 'var(--color-text)',
                  }}
                  aria-live="polite"
                >
                  {jarvisResponse}
                </div>
              </div>
            )}

            {/* Idle prompt */}
            {!hasConversation && !error && !interimTranscript && isRunning && (
              <div
                className="text-xs text-center py-2"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Say <strong>"Hey Jarvis"</strong> to start
              </div>
            )}
          </div>

          {/* Footer: turns + latency toggle */}
          {(turnsCompleted > 0 || Object.keys(latency).length > 0) && (
            <div
              className="px-3 py-1.5 space-y-1"
              style={{ borderTop: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                  Turns: {turnsCompleted}
                </span>
                <button
                  onClick={() => setShowLatency((v) => !v)}
                  className="text-[10px] flex items-center gap-0.5"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  Latency {showLatency ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                </button>
              </div>
              {showLatency && (
                <div className="space-y-0.5">
                  <LatencyRow label="Wake → ack" ms={latency.wake_to_ack_ms} />
                  <LatencyRow label="Wake → record start" ms={latency.wake_to_record_start_ms} />
                  <LatencyRow label="STT duration" ms={latency.stt_duration_ms} />
                  <LatencyRow label="Speech end → STT final" ms={latency.speech_end_to_stt_final_ms} />
                  <LatencyRow label="Model duration" ms={latency.model_duration_ms} />
                  <LatencyRow label="TTS start lag" ms={latency.tts_start_ms} />
                  <LatencyRow label="Total turn" ms={latency.total_turn_ms} />
                </div>
              )}
            </div>
          )}

          {/* Stop phrase hint */}
          {isRunning && (
            <div
              className="px-3 pb-2 text-[10px]"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              Say <em>"stop listening"</em>, <em>"cancel"</em>, or <em>"that's all"</em> to end session.
            </div>
          )}
        </div>
      )}

      {/* Mic button row — always visible */}
      <div className="flex items-center gap-2">
        {isRunning && !expanded && (
          <button
            onClick={() => setExpanded(true)}
            className="text-xs px-2 py-1 rounded-full flex items-center gap-1.5"
            style={{
              background: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            {/* Pulsing dot — visible indicator that wake mode is active */}
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${isWakeListening ? 'animate-pulse' : ''}`}
              style={{
                background: isWakeListening
                  ? 'var(--color-success, #22c55e)'
                  : 'var(--color-accent)',
              }}
            />
            {VOICE_STATE_LABEL[voiceState] ?? voiceState}
            <ChevronUp size={10} />
          </button>
        )}

        <button
          onClick={handleMicClick}
          className={`w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-all ${stateRing(voiceState)}`}
          style={{
            background: isRunning
              ? voiceState === 'recording'
                ? 'var(--color-error, #ef4444)'
                : 'var(--color-accent)'
              : 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            color: isRunning ? '#fff' : 'var(--color-text-secondary)',
          }}
          title={
            isRunning
              ? isWakeListening
                ? 'Wake listening active — say "Hey Jarvis" (click to stop)'
                : 'Stop voice session'
              : 'Manually start voice session (auto-starts on app launch)'
          }
          aria-label={isRunning ? 'Stop Jarvis voice session' : 'Start Jarvis voice session'}
        >
          {voiceState === 'thinking' || voiceState === 'transcribing' ? (
            <Loader2 size={20} className="animate-spin" />
          ) : isRunning ? (
            <Mic size={20} />
          ) : (
            <MicOff size={20} />
          )}
        </button>
      </div>
    </div>
  );
}
