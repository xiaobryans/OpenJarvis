/**
 * usePlan2Adapter — single source of truth for Plan 2 UI state.
 *
 * Reads from: store (streamState, composerOpen, managedAgents, registry,
 * events, pendingApprovalsCount) + useVoiceTurn (voice phase).
 *
 * Writes back: uiMode (auto A/B transition).
 *
 * Components should read from usePlan2Adapter() instead of calling
 * individual store selectors where Plan 2 cross-cutting state is needed.
 */

import { useEffect, useMemo } from 'react';
import { useAppStore } from '../lib/store';
import { useVoiceTurn } from './useVoiceTurn';
import type { Plan2UIState, ModeBTrigger } from '../lib/plan2';
import {
  deriveMode,
  voicePhaseToMood,
  agentAccentToken,
  makeRegistryItem,
} from '../lib/plan2';

// ---------------------------------------------------------------------------
// Auto-mode hook (call once near the root — Layout or App)
// ---------------------------------------------------------------------------

/**
 * Watches store + voice state and auto-transitions uiMode A ↔ B.
 * Mount this exactly once in the component tree (Layout).
 */
export function usePlan2ModeSync() {
  const composerOpen = useAppStore((s) => s.composerOpen);
  const isStreaming = useAppStore((s) => s.streamState.isStreaming);
  const messages = useAppStore((s) => s.messages);
  const pendingApprovalsCount = useAppStore((s) => s.pendingApprovalsCount);
  const managedAgents = useAppStore((s) => s.managedAgents);
  const setUIMode = useAppStore((s) => s.setUIMode);

  const { voiceEnabled, phase: voicePhase } = useVoiceTurn();

  const voiceActive =
    voiceEnabled &&
    voicePhase !== 'idle' &&
    voicePhase !== 'cancelled' &&
    voicePhase !== 'error';

  const hasActiveAgent = managedAgents.some(
    (a) => a.status === 'running' || a.status === 'paused',
  );

  useEffect(() => {
    const triggers = new Set<ModeBTrigger>();
    if (composerOpen) triggers.add('composerOpen');
    if (isStreaming) triggers.add('isStreaming');
    if (messages.length > 0) triggers.add('hasMessages');
    if (voiceActive) triggers.add('voiceActive');
    if (hasActiveAgent) triggers.add('hasActiveAgent');
    if (pendingApprovalsCount > 0) triggers.add('hasPendingApproval');

    const derived = deriveMode(triggers);
    setUIMode(derived);
  }, [
    composerOpen,
    isStreaming,
    messages.length,
    voiceActive,
    hasActiveAgent,
    pendingApprovalsCount,
    setUIMode,
  ]);
}

// ---------------------------------------------------------------------------
// Main adapter hook
// ---------------------------------------------------------------------------

/**
 * Returns the full Plan2UIState derived from live app state.
 * Memoised — stable reference as long as inputs don't change.
 */
export function usePlan2Adapter(): Plan2UIState {
  const uiMode = useAppStore((s) => s.uiMode);
  const composerOpen = useAppStore((s) => s.composerOpen);
  const streamState = useAppStore((s) => s.streamState);
  const messages = useAppStore((s) => s.messages);
  const managedAgents = useAppStore((s) => s.managedAgents);
  const plan2Registry = useAppStore((s) => s.plan2Registry);
  const plan2Events = useAppStore((s) => s.plan2Events);
  const pendingApprovalsCount = useAppStore((s) => s.pendingApprovalsCount);

  const { voiceEnabled, phase: voicePhase } = useVoiceTurn();

  const voiceActive =
    voiceEnabled &&
    voicePhase !== 'idle' &&
    voicePhase !== 'cancelled' &&
    voicePhase !== 'error';

  const hasActiveAgent = managedAgents.some(
    (a) => a.status === 'running' || a.status === 'paused',
  );

  return useMemo(() => {
    // Compute trigger set
    const triggers = new Set<ModeBTrigger>();
    if (composerOpen) triggers.add('composerOpen');
    if (streamState.isStreaming) triggers.add('isStreaming');
    if (messages.length > 0) triggers.add('hasMessages');
    if (voiceActive) triggers.add('voiceActive');
    if (hasActiveAgent) triggers.add('hasActiveAgent');
    if (pendingApprovalsCount > 0) triggers.add('hasPendingApproval');

    // Ambient mood
    const mood = streamState.isStreaming
      ? 'processing'
      : pendingApprovalsCount > 0
      ? 'approval'
      : voicePhaseToMood(
          voicePhase as Parameters<typeof voicePhaseToMood>[0],
          voiceEnabled,
        );

    // Ambient intensity (0–1)
    const intensity = streamState.isStreaming
      ? 0.7
      : voiceActive
      ? 0.6
      : pendingApprovalsCount > 0
      ? 0.5
      : uiMode === 'B'
      ? 0.3
      : 0.1;

    // Partition registry by type
    const agents = plan2Registry.filter((r) => r.type === 'agent');
    const tools = plan2Registry.filter((r) => r.type === 'tool');
    const projects = plan2Registry.filter((r) => r.type === 'project');
    const panels = plan2Registry.filter((r) => r.type === 'panel');
    const approvals = plan2Registry.filter((r) => r.type === 'approval');

    return {
      mode: uiMode,
      modeTriggers: triggers,
      ambient: { mood, intensity },
      registry: {
        agents,
        tools,
        projects,
        panels,
        approvals,
        all: plan2Registry,
      },
      activity: {
        isStreaming: streamState.isStreaming,
        streamPhase: streamState.phase ?? '',
        hasMessages: messages.length > 0,
        hasActiveAgent,
        hasPendingApproval: pendingApprovalsCount > 0,
        pendingApprovalCount: pendingApprovalsCount,
        voiceEnabled,
        voiceActive,
        voicePhase,
      },
      health: {
        apiReachable: null, // filled in by Layout which has the health check
      },
      events: plan2Events,
    };
  }, [
    uiMode,
    composerOpen,
    streamState.isStreaming,
    streamState.phase,
    messages.length,
    voiceActive,
    voicePhase,
    voiceEnabled,
    hasActiveAgent,
    pendingApprovalsCount,
    plan2Registry,
    plan2Events,
  ]);
}

// ---------------------------------------------------------------------------
// Convenience: sync managed agents into the Plan 2 registry
// ---------------------------------------------------------------------------

/**
 * Call once in App or a dedicated effect. Keeps the registry in sync with
 * managedAgents from the API without manual per-page hookup.
 */
export function useSyncAgentsToRegistry() {
  const managedAgents = useAppStore((s) => s.managedAgents);
  const registerItem = useAppStore((s) => s.registerItem);
  const updateRegistryItem = useAppStore((s) => s.updateRegistryItem);
  const clearRegistryByType = useAppStore((s) => s.clearRegistryByType);

  useEffect(() => {
    // Re-sync whenever managedAgents list changes
    managedAgents.forEach((agent, idx) => {
      const status =
        agent.status === 'running'
          ? 'working'
          : agent.status === 'error' || agent.status === 'needs_attention' || agent.status === 'budget_exceeded' || agent.status === 'stalled'
          ? 'error'
          : agent.status === 'archived'
          ? 'hidden'
          : 'idle';

      registerItem(
        makeRegistryItem({
          id: `agent:${agent.id}`,
          type: 'agent',
          name: agent.name ?? agent.id,
          icon: '🤖',
          accentToken: agentAccentToken(idx),
          status,
          priority: agent.status === 'running' ? 10 : 50,
          visibility: agent.status === 'archived' ? 'hidden' : 'visible',
          panelAnchor: 'rail',
          meta: {
            agentId: agent.id,
            agentType: agent.agent_type,
          },
        }),
      );
    });
  }, [managedAgents, registerItem]);
}
