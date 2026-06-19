import { useState, useEffect, useRef, useCallback } from 'react';
import { getBase, authHeaders } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type VoiceState =
  | 'idle'
  | 'listening'
  | 'wake_listening'
  | 'wake_detected'
  | 'acknowledging'
  | 'active_conversation'
  | 'recording'
  | 'waiting_for_silence'
  | 'transcribing'
  | 'thinking'
  | 'speaking'
  | 'follow_up_listening'
  | 'session_ended'
  | 'stopped'
  | 'error';

export interface VoiceEvent {
  type: 'state' | 'interim_transcript' | 'transcript' | 'response' | 'latency' | 'error' | 'stopped';
  state?: VoiceState;
  text?: string;
  stage?: string;
  value_ms?: number;
  message?: string;
  model?: string;
  score?: number;
  reason?: string;
  ts?: number;
}

export interface LatencyMap {
  wake_to_ack_ms?: number;
  wake_to_record_start_ms?: number;
  stt_duration_ms?: number;
  speech_end_to_stt_final_ms?: number;
  model_duration_ms?: number;
  tts_start_ms?: number;
  total_turn_ms?: number;
}

export interface VoiceProviderInfo {
  stt: string;
  tts: string;
  stt_primary?: boolean;
  tts_primary?: boolean;
}

export interface VoiceSessionState {
  voiceState: VoiceState;
  interimTranscript: string;
  finalTranscript: string;
  jarvisResponse: string;
  latency: LatencyMap;
  error: string | null;
  turnsCompleted: number;
  isActive: boolean;
  /** Set when auto-start or manual start fails — contains the actionable reason. */
  startFailedReason: string | null;
  /** Provider info returned from the backend on session start. */
  providerInfo: VoiceProviderInfo | null;
}

export interface VoiceSessionActions {
  start: (opts?: {
    /**
     * Emergency max-recording cap per turn in seconds.
     * Default 120 s. Normal turns end on silence — this is only the safety
     * fallback to prevent runaway recording.
     */
    recordSeconds?: number;
    language?: string;
    sessionTimeout?: number;
    /** Suppress UI error/state flicker — for auto-start on app mount. */
    silent?: boolean;
  }) => Promise<boolean>; // returns true on success, false on failure
  stop: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Label map for UI display
// ---------------------------------------------------------------------------

export const VOICE_STATE_LABEL: Record<VoiceState, string> = {
  idle: 'Voice off',
  listening: 'Listening…',
  wake_listening: 'Listening for "Hey Jarvis"…',
  wake_detected: 'Wake word detected',
  acknowledging: 'Acknowledged',
  active_conversation: 'Conversation active',
  recording: 'Recording',
  waiting_for_silence: 'Waiting for silence…',
  transcribing: 'Transcribing',
  thinking: 'Thinking…',
  speaking: 'Speaking',
  follow_up_listening: 'Follow-up listening…',
  session_ended: 'Session ended',
  stopped: 'Stopped',
  error: 'Error',
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useVoiceSession(): VoiceSessionState & VoiceSessionActions {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [jarvisResponse, setJarvisResponse] = useState('');
  const [latency, setLatency] = useState<LatencyMap>({});
  const [error, setError] = useState<string | null>(null);
  const [turnsCompleted, setTurnsCompleted] = useState(0);
  const [isActive, setIsActive] = useState(false);
  const [startFailedReason, setStartFailedReason] = useState<string | null>(null);
  const [providerInfo, setProviderInfo] = useState<VoiceProviderInfo | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const connectSSE = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }
    const base = getBase();
    const url = `${base}/v1/voice/session/events`;
    const hdrs = authHeaders();
    // EventSource doesn't support custom headers — use fetch-based SSE
    const ac = new AbortController();
    abortRef.current = ac;

    (async () => {
      try {
        const res = await fetch(url, {
          headers: hdrs,
          signal: ac.signal,
        });
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const ev: VoiceEvent = JSON.parse(line.slice(6));
                handleEvent(ev);
              } catch {
                // ignore parse errors
              }
            }
          }
        }
      } catch {
        // connection closed / aborted
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleEvent = useCallback((ev: VoiceEvent) => {
    if (ev.type === 'state' && ev.state) {
      setVoiceState(ev.state);
      if (ev.state === 'wake_detected' || ev.state === 'follow_up_listening') {
        // Latency values belong to one turn only. Without resetting here,
        // a follow-up's total_turn_ms was displayed beside the original
        // wake_to_record_start_ms, producing impossible-looking metrics.
        setLatency({});
      }
      if (ev.state === 'recording') {
        setInterimTranscript('');
        setFinalTranscript('');
        setJarvisResponse('');
      }
    }
    if (ev.type === 'interim_transcript' && ev.text) {
      setInterimTranscript(ev.text);
    }
    if (ev.type === 'transcript' && ev.text) {
      setFinalTranscript(ev.text);
      setInterimTranscript('');
    }
    if (ev.type === 'response' && ev.text) {
      setJarvisResponse(ev.text);
      setTurnsCompleted((n) => n + 1);
    }
    if (ev.type === 'latency' && ev.stage && ev.value_ms !== undefined) {
      setLatency((prev) => ({ ...prev, [ev.stage!]: ev.value_ms }));
    }
    if (ev.type === 'error' && ev.message) {
      setError(ev.message);
    }
    if (ev.type === 'stopped') {
      setVoiceState('idle');
      setIsActive(false);
    }
  }, []);

  // Re-connect SSE when active
  useEffect(() => {
    if (!isActive) return;
    connectSSE();
    return () => {
      abortRef.current?.abort();
    };
  }, [isActive, connectSSE]);

  const start = useCallback(async (opts?: {
    recordSeconds?: number;
    language?: string;
    sessionTimeout?: number;
    /** If true: suppress all UI state changes on failure (for auto-start on mount). */
    silent?: boolean;
  }) => {
    const silent = opts?.silent ?? false;
    if (!silent) {
      setError(null);
      setStartFailedReason(null);
      setVoiceState('listening');
      setFinalTranscript('');
      setJarvisResponse('');
      setInterimTranscript('');
      setLatency({});
      setTurnsCompleted(0);
    }

    const body = {
      // Emergency max cap — 120 s. Silence detection ends turns long before this.
      // This is NOT a fixed speech cap; normal turns end on silence automatically.
      record_seconds: opts?.recordSeconds ?? 120.0,
      language: opts?.language ?? 'en',
      session_timeout: opts?.sessionTimeout ?? 30.0,
    };

    try {
      const res = await fetch(`${getBase()}/v1/voice/session/start`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!data.ok) {
        const errorCode = data.error_code || 'unknown';
        const errorMsg = data.error || 'Failed to start voice session';
        const recovery = data.recovery ? ` Fix: ${data.recovery}` : '';
        const reason = `${errorCode}: ${errorMsg}${recovery}`;
        // Always store the failure reason (used by autoStartFailed indicator)
        setStartFailedReason(reason);
        if (!silent) {
          setError(reason);
          setVoiceState('error');
        }
        return false;
      }
      setStartFailedReason(null);
      if (data.provider_info) {
        setProviderInfo(data.provider_info as VoiceProviderInfo);
      }
      setIsActive(true);
      return true;
    } catch (e) {
      const reason = `network_error: Cannot reach backend. Check the server is running on the expected port.`;
      setStartFailedReason(reason);
      if (!silent) {
        setError(reason);
        setVoiceState('error');
      }
      return false;
    }
  }, []);

  const stop = useCallback(async () => {
    abortRef.current?.abort();
    await fetch(`${getBase()}/v1/voice/session/stop`, {
      method: 'POST',
      headers: authHeaders(),
    }).catch(() => {});
    setIsActive(false);
    setVoiceState('idle');
  }, []);

  return {
    voiceState,
    interimTranscript,
    finalTranscript,
    jarvisResponse,
    latency,
    error,
    turnsCompleted,
    isActive,
    startFailedReason,
    providerInfo,
    start,
    stop,
  };
}
