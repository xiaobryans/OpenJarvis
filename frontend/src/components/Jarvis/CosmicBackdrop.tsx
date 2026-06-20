/**
 * CosmicBackdrop — dark premium voice-first background.
 *
 * Pure CSS, no assets. Sits behind LivingOrb. State-reactive subtle hue shift.
 * Honest design: not a copied starfield from any other product.
 */

import type { TurnPhase } from '../../hooks/useVoiceTurn';

function accentForPhase(phase: TurnPhase, voiceEnabled: boolean): string {
  if (!voiceEnabled) return '#1a2740'; // muted blue when voice off
  switch (phase) {
    case 'recording':
    case 'waiting_for_silence':
      return '#1f3460'; // listening — soft blue glow
    case 'transcribing':
    case 'thinking':
      return '#2a2660'; // processing — indigo
    case 'speaking':
      return '#1a3a35'; // speaking — teal
    case 'error':
      return '#3a1a1a'; // error — dim red
    default:
      return '#152038'; // idle — deep space blue
  }
}

interface Props {
  phase: TurnPhase;
  voiceEnabled: boolean;
}

export function CosmicBackdrop({ phase, voiceEnabled }: Props) {
  const accent = accentForPhase(phase, voiceEnabled);
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden pointer-events-none"
      style={{
        background: `radial-gradient(ellipse 80% 60% at 50% 40%, ${accent} 0%, #050810 65%, #02040a 100%)`,
        transition: 'background 600ms ease',
      }}
    >
      {/* Subtle vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.55) 100%)',
        }}
      />
      {/* Subtle drifting noise grain — CSS only, very low opacity */}
      <div
        className="absolute inset-0 opacity-[0.04] mix-blend-overlay"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 30%, rgba(255,255,255,0.18) 0.5px, transparent 1px), radial-gradient(circle at 70% 60%, rgba(255,255,255,0.14) 0.5px, transparent 1px), radial-gradient(circle at 40% 80%, rgba(255,255,255,0.16) 0.5px, transparent 1px)",
          backgroundSize: '180px 180px, 240px 240px, 200px 200px',
        }}
      />
    </div>
  );
}

export default CosmicBackdrop;
