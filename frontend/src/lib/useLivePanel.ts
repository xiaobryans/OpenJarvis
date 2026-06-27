// useLivePanel — generic auto-refreshing data hook for VANTA cockpit panels.
//
// Polls an authenticated backend endpoint on a fixed interval (Task A) using
// the shared apiFetch (base URL + Bearer auth). First fetch fires immediately;
// thereafter every intervalMs. Never throws to the component — exposes ok/error
// so a panel can show an honest "unavailable" state instead of stale/fake data.

import { useEffect, useRef, useState } from 'react';
import { apiFetch } from './api';

export interface LiveState<T> {
  data: T | null;
  ok: boolean; // last fetch succeeded
  loading: boolean; // first load still in flight
  lastUpdated: number | null; // epoch ms of last successful fetch
  error: string | null;
}

export function useLivePanel<T>(
  path: string,
  intervalMs: number,
  opts?: { enabled?: boolean },
): LiveState<T> {
  const enabled = opts?.enabled ?? true;
  const [state, setState] = useState<LiveState<T>>({
    data: null,
    ok: false,
    loading: true,
    lastUpdated: null,
    error: null,
  });
  const timer = useRef<number | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    if (!enabled) return;

    const tick = async (): Promise<void> => {
      try {
        const r = await apiFetch(path);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = (await r.json()) as T;
        if (!alive.current) return;
        setState({
          data: json,
          ok: true,
          loading: false,
          lastUpdated: Date.now(),
          error: null,
        });
      } catch (e) {
        if (!alive.current) return;
        setState((s) => ({
          ...s,
          ok: false,
          loading: false,
          error: e instanceof Error ? e.message : String(e),
        }));
      }
    };

    void tick();
    timer.current = window.setInterval(() => void tick(), intervalMs);

    return () => {
      alive.current = false;
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [path, intervalMs, enabled]);

  return state;
}
