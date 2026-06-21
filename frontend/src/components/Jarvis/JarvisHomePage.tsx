/**
 * JarvisHomePage — voice-first Jarvis OS home view.
 *
 * Clean Plan 2 rebuild on top of pre-Plan-2 canonical voice path.
 *
 * Tier 1 — central living orb (state-aware)
 * Tier 2 — dark premium cosmic backdrop
 * Tier 3 — bottom tap-to-speak mic control (canonical /v1/voice/turn/*)
 * Tier 4 — agent/status ring around the orb (honest empty state)
 * Tier 5 — live current-turn captions + Jarvis reply caption
 *
 * Cmd+K opens the existing CommandPalette for transcript/chat fallback +
 * text input. Wake word is intentionally NOT wired here — held until the
 * canonical voice path is proven in packaged app.
 *
 * The page does NOT render the floating VoiceOverlay (it would duplicate
 * with the bottom mic). VoiceOverlay still mounts on other pages via App.
 */

import { useEffect } from 'react';
import { useVoiceTurn } from '../../hooks/useVoiceTurn';
import { CosmicBackdrop } from './CosmicBackdrop';
import { LivingOrb } from './LivingOrb';
import { AgentRing } from './AgentRing';
import { LiveCaptions } from './LiveCaptions';
import { MicControl } from './MicControl';

export function JarvisHomePage() {
  const {
    voiceEnabled,
    phase,
    transcript,
    partialTranscript,
    response,
    lastError,
    micDiag,
    enableVoice,
    disableVoice,
    startTurn,
    endRecordingNow,
    cancelTurn,
  } = useVoiceTurn();

  // Voice-first: auto-enable SSE on mount so the orb is "alive" and Cmd+K
  // parity works immediately. Does NOT auto-start a turn — user controls
  // that via the mic tap (or Cmd+K).
  useEffect(() => {
    if (!voiceEnabled) {
      enableVoice();
    }
    // Intentionally not adding disableVoice to deps; we keep SSE alive while
    // the user is in the app.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="relative flex flex-col w-full h-full overflow-hidden"
      style={{ background: '#02040a' }}
    >
      <CosmicBackdrop phase={phase} voiceEnabled={voiceEnabled} />

      {/* Hero zone: orb + agent ring */}
      <div className="relative flex-1 flex items-center justify-center min-h-0">
        <div className="relative flex items-center justify-center">
          <AgentRing radius={200} />
          <div className="relative z-10">
            <LivingOrb phase={phase} voiceEnabled={voiceEnabled} size={240} />
          </div>
        </div>
      </div>

      {/* Captions zone */}
      <div className="relative z-10 shrink-0 px-6">
        <LiveCaptions
          phase={phase}
          voiceEnabled={voiceEnabled}
          transcript={transcript}
          partialTranscript={partialTranscript}
          response={response}
          lastError={lastError}
          micDiag={micDiag}
        />
      </div>

      {/* Mic control + footer */}
      <div className="relative z-10 shrink-0 flex flex-col items-center pb-8 pt-2 gap-3">
        <MicControl
          phase={phase}
          voiceEnabled={voiceEnabled}
          onEnable={enableVoice}
          onDisable={disableVoice}
          onStartTurn={startTurn}
          onEndRecording={endRecordingNow}
          onCancel={cancelTurn}
        />

        {/* Command examples */}
        <div
          className="flex items-center gap-2 flex-wrap justify-center max-w-md px-4"
          style={{ color: 'rgba(160, 180, 220, 0.50)' }}
        >
          {[
            '"Search my GitHub repos for bug fixes"',
            '"What tasks need approval?"',
            '"Summarise my missions today"',
          ].map(ex => (
            <span
              key={ex}
              className="text-[10px] px-2 py-0.5 rounded-full"
              style={{
                background: 'rgba(34, 211, 238, 0.06)',
                border: '1px solid rgba(34, 211, 238, 0.12)',
                color: 'rgba(160, 180, 220, 0.55)',
              }}
            >
              {ex}
            </span>
          ))}
        </div>

        <div
          className="text-[10px] tracking-wide flex items-center gap-2.5"
          style={{ color: 'rgba(160, 180, 220, 0.35)' }}
        >
          <span>⌘K text fallback</span>
          <span aria-hidden="true">·</span>
          <span>Voice: parked/unsafe</span>
          <span aria-hidden="true">·</span>
          <span className="font-mono" style={{ color: 'rgba(61, 220, 151, 0.4)' }}>GitHub LIVE</span>
        </div>
      </div>
    </div>
  );
}

export default JarvisHomePage;
