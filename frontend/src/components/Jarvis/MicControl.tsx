/**
 * MicControl — Tier 3 bottom tap-to-speak control.
 *
 * Single source-of-truth voice path: the canonical pre-Plan-2 useVoiceTurn
 * hook (`/v1/voice/turn/*` SSE). Cmd+K parity comes for free because both
 * call the same backend endpoints and listen to the same SSE stream.
 *
 * Click contract:
 *   voice off           → enable voice + start turn (one tap = ready to speak)
 *   idle (enabled)      → start turn
 *   recording           → end_recording (force-finalize)
 *   waiting_for_silence → end_recording (force-finalize)
 *   follow_up_listening → end_recording (submit follow-up early) or cancel
 *   transcribing        → cancel
 *   thinking            → cancel
 *   speaking            → cancel (kills TTS)
 *   error / cancelled   → start turn (retry)
 */

import { useCallback } from 'react';
import { Mic, MicOff, Square, X, Loader2 } from 'lucide-react';
import type { TurnPhase } from '../../hooks/useVoiceTurn';

interface Props {
  phase: TurnPhase;
  voiceEnabled: boolean;
  onEnable: () => void;
  onDisable: () => Promise<void> | void;
  onStartTurn: () => Promise<{ ok: boolean; error?: string }>;
  onEndRecording: () => Promise<boolean>;
  onCancel: () => Promise<void>;
}

function micLabel(phase: TurnPhase, enabled: boolean): string {
  if (!enabled) return 'Tap to enable voice';
  switch (phase) {
    case 'recording':
      return 'Recording — tap to finalize';
    case 'waiting_for_silence':
      return 'Silence detected — tap to finalize';
    case 'follow_up_listening':
      return 'Follow-up — tap to finalize or cancel';
    case 'transcribing':
      return 'Transcribing — tap to cancel';
    case 'thinking':
      return 'Thinking — tap to cancel';
    case 'speaking':
      return 'Speaking — tap to stop';
    case 'error':
      return 'Error — tap to retry';
    case 'cancelled':
      return 'Cancelled — tap to speak again';
    case 'idle':
    default:
      return 'Tap to speak';
  }
}

function micColor(phase: TurnPhase, enabled: boolean): string {
  if (!enabled) return 'rgba(120, 140, 180, 0.70)';
  switch (phase) {
    case 'recording':
    case 'waiting_for_silence':
      return 'rgba(255, 110, 100, 0.95)';
    case 'follow_up_listening':
      return 'rgba(255, 160, 80, 0.90)';
    case 'transcribing':
    case 'thinking':
      return 'rgba(160, 140, 255, 0.95)';
    case 'speaking':
      return 'rgba(110, 230, 200, 0.95)';
    case 'error':
      return 'rgba(220, 90, 90, 0.95)';
    default:
      return 'rgba(140, 190, 255, 0.95)';
  }
}

export function MicControl({
  phase,
  voiceEnabled,
  onEnable,
  onStartTurn,
  onEndRecording,
  onCancel,
}: Props) {
  const handleClick = useCallback(async () => {
    if (!voiceEnabled) {
      onEnable();
      // Give SSE a moment to attach before starting the turn. The backend
      // accepts start without SSE, but the UI feels better with the event
      // stream live.
      setTimeout(() => {
        void onStartTurn();
      }, 120);
      return;
    }
    if (phase === 'recording' || phase === 'waiting_for_silence') {
      await onEndRecording();
      return;
    }
    if (phase === 'follow_up_listening') {
      // Tap during follow-up: submit current audio early if any was captured,
      // otherwise cancel the follow-up and end the conversation.
      await onEndRecording();
      return;
    }
    if (
      phase === 'transcribing' ||
      phase === 'thinking' ||
      phase === 'speaking'
    ) {
      await onCancel();
      return;
    }
    // idle, error, cancelled → start a new turn
    await onStartTurn();
  }, [
    voiceEnabled,
    phase,
    onEnable,
    onStartTurn,
    onEndRecording,
    onCancel,
  ]);

  const color = micColor(phase, voiceEnabled);
  const label = micLabel(phase, voiceEnabled);
  const isActiveListening =
    voiceEnabled &&
    (phase === 'recording' || phase === 'waiting_for_silence' || phase === 'follow_up_listening');
  const isProcessing =
    voiceEnabled &&
    (phase === 'transcribing' || phase === 'thinking' || phase === 'speaking');

  const Icon = (() => {
    if (!voiceEnabled) return MicOff;
    if (isActiveListening) return Square;
    if (isProcessing) return X;
    return Mic;
  })();

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={handleClick}
        className={`relative rounded-full flex items-center justify-center transition-all duration-200 ${
          isActiveListening ? 'mic-ring-listening' : ''
        }`}
        style={{
          width: 76,
          height: 76,
          background: `radial-gradient(circle at 35% 30%, ${color} 0%, rgba(20, 30, 50, 0.95) 90%)`,
          border: `1px solid ${color}`,
          boxShadow: `0 0 32px ${color}, inset 0 0 18px rgba(255,255,255,0.06)`,
          color: '#ffffff',
        }}
        aria-label={label}
        title={label}
      >
        {isProcessing && phase !== 'speaking' ? (
          <Loader2 size={26} className="animate-spin" />
        ) : (
          <Icon size={26} />
        )}
      </button>
      <div
        className="text-[12px] tracking-wide"
        style={{
          color: 'rgba(180, 200, 230, 0.65)',
          textShadow: '0 0 8px rgba(0,0,0,0.5)',
        }}
      >
        {label}
      </div>
    </div>
  );
}

export default MicControl;
