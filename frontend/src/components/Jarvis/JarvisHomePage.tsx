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
    response,
    lastError,
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
          response={response}
          lastError={lastError}
        />
      </div>

      {/* Mic control + footer */}
      <div className="relative z-10 shrink-0 flex flex-col items-center pb-8 pt-2 gap-4">
        <MicControl
          phase={phase}
          voiceEnabled={voiceEnabled}
          onEnable={enableVoice}
          onDisable={disableVoice}
          onStartTurn={startTurn}
          onEndRecording={endRecordingNow}
          onCancel={cancelTurn}
        />
        <div
          className="text-[11px] tracking-wide flex items-center gap-3"
          style={{ color: 'rgba(160, 180, 220, 0.40)' }}
        >
          <span>⌘K — transcript & text fallback</span>
          <span aria-hidden="true">·</span>
          <span>Wake word — coming soon</span>
        </div>
      </div>
    </div>
  );
}

export default JarvisHomePage;
