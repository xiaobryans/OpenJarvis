/**
 * AmbientCore — lightweight Plan 2 visual identity layer.
 *
 * Rules:
 * - No permanent stars, rings, constellations, nebula, or sci-fi wallpaper.
 * - CSS-only: two soft radial gradients + an optional inner glow disc.
 * - Mood-reactive via className + CSS variable.
 * - Degrades cleanly: remove <AmbientCore /> and nothing breaks.
 * - Renders behind all content (z-index 0, pointer-events none).
 * - Intensity 0 = invisible; intensity 1 = full presence.
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

/**
 * Returns the CSS var name for the primary glow for the given mood.
 * Falls back to teal.
 */
function moodToGlowVar(mood: AmbientMood): string {
  switch (mood) {
    case 'listening':  return 'var(--p2-glow-amber)';
    case 'processing': return 'var(--p2-glow-indigo)';
    case 'speaking':   return 'var(--p2-glow-mint)';
    case 'error':      return 'var(--p2-glow-coral)';
    case 'approval':   return 'var(--p2-glow-amber)';
    default:           return 'var(--p2-glow-teal)';
  }
}

export function AmbientCore({ mood, intensity, enabled = true }: AmbientCoreProps) {
  if (!enabled || intensity <= 0) return null;

  const moodClass = moodToCSSClass(mood);
  const glowColor = moodToCSSVar(mood);
  const glowShadow = moodToGlowVar(mood);

  // Outer ambient haze — large, very soft, fills the background corners
  const hazeStyle = useMemo(() => ({
    position: 'fixed' as const,
    inset: 0,
    zIndex: 0,
    pointerEvents: 'none' as const,
    opacity: intensity * 0.6,
    background: `radial-gradient(ellipse 80% 60% at 50% 0%, ${glowColor} 0%, transparent 70%)`,
    transition: `opacity var(--p2-dur-slow) var(--p2-ease-smooth), background var(--p2-dur-slow) var(--p2-ease-smooth)`,
  }), [intensity, glowColor]);

  // Inner identity disc — small, crisp, anchored to the center-top
  // This is the "core" presence dot — subtle, not dominant.
  const discStyle = useMemo(() => ({
    position: 'fixed' as const,
    top: '-40px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 0,
    pointerEvents: 'none' as const,
    width: '160px',
    height: '80px',
    borderRadius: '0 0 80px 80px',
    opacity: intensity * 0.7,
    background: glowColor,
    filter: 'blur(28px)',
    boxShadow: intensity > 0.4 ? glowShadow : 'none',
    transition: `opacity var(--p2-dur-slow) var(--p2-ease-smooth), background var(--p2-dur-slow) var(--p2-ease-smooth), box-shadow var(--p2-dur-base) var(--p2-ease-smooth)`,
  }), [intensity, glowColor, glowShadow]);

  return (
    <>
      {/* Outer haze — fills background with mood color */}
      <div
        aria-hidden="true"
        style={hazeStyle}
      />

      {/* Inner core disc — animated with mood class */}
      <div
        aria-hidden="true"
        className={moodClass}
        style={discStyle}
      />
    </>
  );
}

/**
 * AmbientCorePortal — renders AmbientCore outside the layout flow.
 * Use this if you want the ambient layer to truly underlay everything
 * including fixed elements (attach to document.body via React.createPortal
 * if needed in future). For now it's just a named wrapper.
 */
export { AmbientCore as AmbientCorePortal };
