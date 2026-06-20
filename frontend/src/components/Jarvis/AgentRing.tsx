/**
 * AgentRing — Tier 4 agent/status layer around the orb.
 *
 * Honest empty state: if no managed agents exist, render a single muted
 * "No active agents" pill instead of fake constellation dots.
 *
 * Active agents → pulse + colored dot. Agents are arranged on an invisible
 * circle around the orb. Pure CSS, no canvas.
 */

import { useMemo } from 'react';
import { useAppStore } from '../../lib/store';
import type { ManagedAgent } from '../../lib/api';

const STATUS_COLOR: Record<ManagedAgent['status'], string> = {
  idle: 'rgba(140, 190, 255, 0.55)',
  running: 'rgba(110, 230, 200, 0.95)',
  paused: 'rgba(180, 180, 200, 0.55)',
  error: 'rgba(220, 90, 90, 0.95)',
  archived: 'rgba(100, 110, 130, 0.4)',
  needs_attention: 'rgba(255, 180, 100, 0.95)',
  budget_exceeded: 'rgba(255, 140, 80, 0.95)',
  stalled: 'rgba(180, 140, 90, 0.75)',
};

const PULSING_STATUSES: ManagedAgent['status'][] = [
  'running',
  'needs_attention',
  'error',
  'budget_exceeded',
];

interface Props {
  radius?: number;
}

export function AgentRing({ radius = 200 }: Props) {
  const agents = useAppStore((s) => s.managedAgents);
  const visibleAgents = useMemo(
    () => agents.filter((a) => a.status !== 'archived').slice(0, 12),
    [agents],
  );

  if (visibleAgents.length === 0) {
    return (
      <div
        className="absolute pointer-events-none flex items-center justify-center"
        style={{
          width: radius * 2,
          height: radius * 2,
        }}
      >
        <div
          className="absolute rounded-full"
          style={{
            width: radius * 2,
            height: radius * 2,
            border: '1px dashed rgba(140, 170, 220, 0.10)',
          }}
        />
        <div
          className="absolute"
          style={{
            bottom: -36,
            fontSize: 11,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'rgba(160, 180, 220, 0.45)',
          }}
        >
          No active agents
        </div>
      </div>
    );
  }

  const n = visibleAgents.length;
  return (
    <div
      className="absolute pointer-events-none"
      style={{
        width: radius * 2,
        height: radius * 2,
      }}
    >
      {/* Faint ring guide */}
      <div
        className="absolute rounded-full"
        style={{
          width: radius * 2,
          height: radius * 2,
          border: '1px solid rgba(140, 170, 220, 0.07)',
        }}
      />
      {visibleAgents.map((agent, i) => {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
        const cx = radius + Math.cos(angle) * radius;
        const cy = radius + Math.sin(angle) * radius;
        const color = STATUS_COLOR[agent.status] ?? 'rgba(140,170,220,0.6)';
        const pulsing = PULSING_STATUSES.includes(agent.status);
        return (
          <div
            key={agent.id}
            className="absolute flex flex-col items-center pointer-events-auto"
            style={{
              left: cx,
              top: cy,
              transform: 'translate(-50%, -50%)',
            }}
            title={`${agent.name} — ${agent.status}`}
          >
            <div
              className={`rounded-full ${pulsing ? 'agent-dot-pulse' : ''}`}
              style={{
                width: 12,
                height: 12,
                background: color,
                boxShadow: `0 0 14px ${color}`,
              }}
            />
            <div
              className="mt-1.5 text-[10px] truncate max-w-[80px] text-center"
              style={{
                color: 'rgba(190, 210, 240, 0.7)',
                textShadow: '0 0 6px rgba(0,0,0,0.6)',
              }}
            >
              {agent.name}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default AgentRing;
