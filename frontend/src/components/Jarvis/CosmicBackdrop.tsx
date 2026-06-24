/**
 * CosmicBackdrop — deep space, cinematic cockpit background.
 *
 * Three layers:
 *   1. State-reactive radial gradient — phase drives hue (more vivid than before)
 *   2. Neural/circuit grid field at low opacity (gives depth and spatial reference)
 *   3. Edge vignette — pulls focus to center where Jarvis core lives
 *
 * Pure CSS — no assets. Phase-reactive but never fakes state.
 */

import type { TurnPhase } from '../../hooks/useVoiceTurn';

function accentForPhase(phase: TurnPhase, voiceEnabled: boolean): { near: string; mid: string } {
  if (!voiceEnabled) {
    return { near: '#1e3050', mid: '#0d1830' };
  }
  switch (phase) {
    case 'recording':
      return { near: '#3a1418', mid: '#220a0c' };
    case 'waiting_for_silence':
      return { near: '#3a2000', mid: '#220f00' };
    case 'transcribing':
    case 'thinking':
      return { near: '#25185a', mid: '#120b30' };
    case 'speaking':
      return { near: '#0e3530', mid: '#07201c' };
    case 'follow_up_listening':
      return { near: '#0e2848', mid: '#061525' };
    case 'error':
      return { near: '#4a1818', mid: '#280808' };
    case 'cancelled':
      return { near: '#1a1e28', mid: '#0c0f18' };
    case 'idle':
    default:
      return { near: '#1c3260', mid: '#0d1838' };
  }
}

interface Props {
  phase: TurnPhase;
  voiceEnabled: boolean;
}

export function CosmicBackdrop({ phase, voiceEnabled }: Props) {
  const { near, mid } = accentForPhase(phase, voiceEnabled);
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Primary radial gradient — bright center, very dark edge */}
      <div
        style={{
          position: 'absolute', inset: 0,
          background: `radial-gradient(ellipse 100% 80% at 50% 32%, ${near} 0%, ${mid} 42%, #030508 72%, #020408 100%)`,
          transition: 'background 900ms ease',
        }}
      />

      {/* Secondary depth: faint top-left source light */}
      <div
        style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(ellipse 55% 45% at 38% 20%, rgba(34,211,238,0.06) 0%, transparent 100%)',
          transition: 'opacity 600ms',
        }}
      />

      {/* Neural / circuit grid field */}
      <div
        style={{
          position: 'absolute', inset: 0,
          opacity: 0.07,
          backgroundImage:
            'linear-gradient(rgba(34,211,238,0.55) 1px, transparent 1px),' +
            'linear-gradient(90deg, rgba(34,211,238,0.55) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          WebkitMaskImage: 'radial-gradient(ellipse 72% 60% at 50% 38%, black 0%, transparent 78%)',
          maskImage: 'radial-gradient(ellipse 72% 60% at 50% 38%, black 0%, transparent 78%)',
        }}
      />

      {/* Strong edge vignette — pulls focus to cockpit center */}
      <div
        style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(ellipse at center, transparent 25%, rgba(0,0,0,0.68) 100%)',
        }}
      />

      {/* Subtle noise grain at very low opacity */}
      <div
        className="absolute inset-0 mix-blend-overlay"
        style={{
          opacity: 0.032,
          backgroundImage:
            'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.18) 0.5px, transparent 1px),' +
            'radial-gradient(circle at 70% 60%, rgba(255,255,255,0.14) 0.5px, transparent 1px),' +
            'radial-gradient(circle at 40% 80%, rgba(255,255,255,0.16) 0.5px, transparent 1px)',
          backgroundSize: '180px 180px, 240px 240px, 200px 200px',
        }}
      />
    </div>
  );
}

export default CosmicBackdrop;
