/**
 * No-gap readiness status helpers.
 *
 * Extracted for testability. The healthChipColor function is intentionally
 * strict: statuses that are pending or partial (ready_pending_test_approval,
 * configured_not_started) are amber, not green. Green is reserved for states
 * that have passed full verification.
 *
 * Full no-gap certification is HOLD until all four required sprints pass.
 * This module is the single source of truth for remaining sprint items and
 * voice gate messaging so tests can assert against real copy.
 */

/**
 * Map a raw system-health status value to a CSS color.
 *
 * Green (#22c55e)  — pass / ready / configured (fully verified)
 * Amber (#f59e0b)  — partial, degraded, warn, or pending states
 *                    (including ready_pending_test_approval and
 *                     configured_not_started — NOT verified green)
 * Red   (#ef4444)  — fail / hold / not_configured / error
 * Gray             — unknown / anything else
 */
export function healthChipColor(rawVal: string | undefined): string {
  const v = (rawVal ?? 'unknown').toLowerCase();
  if (v === 'pass' || v === 'ready' || v === 'configured') {
    return '#22c55e';
  }
  if (
    v === 'warn' ||
    v === 'partial' ||
    v === 'degraded' ||
    v === 'ready_pending_test_approval' ||
    v === 'configured_not_started'
  ) {
    return '#f59e0b';
  }
  if (v === 'fail' || v === 'hold' || v === 'not_configured' || v === 'error') {
    return '#ef4444';
  }
  return 'var(--color-text-tertiary)';
}

export const VOICE_GATE_LABEL =
  'Voice: separate safety sprint required — not yet certified';

/**
 * Remaining required sprints for full no-gap certification.
 * Status reflects the current sprint phase. Do NOT mark any as
 * 'completed' until the corresponding sprint verdict passes review.
 */
export const NO_GAP_REMAINING_ITEMS = [
  {
    id: 'ui_polish' as const,
    label: 'UI polish sprint',
    status: 'in_progress' as const,
  },
  {
    id: 'packaging' as const,
    label: 'Packaging / release sprint',
    status: 'pending' as const,
  },
  {
    id: 'voice_safety' as const,
    label: 'Voice safety sprint',
    status: 'pending' as const,
  },
  {
    id: 'no_gap_suite' as const,
    label: '30-task no-gap certification suite',
    status: 'pending' as const,
  },
] as const;

export type NoGapItemId = (typeof NO_GAP_REMAINING_ITEMS)[number]['id'];
