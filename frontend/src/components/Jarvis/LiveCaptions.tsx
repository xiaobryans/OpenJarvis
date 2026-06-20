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
 *   - Follow-up state: "Listening for follow-up…" during follow_up_listening.
 *   - Mic diagnostic hint shown when mic_diag.too_quiet is true.
 */

import type { MicDiag, TurnPhase } from '../../hooks/useVoiceTurn';

interface Props {
  phase: TurnPhase;
  voiceEnabled: boolean;
  transcript: string;
  partialTranscript: string;
  response: string;
  lastError: string | null;
  micDiag?: MicDiag | null;
}

const RECORDING_PHASES: TurnPhase[] = ['recording', 'waiting_for_silence'];

export function LiveCaptions({
  phase,
  voiceEnabled,
  transcript,
  partialTranscript,
  response,
  lastError,
  micDiag,
}: Props) {
  const showError = phase === 'error' && lastError;
  const isRecording = RECORDING_PHASES.includes(phase);
  const isFollowUp = phase === 'follow_up_listening';

  // Determine what text to show in the user caption area.
  // Priority: final transcript > partial (while recording or follow-up) > nothing
  const userText = transcript || ((isRecording || isFollowUp) ? partialTranscript : '');
  const isPartial = !transcript && !!partialTranscript && (isRecording || isFollowUp);

  const hintText = (() => {
    if (!voiceEnabled) return 'Voice off — tap the mic below to enable Jarvis';
    if (phase === 'idle') return 'Tap mic to speak · ⌘K for transcript & text';
    if (phase === 'recording' || phase === 'waiting_for_silence') return 'Listening…';
    if (phase === 'follow_up_listening') return 'Listening for follow-up…';
    return '';
  })();

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

      {micDiag?.too_quiet && (
        <div
          className="px-3 py-1.5 rounded-lg text-xs"
          style={{
            background: 'rgba(255, 180, 60, 0.08)',
            border: '1px solid rgba(255, 180, 60, 0.22)',
            color: 'rgba(255, 210, 120, 0.90)',
          }}
        >
          {micDiag.hint ?? 'Mic too quiet — try speaking louder or closer to the MacBook'}
        </div>
      )}

      {userText && (
        <div
          aria-live="polite"
          className="text-center"
          style={{
            fontSize: 19,
            fontWeight: 500,
            lineHeight: 1.4,
            color: isPartial
              ? 'rgba(200, 220, 255, 0.75)'
              : 'rgba(220, 235, 255, 0.92)',
            textShadow: isPartial
              ? '0 0 8px rgba(80, 140, 230, 0.20)'
              : '0 0 12px rgba(80, 140, 230, 0.35)',
            maxWidth: '100%',
            transition: 'color 200ms ease, opacity 150ms ease',
            fontStyle: isPartial ? 'italic' : 'normal',
          }}
        >
          {userText}
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

      {!userText && !response && !showError && hintText && (
        <div
          className="text-center"
          style={{
            fontSize: 13,
            letterSpacing: '0.04em',
            color: isFollowUp
              ? 'rgba(140, 200, 255, 0.60)'
              : 'rgba(160, 180, 220, 0.45)',
          }}
        >
          {hintText}
        </div>
      )}
    </div>
  );
}

export default LiveCaptions;
