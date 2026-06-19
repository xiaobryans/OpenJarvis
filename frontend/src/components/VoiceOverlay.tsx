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
  MessageSquare,
  AlertTriangle,
} from 'lucide-react';
import { useVoiceSession, VOICE_STATE_LABEL, type VoiceState } from '../hooks/useVoiceSession';

// ---------------------------------------------------------------------------
// State → icon + colour
// ---------------------------------------------------------------------------

function StateIcon({ state }: { state: VoiceState }) {
  const cls = 'w-4 h-4';
  switch (state) {
    case 'recording':
    case 'waiting_for_silence':
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
      return <AlertTriangle className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    default:
      return <MicOff className={cls} style={{ color: 'var(--color-text-tertiary)' }} />;
  }
}

function statePulse(state: VoiceState): string {
  switch (state) {
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

function stateRing(state: VoiceState): string {
  switch (state) {
    case 'recording':
    case 'waiting_for_silence':
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
// Provider chip
// ---------------------------------------------------------------------------

function ProviderChip({ stt, tts }: { stt: string; tts: string }) {
  const same = stt === tts;
  return (
    <span
      className="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wide"
      style={{
        background: 'color-mix(in srgb, var(--color-accent) 12%, transparent)',
        color: 'var(--color-accent)',
        border: '1px solid color-mix(in srgb, var(--color-accent) 25%, transparent)',
      }}
      title={same ? `STT + TTS: ${stt}` : `STT: ${stt} · TTS: ${tts}`}
    >
      {same ? stt : `${stt}/${tts}`}
    </span>
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
  'waiting_for_silence',
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
    startFailedReason,
    providerInfo,
    wakeMode,
    wakeWorkerReady,
    wakeFailureReason,
    wakePhraseActive,
    manualTriggerAvailable,
    configuredShortcut,
    trigger,
    start,
    stop,
  } = useVoiceSession();

  const [expanded, setExpanded] = useState(false);
  const [showLatency, setShowLatency] = useState(false);
  // Whether the auto-start attempt has completed (regardless of outcome)
  const [autoStartDone, setAutoStartDone] = useState(false);
  const autoStarted = useRef(false);

  // ── 1. AUTO-START: begin wake-word listening when the app loads ──────────
  useEffect(() => {
    if (autoStarted.current) return;
    autoStarted.current = true;

    let mounted = true;

    const tryAutoStart = async () => {
      if (!mounted) return;
      await start({ silent: true });
      if (mounted) setAutoStartDone(true);
    };

    // First attempt after 1.5 s — gives backend time to be ready after Tauri launch
    const t1 = setTimeout(tryAutoStart, 1500);
    // Retry at 5 s in case the server was still starting
    const t2 = setTimeout(async () => {
      if (!mounted || isActive) return;
      await start({ silent: true });
      if (mounted) setAutoStartDone(true);
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
      const t = setTimeout(() => setExpanded(false), 8000);
      return () => clearTimeout(t);
    }
  }, [voiceState]);

  // Expand on failure so Bryan can read the exact reason
  useEffect(() => {
    if (startFailedReason && autoStartDone) setExpanded(true);
  }, [startFailedReason, autoStartDone]);

  const isRunning = isActive && voiceState !== 'idle' && voiceState !== 'stopped' && voiceState !== 'session_ended';
  const isWakeListening = isRunning && (voiceState === 'listening' || voiceState === 'wake_listening');
  const hasConversation = !!finalTranscript || !!jarvisResponse;

  // Truthful wake-listening label — never claim "Hey Jarvis" unless worker
  // is confirmed ready and in wake_word mode.
  const wakeListeningLabel = (() => {
    if (wakePhraseActive) return 'Listening for "Hey Jarvis"…';
    if (wakeMode === 'hotkey_only') return 'Wake word unavailable — tap mic to speak';
    return 'Wake word loading — tap mic to speak';
  })();

  // ── Badge label logic — never show "Voice off" when the session is active
  // or still starting. ──────────────────────────────────────────────────────
  const badgeLabel = (() => {
    if (isActive) {
      if (isWakeListening) return wakeListeningLabel;
      return VOICE_STATE_LABEL[voiceState] ?? voiceState;
    }
    if (voiceState === 'error') return 'Error';
    if (voiceState === 'stopped' || voiceState === 'session_ended') return 'Stopped';
    if (startFailedReason) return 'Voice unavailable';
    if (!autoStartDone) return 'Connecting…';
    return 'Voice off';
  })();

  const badgeDotColor = (() => {
    if (startFailedReason && !isActive) return 'var(--color-error, #ef4444)';
    if (voiceState === 'error') return 'var(--color-error, #ef4444)';
    if (isWakeListening) return 'var(--color-success, #22c55e)';
    if (isRunning) return 'var(--color-accent)';
    return 'var(--color-text-tertiary)';
  })();

  // Mic button:
  // - If listening (any wake mode) → always trigger a recording turn. The
  //   mic button is the primary reliable manual trigger regardless of whether
  //   the wake-word worker is active, loading, or unavailable.
  // - If active turn in progress (recording/transcribing/speaking) → stop.
  // - If not running → start session.
  const handleMicClick = async () => {
    if (isRunning) {
      if (isWakeListening) {
        // Always trigger — works whether wake-word is active or unavailable.
        await trigger();
        setExpanded(true);
      } else {
        // Active turn in progress → stop
        await stop();
        setExpanded(false);
      }
    } else {
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
            <div className="flex items-center gap-2 min-w-0">
              <div className={statePulse(voiceState)}>
                <StateIcon state={voiceState} />
              </div>
              <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                {isWakeListening ? wakeListeningLabel : (VOICE_STATE_LABEL[voiceState] ?? voiceState)}
              </span>
              {/* Provider chip — shown when provider info is available */}
              {providerInfo && isActive && (
                <ProviderChip stt={providerInfo.stt} tts={providerInfo.tts} />
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

          {/* Conversation body */}
          <div className="px-3 py-2 space-y-2 max-h-64 overflow-y-auto">
            {/* Error / start failure */}
            {(error || (startFailedReason && !isActive)) && (
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
                  Voice session failed
                </div>
                <div className="font-mono text-[10px] break-all">
                  {error ?? startFailedReason}
                </div>
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

            {/* Wake listening idle prompt — truthful, mic-button-first */}
            {!hasConversation && !error && !startFailedReason && !interimTranscript && isRunning && isWakeListening && (
              <div className="space-y-1">
                {wakePhraseActive ? (
                  // Wake-word confirmed active
                  <div className="text-xs text-center py-2 space-y-1">
                    <div style={{ color: 'var(--color-text-secondary)' }}>
                      Say <strong>"Hey Jarvis"</strong>
                      {configuredShortcut ? (
                        <> or press{' '}
                          <kbd className="px-1 rounded text-[10px]" style={{ background: 'var(--color-bg-tertiary)' }}>
                            {configuredShortcut}
                          </kbd>
                        </>
                      ) : (
                        ' or tap the mic'
                      )}
                    </div>
                  </div>
                ) : (
                  // Wake-word unavailable or loading — mic is the trigger
                  <div className="text-xs text-center py-2 space-y-1">
                    <div style={{ color: 'var(--color-text-secondary)' }}>
                      {configuredShortcut ? (
                        <>Press{' '}
                          <kbd className="px-1 rounded text-[10px]" style={{ background: 'var(--color-bg-tertiary)' }}>
                            {configuredShortcut}
                          </kbd>{' '}
                          or{' '}
                        </>
                      ) : null}
                      <strong>Tap the mic</strong> to speak
                    </div>
                    {wakeFailureReason && (
                      <div
                        className="text-[10px] px-2 py-1 rounded font-mono"
                        style={{
                          color: 'var(--color-text-tertiary)',
                          background: 'var(--color-bg-tertiary)',
                        }}
                      >
                        Wake-word unavailable: {wakeFailureReason.split('.')[0]}
                      </div>
                    )}
                    {!wakeFailureReason && wakeMode === 'wake_word' && !wakeWorkerReady && (
                      <div
                        className="text-[10px] px-2 py-1 rounded font-mono"
                        style={{
                          color: 'var(--color-text-tertiary)',
                          background: 'var(--color-bg-tertiary)',
                        }}
                      >
                        Wake-word model loading…
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Recording state — silence-based ending, 120s emergency cap */}
            {isRunning && voiceState === 'recording' && !interimTranscript && (
              <div
                className="text-xs text-center py-1"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Speak freely — ends on silence (max 120 s)
              </div>
            )}
            {isRunning && voiceState === 'waiting_for_silence' && (
              <div
                className="text-xs text-center py-1 animate-pulse"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Waiting for silence…
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

          {/* Text fallback — always available */}
          <div
            className="px-3 pb-2 pt-1 flex items-center justify-between"
            style={{ borderTop: '1px solid var(--color-border)' }}
          >
            <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
              {isRunning ? (
                <>Say <em>"stop"</em>, <em>"cancel"</em>, or <em>"never mind"</em> to end</>
              ) : (
                'Voice session inactive'
              )}
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
        {/* State badge — always visible */}
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
              className={`inline-block w-1.5 h-1.5 rounded-full ${isWakeListening ? 'animate-pulse' : ''}`}
              style={{ background: badgeDotColor }}
            />
            {badgeLabel}
            <ChevronUp size={10} />
          </button>
        )}

        <button
          onClick={handleMicClick}
          className={`w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-all ${stateRing(voiceState)}`}
          style={{
            background: isRunning
              ? voiceState === 'recording' || voiceState === 'waiting_for_silence'
                ? 'var(--color-error, #ef4444)'
                : 'var(--color-accent)'
              : 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            color: isRunning ? '#fff' : 'var(--color-text-secondary)',
          }}
          title={
            isRunning
              ? isWakeListening
                ? wakePhraseActive
                  ? `Say "Hey Jarvis" or click to trigger manually`
                  : 'Click to trigger recording (wake word unavailable)'
                : 'Stop voice session'
              : 'Start voice session manually'
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
