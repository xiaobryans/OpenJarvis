import { describe, expect, it } from 'vitest';
import {
  healthChipColor,
  NO_GAP_REMAINING_ITEMS,
  VOICE_GATE_LABEL,
} from './no_gap_status';

// ---------------------------------------------------------------------------
// healthChipColor
// ---------------------------------------------------------------------------

describe('healthChipColor', () => {
  it('maps pass / ready / configured to green', () => {
    expect(healthChipColor('pass')).toBe('#22c55e');
    expect(healthChipColor('ready')).toBe('#22c55e');
    expect(healthChipColor('configured')).toBe('#22c55e');
  });

  it('does NOT map ready_pending_test_approval to green', () => {
    const color = healthChipColor('ready_pending_test_approval');
    expect(color).not.toBe('#22c55e');
    expect(color).toBe('#f59e0b');
  });

  it('does NOT map configured_not_started to green', () => {
    const color = healthChipColor('configured_not_started');
    expect(color).not.toBe('#22c55e');
    expect(color).toBe('#f59e0b');
  });

  it('maps warn / partial / degraded to amber', () => {
    expect(healthChipColor('warn')).toBe('#f59e0b');
    expect(healthChipColor('partial')).toBe('#f59e0b');
    expect(healthChipColor('degraded')).toBe('#f59e0b');
  });

  it('maps fail / hold / not_configured / error to red', () => {
    expect(healthChipColor('fail')).toBe('#ef4444');
    expect(healthChipColor('hold')).toBe('#ef4444');
    expect(healthChipColor('not_configured')).toBe('#ef4444');
    expect(healthChipColor('error')).toBe('#ef4444');
  });

  it('returns a non-green fallback for unknown values', () => {
    const color = healthChipColor('unknown');
    expect(color).not.toBe('#22c55e');
    const colorUndef = healthChipColor(undefined);
    expect(colorUndef).not.toBe('#22c55e');
  });
});

// ---------------------------------------------------------------------------
// NO_GAP_REMAINING_ITEMS — required sprint tracking
// ---------------------------------------------------------------------------

describe('NO_GAP_REMAINING_ITEMS', () => {
  it('contains exactly 4 required sprints', () => {
    expect(NO_GAP_REMAINING_ITEMS).toHaveLength(4);
  });

  it('includes all four required no-gap sprints by id', () => {
    const ids = NO_GAP_REMAINING_ITEMS.map(i => i.id);
    expect(ids).toContain('ui_polish');
    expect(ids).toContain('packaging');
    expect(ids).toContain('voice_safety');
    expect(ids).toContain('no_gap_suite');
  });

  it('does NOT mark any sprint as completed', () => {
    for (const item of NO_GAP_REMAINING_ITEMS) {
      expect((item as { status: string }).status).not.toBe('completed');
      expect((item as { status: string }).status).not.toBe('certified');
    }
  });

  it('ui_polish sprint is in_progress — first active sprint', () => {
    const uiPolish = NO_GAP_REMAINING_ITEMS.find(i => i.id === 'ui_polish');
    expect(uiPolish?.status).toBe('in_progress');
  });

  it('voice_safety is a distinct sprint — not merged with text/AI cert', () => {
    const voice = NO_GAP_REMAINING_ITEMS.find(i => i.id === 'voice_safety');
    expect(voice).toBeDefined();
    expect(voice?.label.toLowerCase()).toContain('voice');
    expect(voice?.label.toLowerCase()).not.toContain('text');
  });
});

// ---------------------------------------------------------------------------
// VOICE_GATE_LABEL
// ---------------------------------------------------------------------------

describe('VOICE_GATE_LABEL', () => {
  it('mentions voice and sprint requirement — not certified', () => {
    expect(VOICE_GATE_LABEL.toLowerCase()).toContain('voice');
    expect(VOICE_GATE_LABEL.toLowerCase()).toContain('sprint');
  });

  it('does NOT claim voice is ready or certified', () => {
    const lower = VOICE_GATE_LABEL.toLowerCase();
    expect(lower).not.toMatch(/voice.*ready(?!\s+pending)/);
    expect(lower).not.toContain('voice certified');
    expect(lower).not.toContain('voice passed');
  });
});
