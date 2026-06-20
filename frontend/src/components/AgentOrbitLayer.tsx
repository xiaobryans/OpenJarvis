/**
 * AgentOrbitLayer — lightweight agent/bot status indicators around the JarvisOrb.
 *
 * Rules:
 *   - No permanent rings, constellation lines, or noisy backgrounds.
 *   - Max 8 agents shown. Data-driven from plan2Registry.
 *   - idle → dim dot. working → pulse/glow. error → coral. done → muted green.
 *   - CSS-only animation. No new dependencies.
 *   - Positions arranged in a halo around the orb center using trig.
 *   - Hides when uiMode = 'B' (work surface) to not distract.
 */

import { useMemo } from 'react';
import { useAppStore } from '../lib/store';
import type { RegistryItem } from '../lib/plan2';
import type { UIMode } from '../lib/plan2';

interface AgentOrbitLayerProps {
  uiMode: UIMode;
}

const ORBIT_RADIUS_VH = 18; // distance from center as vmin units
const MAX_AGENTS = 8;

/** Status → color + glow */
function agentStatusStyle(status: RegistryItem['status']): {
  bg: string; shadow: string; animate: boolean;
} {
  switch (status) {
    case 'working':
      return {
        bg: 'rgba(34,211,238,0.85)',
        shadow: '0 0 10px 4px rgba(34,211,238,0.55), 0 0 20px 6px rgba(34,211,238,0.25)',
        animate: true,
      };
    case 'error':
      return {
        bg: 'rgba(244,63,94,0.85)',
        shadow: '0 0 8px 3px rgba(244,63,94,0.45)',
        animate: false,
      };
    case 'done':
      return {
        bg: 'rgba(52,211,153,0.6)',
        shadow: '0 0 6px 2px rgba(52,211,153,0.25)',
        animate: false,
      };
    case 'hidden':
      return { bg: 'transparent', shadow: 'none', animate: false };
    default: // idle
      return {
        bg: 'rgba(255,255,255,0.18)',
        shadow: 'none',
        animate: false,
      };
  }
}

function AgentDot({ item, index, total }: { item: RegistryItem; index: number; total: number }) {
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2; // start from top
  const x = Math.cos(angle) * ORBIT_RADIUS_VH;
  const y = Math.sin(angle) * ORBIT_RADIUS_VH;

  const { bg, shadow, animate } = agentStatusStyle(item.status);
  if (item.status === 'hidden') return null;

  return (
    // Wrapper handles fixed position; inner handles animation (keeps transforms separate)
    <div
      style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: `translate(calc(-50% + ${x}vmin), calc(-50% + ${y}vmin))`,
        zIndex: 2,
        pointerEvents: 'none',
      }}
    >
      <div
        title={`${item.name} — ${item.status}`}
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: bg,
          boxShadow: shadow,
          animation: animate ? 'agent-glow-pulse 1.4s ease-in-out infinite' : 'none',
          transition: 'background 500ms ease, box-shadow 500ms ease',
        }}
      />
    </div>
  );
}

function AgentLabel({ item, index, total }: { item: RegistryItem; index: number; total: number }) {
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
  const labelRadius = ORBIT_RADIUS_VH + 3.5;
  const x = Math.cos(angle) * labelRadius;
  const y = Math.sin(angle) * labelRadius;

  if (item.status === 'hidden') return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: `translate(calc(-50% + ${x}vmin), calc(-50% + ${y}vmin))`,
        fontSize: '9px',
        fontFamily: 'var(--font-hud)',
        letterSpacing: '0.06em',
        color: item.status === 'working' ? 'var(--p2-teal)' : 'rgba(255,255,255,0.3)',
        textAlign: 'center',
        whiteSpace: 'nowrap',
        zIndex: 2,
        pointerEvents: 'none',
        transition: 'color 500ms ease',
        maxWidth: '70px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {item.name.slice(0, 12)}
    </div>
  );
}

export function AgentOrbitLayer({ uiMode }: AgentOrbitLayerProps) {
  const registry = useAppStore((s) => s.plan2Registry);

  const agents = useMemo(
    () => registry
      .filter((r) => r.type === 'agent' && r.status !== 'hidden')
      .slice(0, MAX_AGENTS),
    [registry],
  );

  // In Mode B (work surface), agents are present but smaller/dimmer
  // In Mode A (ambient), agents are full size
  const scale = uiMode === 'B' ? 0.6 : 1.0;
  const opacity = uiMode === 'B' ? 0.3 : 0.9;

  if (agents.length === 0) return null;

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        transition: 'opacity 600ms ease, transform 600ms ease',
      }}
    >
      {agents.map((agent, i) => (
        <AgentDot key={agent.id} item={agent} index={i} total={agents.length} />
      ))}
      {agents.map((agent, i) => (
        <AgentLabel key={`${agent.id}-label`} item={agent} index={i} total={agents.length} />
      ))}
    </div>
  );
}
