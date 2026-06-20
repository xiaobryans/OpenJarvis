/**
 * Plan 2 — canonical UI architecture types.
 *
 * Pure types and utilities — no React, no store imports.
 * The adapter hook (usePlan2Adapter.ts) consumes these and returns
 * Plan2UIState from live app state.
 */

// ---------------------------------------------------------------------------
// Mode A / Mode B
// ---------------------------------------------------------------------------

/**
 * Mode A = ambient front door / clean idle.
 * Mode B = work surface (typing, streaming, voice, agent active, approvals).
 */
export type UIMode = 'A' | 'B';

/** Conditions that push A → B */
export const MODE_B_TRIGGERS = [
  'composerOpen',
  'isStreaming',
  'hasMessages',
  'voiceActive',
  'hasActiveAgent',
  'hasPendingApproval',
] as const;
export type ModeBTrigger = (typeof MODE_B_TRIGGERS)[number];

// ---------------------------------------------------------------------------
// Canonical UI event types
// ---------------------------------------------------------------------------

export type Plan2EventType =
  | 'voice_state_changed'
  | 'turn_started'
  | 'turn_completed'
  | 'project_changed'
  | 'agent_registered'
  | 'agent_working'
  | 'agent_finished'
  | 'tool_running'
  | 'tool_finished'
  | 'approval_required'
  | 'approval_resolved'
  | 'runtime_health_changed'
  | 'error_raised';

export interface Plan2Event<P = unknown> {
  type: Plan2EventType;
  ts: number;
  payload: P;
}

// Typed payload shapes for key events
export interface VoiceStateChangedPayload {
  enabled: boolean;
  phase: 'idle' | 'recording' | 'waiting_for_silence' | 'transcribing' | 'thinking' | 'speaking' | 'error' | 'cancelled';
}

export interface AgentEventPayload {
  agentId: string;
  name: string;
  status: 'working' | 'finished' | 'error';
}

export interface ToolEventPayload {
  toolId: string;
  name: string;
  agentId?: string;
}

export interface ApprovalPayload {
  approvalId: string;
  tier: 'trivial' | 'low' | 'medium' | 'high';
  description: string;
}

export interface ErrorPayload {
  message: string;
  source: string;
  code?: string;
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export type RegistryItemType = 'agent' | 'tool' | 'project' | 'panel' | 'approval';

export type ItemStatus =
  | 'idle'
  | 'working'
  | 'waiting'
  | 'error'
  | 'done'
  | 'approval_required'
  | 'hidden';

export type PanelAnchor = 'rail' | 'canvas' | 'diagnostics' | 'composer';

/**
 * Universal registry item — agents, tools, projects, panels, approvals all
 * share this shape so UI zones can render them without per-type hardcoding.
 */
export interface RegistryItem {
  id: string;
  type: RegistryItemType;
  name: string;
  description?: string;
  /** Emoji or lucide icon name used as fallback when no custom avatar exists. */
  icon?: string;
  /**
   * CSS variable name for the accent color, e.g. '--p2-agent-0'.
   * Defaults to '--p2-teal'.
   */
  accentToken: string;
  status: ItemStatus;
  /** Lower = higher priority in sorted lists. */
  priority: number;
  visibility: 'visible' | 'hidden' | 'background';
  panelAnchor?: PanelAnchor;
  /** Arbitrary key/value metadata (tier, model, path, etc). */
  meta?: Record<string, unknown>;
  /** ISO timestamp of last status change. */
  updatedAt: string;
}

/** Minimal shape for creating a registry item (required fields only). */
export type RegistryItemInit = Pick<RegistryItem, 'id' | 'type' | 'name'> &
  Partial<Omit<RegistryItem, 'id' | 'type' | 'name'>>;

/** Returns a fully-resolved RegistryItem with defaults applied. */
export function makeRegistryItem(init: RegistryItemInit): RegistryItem {
  return {
    accentToken: '--p2-teal',
    status: 'idle',
    priority: 50,
    visibility: 'visible',
    updatedAt: new Date().toISOString(),
    ...init,
  };
}

// ---------------------------------------------------------------------------
// Ambient mood
// ---------------------------------------------------------------------------

export type AmbientMood =
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'error'
  | 'approval';

/** Maps voice phase → ambient mood. */
export function voicePhaseToMood(
  phase: VoiceStateChangedPayload['phase'],
  enabled: boolean,
): AmbientMood {
  if (!enabled) return 'idle';
  switch (phase) {
    case 'recording':
    case 'waiting_for_silence':
      return 'listening';
    case 'transcribing':
    case 'thinking':
      return 'processing';
    case 'speaking':
      return 'speaking';
    case 'error':
      return 'error';
    default:
      return 'idle';
  }
}

/** CSS class for the current ambient mood. */
export function moodToCSSClass(mood: AmbientMood): string {
  switch (mood) {
    case 'listening':  return 'p2-ambient-listen';
    case 'processing': return 'p2-ambient-process';
    case 'speaking':   return 'p2-ambient-speaking';
    case 'error':      return 'p2-ambient-error';
    default:           return 'p2-ambient-idle';
  }
}

/** CSS variable name for the current mood color. */
export function moodToCSSVar(mood: AmbientMood): string {
  return `var(--p2-mood-${mood})`;
}

// ---------------------------------------------------------------------------
// Plan 2 UI state (output of the adapter)
// ---------------------------------------------------------------------------

export interface Plan2UIState {
  mode: UIMode;
  modeTriggers: Set<ModeBTrigger>;
  ambient: {
    mood: AmbientMood;
    intensity: number; // 0–1; driven by activity level
  };
  registry: {
    agents: RegistryItem[];
    tools: RegistryItem[];
    projects: RegistryItem[];
    panels: RegistryItem[];
    approvals: RegistryItem[];
    all: RegistryItem[];
  };
  activity: {
    isStreaming: boolean;
    streamPhase: string;
    hasMessages: boolean;
    hasActiveAgent: boolean;
    hasPendingApproval: boolean;
    pendingApprovalCount: number;
    voiceEnabled: boolean;
    voiceActive: boolean;
    voicePhase: string;
  };
  health: {
    apiReachable: boolean | null;
  };
  events: Plan2Event[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive UIMode from a set of active triggers. */
export function deriveMode(triggers: Set<ModeBTrigger>): UIMode {
  for (const t of MODE_B_TRIGGERS) {
    if (triggers.has(t)) return 'B';
  }
  return 'A';
}

/** Assign an agent accent token by round-robin index. */
export function agentAccentToken(index: number): string {
  return `--p2-agent-${index % 8}`;
}
