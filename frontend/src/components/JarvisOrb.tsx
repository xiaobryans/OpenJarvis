/**
 * JarvisOrb — the central living identity core for Plan 2.
 *
 * CSS 3D sphere using:
 *   - Radial gradient with off-center specular highlight (top-left)
 *   - Multi-layer box-shadow: close glow + mid bloom + far atmosphere
 *   - Inset shadows for bottom shadow depth + top rim highlight
 *   - Breathing / pulse keyframes for each mood
 *
 * Rules:
 *   - No permanent stars, rings, constellations, or nebula wallpaper.
 *   - CSS-only — no canvas, no WebGL, no extra dependencies.
 *   - Mode A: large (200px), prominent, breathes slowly.
 *   - Mode B: small (56px), subtle, stays present as ambient indicator.
 *   - Reduced-motion: keeps color; disables animation.
 *   - Low-power: animation only when prefers-reduced-motion is not set.
 */

import { useMemo } from 'react';
import type { AmbientMood } from '../lib/plan2';
import type { UIMode } from '../lib/plan2';

interface JarvisOrbProps {
  mood: AmbientMood;
  uiMode: UIMode;
  /** 0–1. Inherits from parent intensity if needed; default 1. */
  intensity?: number;
}

/** Mood color palettes — base, mid, glow layers */
const MOOD_PALETTE = {
  idle: {
    highlight: 'rgba(255,255,255,0.28)',
    bright:    'rgba(34,211,238,0.92)',
    mid:       'rgba(8,145,178,0.75)',
    dark:      'rgba(4,60,95,0.92)',
    rim:       'rgba(2,18,32,0.97)',
    glow1:     'rgba(34,211,238,0.55)',
    glow2:     'rgba(8,145,178,0.28)',
    glow3:     'rgba(8,145,178,0.12)',
    anim:      'orb-breathe-idle',
  },
  listening: {
    highlight: 'rgba(255,255,255,0.22)',
    bright:    'rgba(251,191,36,0.95)',
    mid:       'rgba(245,158,11,0.78)',
    dark:      'rgba(80,45,0,0.92)',
    rim:       'rgba(28,14,0,0.97)',
    glow1:     'rgba(245,158,11,0.58)',
    glow2:     'rgba(245,158,11,0.28)',
    glow3:     'rgba(245,158,11,0.12)',
    anim:      'orb-breathe-listen',
  },
  processing: {
    highlight: 'rgba(255,255,255,0.22)',
    bright:    'rgba(129,140,248,0.92)',
    mid:       'rgba(99,102,241,0.76)',
    dark:      'rgba(40,35,90,0.92)',
    rim:       'rgba(12,10,30,0.97)',
    glow1:     'rgba(99,102,241,0.55)',
    glow2:     'rgba(99,102,241,0.28)',
    glow3:     'rgba(99,102,241,0.12)',
    anim:      'orb-breathe-process',
  },
  speaking: {
    highlight: 'rgba(255,255,255,0.24)',
    bright:    'rgba(52,211,153,0.92)',
    mid:       'rgba(16,185,129,0.76)',
    dark:      'rgba(4,60,40,0.92)',
    rim:       'rgba(2,18,12,0.97)',
    glow1:     'rgba(16,185,129,0.55)',
    glow2:     'rgba(16,185,129,0.28)',
    glow3:     'rgba(16,185,129,0.12)',
    anim:      'orb-breathe-process',
  },
  error: {
    highlight: 'rgba(255,255,255,0.18)',
    bright:    'rgba(251,113,133,0.92)',
    mid:       'rgba(244,63,94,0.76)',
    dark:      'rgba(80,10,20,0.92)',
    rim:       'rgba(28,2,6,0.97)',
    glow1:     'rgba(244,63,94,0.55)',
    glow2:     'rgba(244,63,94,0.28)',
    glow3:     'rgba(244,63,94,0.12)',
    anim:      'orb-breathe-listen',
  },
  approval: {
    highlight: 'rgba(255,255,255,0.24)',
    bright:    'rgba(251,191,36,0.92)',
    mid:       'rgba(245,158,11,0.76)',
    dark:      'rgba(80,45,0,0.92)',
    rim:       'rgba(28,14,0,0.97)',
    glow1:     'rgba(245,158,11,0.55)',
    glow2:     'rgba(245,158,11,0.28)',
    glow3:     'rgba(245,158,11,0.12)',
    anim:      'orb-breathe-listen',
  },
} satisfies Record<AmbientMood, {
  highlight: string; bright: string; mid: string; dark: string; rim: string;
  glow1: string; glow2: string; glow3: string; anim: string;
}>;

export function JarvisOrb({ mood, uiMode, intensity = 1 }: JarvisOrbProps) {
  const p = MOOD_PALETTE[mood] ?? MOOD_PALETTE.idle;

  // Mode A: large, centered, prominent. Mode B: small, near-top, dimmer but still visible.
  const isModeA = uiMode === 'A';
  const size     = isModeA ? 200 : 64;
  const opacity  = isModeA ? intensity * 0.92 : intensity * 0.45;
  // Mode A: vertically centered on screen. Mode B: 35% from top (below top bar, visible).
  const top      = isModeA ? '50%' : '35%';
  const ytrans   = isModeA ? '-50%' : '-50%';

  const orbStyle = useMemo(() => ({
    position: 'fixed' as const,
    top,
    left: '50%',
    transform: `translate(-50%, ${ytrans})`,
    width: `${size}px`,
    height: `${size}px`,
    borderRadius: '50%',
    zIndex: 15,    // above layout content (z=10), below top bar (z=100)
    pointerEvents: 'none' as const,
    opacity,
    // 3D sphere gradient: specular at top-left, bright teal zone, dark rim
    background: `radial-gradient(
      circle at 33% 30%,
      ${p.highlight} 0%,
      ${p.bright}    18%,
      ${p.mid}       42%,
      ${p.dark}      68%,
      ${p.rim}       100%
    )`,
    // Multi-layer glow: close bloom + mid atmosphere + far halo
    // + inset bottom shadow (depth) + inset top rim (highlight edge)
    boxShadow: [
      `0 0 ${isModeA ? 50 : 14}px ${isModeA ? 16 : 4}px ${p.glow1}`,
      `0 0 ${isModeA ? 120 : 30}px ${isModeA ? 40 : 10}px ${p.glow2}`,
      `0 0 ${isModeA ? 220 : 50}px ${isModeA ? 80 : 18}px ${p.glow3}`,
      `inset 0 -${isModeA ? 35 : 10}px ${isModeA ? 55 : 15}px rgba(0,0,0,0.55)`,
      `inset 0 ${isModeA ? 3 : 1}px ${isModeA ? 12 : 4}px rgba(255,255,255,0.22)`,
    ].join(', '),
    animation: isModeA ? `${p.anim} ${mood === 'processing' || mood === 'speaking' ? '1.1s' : '4s'} ease-in-out infinite` : 'none',
    transition: [
      'width 700ms cubic-bezier(0.4,0,0.2,1)',
      'height 700ms cubic-bezier(0.4,0,0.2,1)',
      'top 700ms cubic-bezier(0.4,0,0.2,1)',
      'opacity 700ms cubic-bezier(0.4,0,0.2,1)',
      'background 600ms cubic-bezier(0.4,0,0.2,1)',
      'box-shadow 600ms cubic-bezier(0.4,0,0.2,1)',
    ].join(', '),
  }), [p, isModeA, size, opacity, top, ytrans, mood]);

  return <div aria-hidden="true" className="jarvis-orb" style={orbStyle} />;
}
