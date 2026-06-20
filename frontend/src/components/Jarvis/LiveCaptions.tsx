/**
 * LiveCaptions — Tier 5. Current-turn live transcript + Jarvis reply caption.
 *
 * Hard contract:
 *   - User caption is the CURRENT TURN transcript only. No conversation
 *     history. The pre-Plan-2 useVoiceTurn already resets transcript at
 *     the start of each turn, so this just renders state.transcript.
 *   - Jarvis caption is the current TTS response text. Visible while
 *     phase === 'speaking' and lingers briefly after.
 *   - Empty state when voice off or idle with no transcript/response yet:
 *     small hint instead of fake content.
 */

import type { TurnPhase } from '../../hooks/useVoiceTurn';

interface Props {
  phase: TurnPhase;
  voiceEnabled: boolean;
  transcript: string;
  response: string;
  lastError: string | null;
}

export function LiveCaptions({
  phase,
  voiceEnabled,
  transcript,
  response,
  lastError,
}: Props) {
  const showError = phase === 'error' && lastError;

  return (
    <div
      className="w-full max-w-2xl mx-auto px-6 py-4 flex flex-col items-center gap-3"
      style={{ minHeight: 120 }}
    >
      {showError && (
        <div
          className="px-4 py-2 rounded-lg text-sm"
          style={{
            background: 'rgba(220, 90, 90, 0.10)',
            border: '1px solid rgba(220, 90, 90, 0.25)',
            color: 'rgba(255, 200, 200, 0.95)',
            maxWidth: '100%',
          }}
        >
          Voice error: {lastError}
        </div>
      )}

      {transcript && (
        <div
          aria-live="polite"
          className="text-center"
          style={{
            fontSize: 19,
            fontWeight: 500,
            lineHeight: 1.4,
            color: 'rgba(220, 235, 255, 0.92)',
            textShadow: '0 0 12px rgba(80, 140, 230, 0.35)',
            maxWidth: '100%',
          }}
        >
          {transcript}
        </div>
      )}

      {response && (
        <div
          aria-live="polite"
          className="text-center"
          style={{
            fontSize: 17,
            fontWeight: 400,
            lineHeight: 1.45,
            color: 'rgba(180, 230, 215, 0.92)',
            textShadow: '0 0 10px rgba(60, 200, 170, 0.30)',
            maxWidth: '100%',
          }}
        >
          {response}
        </div>
      )}

      {!transcript && !response && !showError && (
        <div
          className="text-center"
          style={{
            fontSize: 13,
            letterSpacing: '0.04em',
            color: 'rgba(160, 180, 220, 0.45)',
          }}
        >
          {!voiceEnabled
            ? 'Voice off — tap the mic below to enable Jarvis'
            : phase === 'idle'
              ? 'Tap mic to speak · ⌘K for transcript & text'
              : ''}
        </div>
      )}
    </div>
  );
}

export default LiveCaptions;
