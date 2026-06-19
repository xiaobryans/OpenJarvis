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
  Play,
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
    configuredShortcut,
    lastVadEvent,
    lastTriggerSource,
    trigger,
    endRecording,
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
    // Auto-collapse 30 s after returning to background wake-listening —
    // 8 s was too short; a turn ending would collapse the panel before
    // the user had a chance to read the response or say something again.
    if (voiceState === 'listening' || voiceState === 'wake_listening') {
      const t = setTimeout(() => setExpanded(false), 30000);
      return () => clearTimeout(t);
    }
  }, [voiceState]);

  // Expand on failure so Bryan can read the exact reason
  useEffect(() => {
    if (startFailedReason && autoStartDone) setExpanded(true);
  }, [startFailedReason, autoStartDone]);

  // session_ended is a brief transitional state between one turn ending and
  // returning to wake-listening. Do NOT exclude it from isRunning — doing so
  // causes a visible "stopped → listening" bounce every time a turn completes.
  const isRunning = isActive && voiceState !== 'idle' && voiceState !== 'stopped';
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

  // Mic button = voice system ON / OFF only.
  // It does NOT trigger a command recording turn — use "Speak now" for that.
  const handleMicClick = async () => {
    if (isActive) {
      await stop();
      setExpanded(false);
    } else {
      await start();
      setExpanded(true);
    }
  };

  // "Speak now" / manual command trigger — calls /v1/voice/session/trigger.
  // Works when wake-word is unavailable, unreliable, or simply not wanted.
  const handleSpeakNow = async () => {
    await trigger();
    setExpanded(true);
  };

  // "End & send" — force-stop active VAD recording and submit captured audio.
  // Use when silence detection hasn't fired (noisy room, soft speaker).
  const handleEndRecording = async () => {
    await endRecording();
  };

  const isRecordingActive = isActive && (voiceState === 'recording' || voiceState === 'waiting_for_silence');

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

            {/* "Speak now" manual trigger button — always visible when listening.
                This is the primary reliable command trigger for daily-driver use.
                Separate from the mic enable/disable button. */}
            {isActive && isWakeListening && (
              <div className="pt-1 pb-0.5 space-y-2">
                <button
                  onClick={handleSpeakNow}
                  className="w-full py-2.5 rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition-opacity hover:opacity-90 active:opacity-75"
                  style={{
                    background: 'var(--color-success, #22c55e)',
                    color: '#fff',
                  }}
                  title="Start one command recording turn (uses VAD silence endpointing)"
                  aria-label="Start voice command — speak after clicking"
                >
                  <Play size={15} />
                  Speak now
                </button>

                {/* Wake-phrase hint below the button */}
                {wakePhraseActive ? (
                  <div className="text-[11px] text-center" style={{ color: 'var(--color-text-tertiary)' }}>
                    Or say <strong>"Hey Jarvis"</strong>
                    {configuredShortcut ? <> or <kbd className="px-1 rounded text-[10px]" style={{ background: 'var(--color-bg-tertiary)' }}>{configuredShortcut}</kbd></> : null}
                  </div>
                ) : (
                  <div className="text-[11px] text-center space-y-0.5">
                    {wakeFailureReason && (
                      <div className="font-mono" style={{ color: 'var(--color-text-tertiary)' }}>
                        Wake-word unavailable: {wakeFailureReason.split('.')[0]}
                      </div>
                    )}
                    {!wakeFailureReason && wakeMode === 'wake_word' && !wakeWorkerReady && (
                      <div style={{ color: 'var(--color-text-tertiary)' }}>
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
                Recording — ends automatically on silence
              </div>
            )}
            {isRunning && voiceState === 'waiting_for_silence' && (
              <div
                className="text-xs text-center py-1 animate-pulse"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Silence detected — endpointing…
              </div>
            )}

            {/* "End & send" rescue button — visible during recording/waiting_for_silence.
                Submits captured audio immediately when VAD hasn't fired.
                Use in noisy rooms or when speaking softly. */}
            {isRecordingActive && (
              <button
                onClick={handleEndRecording}
                className="w-full py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-opacity hover:opacity-90"
                style={{
                  background: 'color-mix(in srgb, var(--color-accent) 15%, transparent)',
                  color: 'var(--color-accent)',
                  border: '1px solid color-mix(in srgb, var(--color-accent) 30%, transparent)',
                }}
                title="Force-end recording and submit audio to STT now"
                aria-label="End recording and send to Jarvis"
              >
                End &amp; send
              </button>
            )}
          </div>

          {/* Footer: turns + VAD diagnostics + latency toggle */}
          {(turnsCompleted > 0 || Object.keys(latency).length > 0 || lastVadEvent) && (
            <div
              className="px-3 py-1.5 space-y-1"
              style={{ borderTop: '1px solid var(--color-border)' }}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                  Turns: {turnsCompleted}
                  {lastTriggerSource && (
                    <> · trigger: {lastTriggerSource}</>
                  )}
                </span>
                <button
                  onClick={() => setShowLatency((v) => !v)}
                  className="text-[10px] flex items-center gap-0.5"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  Diag {showLatency ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                </button>
              </div>
              {showLatency && (
                <div className="space-y-0.5">
                  {lastVadEvent && (
                    <>
                      <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                        <span>VAD stop reason</span>
                        <span className="font-mono">{lastVadEvent.stop_reason}</span>
                      </div>
                      <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                        <span>Recording duration</span>
                        <span className="font-mono">{lastVadEvent.duration_s.toFixed(1)} s</span>
                      </div>
                      <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                        <span>Silence window</span>
                        <span className="font-mono">{lastVadEvent.silence_stop_ms} ms</span>
                      </div>
                      {lastVadEvent.noise_floor_rms != null && (
                        <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                          <span>Noise floor RMS</span>
                          <span className="font-mono">{lastVadEvent.noise_floor_rms.toFixed(1)}</span>
                        </div>
                      )}
                      {lastVadEvent.effective_threshold != null && (
                        <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                          <span>Effective threshold</span>
                          <span className="font-mono">{lastVadEvent.effective_threshold.toFixed(1)}</span>
                        </div>
                      )}
                    </>
                  )}
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
              {isActive ? (
                <>Say <em>"stop"</em> or click mic to turn off</>
              ) : (
                'Voice off — click mic to enable'
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
          className="w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-all"
          style={{
            background: isActive ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            color: isActive ? '#fff' : 'var(--color-text-secondary)',
          }}
          title={isActive ? 'Turn off voice system' : 'Turn on voice system'}
          aria-label={isActive ? 'Turn off Jarvis voice' : 'Turn on Jarvis voice'}
        >
          {isActive ? (
            <Mic size={20} />
          ) : (
            <MicOff size={20} />
          )}
        </button>
      </div>
    </div>
  );
}
