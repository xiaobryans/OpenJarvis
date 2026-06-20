/**
 * AmbientCore — living Plan 2 identity layer.
 *
 * Rules:
 * - No permanent stars, rings, constellations, nebula, or sci-fi wallpaper.
 * - CSS-only: three-layer radial depth system — haze → mid-field → core orb.
 * - Mood-reactive via className + CSS variable.
 * - Degrades cleanly: remove <AmbientCore /> and nothing breaks.
 * - Renders behind all content (z-index 0, pointer-events none).
 * - Intensity 0 = invisible; intensity 1 = full presence.
 * - Respects prefers-reduced-motion.
 */

import { useMemo } from 'react';
import type { AmbientMood } from '../lib/plan2';
import { moodToCSSClass, moodToCSSVar } from '../lib/plan2';

interface AmbientCoreProps {
  mood: AmbientMood;
  intensity: number; // 0–1
  /** If false, renders nothing (clean degradation). */
  enabled?: boolean;
}

/** Mood → tighter glow shadow with color + spread that suits depth. */
function moodToGlowShadow(mood: AmbientMood): string {
  switch (mood) {
    case 'listening':  return '0 0 60px 20px rgba(245,158,11,0.45), 0 0 120px 40px rgba(245,158,11,0.18)';
    case 'processing': return '0 0 60px 20px rgba(99,102,241,0.45), 0 0 120px 40px rgba(99,102,241,0.18)';
    case 'speaking':   return '0 0 60px 20px rgba(16,185,129,0.45), 0 0 120px 40px rgba(16,185,129,0.18)';
    case 'error':      return '0 0 60px 20px rgba(244,63,94,0.45), 0 0 120px 40px rgba(244,63,94,0.18)';
    case 'approval':   return '0 0 60px 20px rgba(245,158,11,0.42), 0 0 100px 35px rgba(245,158,11,0.16)';
    default:           return '0 0 60px 20px rgba(8,145,178,0.38), 0 0 120px 40px rgba(8,145,178,0.14)';
  }
}

export function AmbientCore({ mood, intensity, enabled = true }: AmbientCoreProps) {
  if (!enabled || intensity <= 0) return null;

  const moodClass = moodToCSSClass(mood);
  const glowColor = moodToCSSVar(mood);
  const glowShadow = moodToGlowShadow(mood);

  // Layer 1 — Atmospheric haze: large diffuse fill from the top-center
  const hazeStyle = useMemo(() => ({
    position: 'fixed' as const,
    inset: 0,
    zIndex: 0,
    pointerEvents: 'none' as const,
    opacity: intensity * 0.55,
    background: `radial-gradient(ellipse 100% 55% at 50% -5%, ${glowColor} 0%, transparent 72%)`,
    transition: 'opacity 1200ms cubic-bezier(0.4,0,0.2,1), background 1200ms cubic-bezier(0.4,0,0.2,1)',
  }), [intensity, glowColor]);

  // Layer 2 — Mid-field glow: medium disc, acts as depth "atmosphere"
  const midStyle = useMemo(() => ({
    position: 'fixed' as const,
    top: '-60px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 0,
    pointerEvents: 'none' as const,
    width: '420px',
    height: '200px',
    borderRadius: '0 0 210px 210px',
    opacity: intensity * 0.5,
    background: glowColor,
    filter: 'blur(55px)',
    transition: 'opacity 1000ms cubic-bezier(0.4,0,0.2,1), background 1000ms cubic-bezier(0.4,0,0.2,1)',
  }), [intensity, glowColor]);

  // Layer 3 — Core orb: small, bright center with crisp glow, carries animation
  const coreStyle = useMemo(() => ({
    position: 'fixed' as const,
    top: '-28px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 0,
    pointerEvents: 'none' as const,
    width: '120px',
    height: '56px',
    borderRadius: '0 0 60px 60px',
    opacity: intensity * 0.9,
    background: glowColor,
    filter: 'blur(16px)',
    boxShadow: intensity > 0.25 ? glowShadow : 'none',
    transition: 'opacity 800ms cubic-bezier(0.4,0,0.2,1), background 800ms cubic-bezier(0.4,0,0.2,1), box-shadow 600ms cubic-bezier(0.4,0,0.2,1)',
  }), [intensity, glowColor, glowShadow]);

  return (
    <>
      {/* Layer 1 — Atmospheric haze */}
      <div aria-hidden="true" style={hazeStyle} />

      {/* Layer 2 — Mid-field depth */}
      <div aria-hidden="true" style={midStyle} />

      {/* Layer 3 — Core orb with mood animation */}
      <div aria-hidden="true" className={moodClass} style={coreStyle} />
    </>
  );
}

export { AmbientCore as AmbientCorePortal };
