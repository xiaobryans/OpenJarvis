/**
 * LivingOrb — central state-aware breathing orb.
 *
 * Tier 1 of the voice-first VANTA OS. State drives color, pulse rate, and
 * inner shimmer. Pure CSS — no Three.js to keep the packaged bundle tight
 * and avoid the dead-3D-orb failure mode from Plan 2.
 *
 * Phases:
 *   idle               → slow breath, cool blue
 *   recording          → fast pulse, red-coral
 *   waiting_for_silence→ medium pulse, amber
 *   transcribing       → spin shimmer, indigo
 *   thinking           → spin shimmer, indigo
 *   speaking           → bounce wave, teal-green
 *   error              → static dim red
 *   cancelled          → static muted
 */

import type { TurnPhase } from '../../hooks/useVoiceTurn';

interface Style {
  core: string;
  halo: string;
  ring: string;
  animation: string;
  breathMs: number;
}

function styleFor(phase: TurnPhase, voiceEnabled: boolean): Style {
  if (!voiceEnabled) {
    return {
      core: 'rgba(120, 140, 180, 0.55)',
      halo: 'rgba(80, 110, 160, 0.25)',
      ring: 'rgba(80, 110, 160, 0.18)',
      animation: 'orb-breath',
      breathMs: 5200,
    };
  }
  switch (phase) {
    case 'recording':
      return {
        core: 'rgba(255, 120, 110, 0.92)',
        halo: 'rgba(255, 80, 90, 0.45)',
        ring: 'rgba(255, 80, 90, 0.28)',
        animation: 'orb-pulse-fast',
        breathMs: 900,
      };
    case 'waiting_for_silence':
      return {
        core: 'rgba(255, 180, 100, 0.92)',
        halo: 'rgba(255, 150, 60, 0.42)',
        ring: 'rgba(255, 150, 60, 0.25)',
        animation: 'orb-pulse-med',
        breathMs: 1400,
      };
    case 'transcribing':
    case 'thinking':
      return {
        core: 'rgba(160, 140, 255, 0.92)',
        halo: 'rgba(110, 90, 230, 0.45)',
        ring: 'rgba(110, 90, 230, 0.28)',
        animation: 'orb-spin',
        breathMs: 2200,
      };
    case 'speaking':
      return {
        core: 'rgba(110, 230, 200, 0.92)',
        halo: 'rgba(60, 200, 170, 0.45)',
        ring: 'rgba(60, 200, 170, 0.28)',
        animation: 'orb-wave',
        breathMs: 1200,
      };
    case 'error':
      return {
        core: 'rgba(220, 90, 90, 0.85)',
        halo: 'rgba(190, 60, 60, 0.35)',
        ring: 'rgba(190, 60, 60, 0.20)',
        animation: 'orb-breath',
        breathMs: 4000,
      };
    case 'cancelled':
      return {
        core: 'rgba(140, 150, 170, 0.55)',
        halo: 'rgba(100, 110, 140, 0.22)',
        ring: 'rgba(100, 110, 140, 0.15)',
        animation: 'orb-breath',
        breathMs: 5200,
      };
    case 'idle':
    default:
      return {
        core: 'rgba(140, 190, 255, 0.85)',
        halo: 'rgba(80, 140, 230, 0.38)',
        ring: 'rgba(80, 140, 230, 0.22)',
        animation: 'orb-breath',
        breathMs: 3600,
      };
  }
}

interface Props {
  phase: TurnPhase;
  voiceEnabled: boolean;
  size?: number;
}

export function LivingOrb({ phase, voiceEnabled, size = 240 }: Props) {
  const s = styleFor(phase, voiceEnabled);

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Jarvis state: ${voiceEnabled ? phase : 'voice off'}`}
    >
      {/* Outer halo ring */}
      <div
        className="absolute rounded-full"
        style={{
          width: size * 1.25,
          height: size * 1.25,
          background: `radial-gradient(circle, ${s.ring} 0%, transparent 70%)`,
          animation: `${s.animation} ${s.breathMs}ms ease-in-out infinite`,
          willChange: 'transform, opacity',
        }}
      />
      {/* Mid halo */}
      <div
        className="absolute rounded-full"
        style={{
          width: size * 1.05,
          height: size * 1.05,
          background: `radial-gradient(circle, ${s.halo} 0%, transparent 65%)`,
          animation: `${s.animation} ${s.breathMs * 0.8}ms ease-in-out infinite`,
          filter: 'blur(8px)',
        }}
      />
      {/* Orbital arc — rotates continuously */}
      <div
        className="absolute"
        style={{
          width: size * 1.45,
          height: size * 1.45,
          borderRadius: '50%',
          border: `1px solid ${s.ring}`,
          borderTopColor: s.core,
          borderRightColor: 'transparent',
          borderBottomColor: 'transparent',
          animation: `orb-orbital-rotate ${s.breathMs * 3}ms linear infinite`,
          pointerEvents: 'none',
        }}
      />
      {/* Scan sweep arc — counter-rotates at different speed */}
      <div
        className="absolute"
        style={{
          width: size * 1.15,
          height: size * 1.15,
          borderRadius: '50%',
          border: '1px solid transparent',
          borderTopColor: `${s.halo}`,
          animation: `orb-orbital-rotate ${s.breathMs * 2}ms linear infinite reverse`,
          pointerEvents: 'none',
        }}
      />
      {/* Secondary pulse ring — fast independent pulse */}
      <div
        className="absolute rounded-full"
        style={{
          width: size * 0.85,
          height: size * 0.85,
          border: `1px solid ${s.ring}`,
          animation: `orb-secondary-pulse ${s.breathMs * 0.4}ms ease-in-out infinite`,
          pointerEvents: 'none',
          opacity: 0.6,
        }}
      />
      {/* Core orb */}
      <div
        className="rounded-full"
        style={{
          width: size * 0.65,
          height: size * 0.65,
          background: `radial-gradient(circle at 35% 30%, ${s.core} 0%, ${s.halo} 60%, transparent 90%)`,
          boxShadow: `0 0 60px ${s.halo}, inset 0 0 40px rgba(255,255,255,0.06)`,
          animation: `${s.animation} ${s.breathMs * 0.6}ms ease-in-out infinite`,
        }}
      />
      {/* Inner shimmer */}
      <div
        className="absolute rounded-full"
        style={{
          width: size * 0.22,
          height: size * 0.22,
          background:
            'radial-gradient(circle at 40% 35%, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.15) 50%, transparent 80%)',
          animation: `orb-shimmer ${s.breathMs * 0.5}ms ease-in-out infinite`,
          filter: 'blur(2px)',
        }}
      />
    </div>
  );
}

export default LivingOrb;
