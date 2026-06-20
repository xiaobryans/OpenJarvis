/**
 * useVoiceTurn — manual-command-first voice turn hook.
 *
 * Uses the new deterministic VoiceTurnEngine (/v1/voice/turn/*).
 * No wake-word, no background recording, no session loop.
 *
 * UI contract:
 *   voiceEnabled false  → "Voice off"
 *   voiceEnabled true + phase 'idle'   → "Ready — press Speak now"
 *   phase 'recording'                  → "Recording"
 *   phase 'waiting_for_silence'        → "Waiting for silence"
 *   phase 'transcribing'               → "Transcribing"
 *   phase 'thinking'                   → "Thinking"
 *   phase 'speaking'                   → "Speaking"
 *   phase 'error'                      → "Error" + lastError
 *   phase 'cancelled'                  → "Cancelled"
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getBase, authHeaders } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TurnPhase =
  | 'idle'
  | 'recording'
  | 'waiting_for_silence'
  | 'transcribing'
  | 'thinking'
  | 'speaking'
  | 'follow_up_listening'
  | 'error'
  | 'cancelled';

export type { TurnPhase as VoiceTurnPhase };

export interface VadDiag {
  stop_reason?: string;
  duration_s?: number;
  silence_stop_ms?: number;
  noise_floor_rms?: number;
  effective_threshold?: number;
}

export interface MicDiag {
  too_quiet: boolean;
  original_rms?: number;
  scale?: number;
  hint?: string;
}

export interface TurnEvent {
  type:
    | 'state'
    | 'transcript'
    | 'partial_transcript'
    | 'transcript_rejected'
    | 'response'
    | 'route'
    | 'vad'
    | 'error'
    | 'turn_done'
    | 'follow_up_listening'
    | 'conversation_ended'
    | 'mic_diag'
    | 'keepalive';
  state?: TurnPhase;
  text?: string;
  reason?: string;
  turn_id?: number;
  final_phase?: TurnPhase;
  ts?: number;
  // vad fields
  stop_reason?: string;
  duration_s?: number;
  silence_stop_ms?: number;
  noise_floor_rms?: number;
  effective_threshold?: number;
  // route fields
  model?: string;
  provider?: string;
  complexity_tier?: string;
  // follow-up fields
  timeout_s?: number;
  conversation_turns?: number;
  stop_phrase?: string;
  // mic_diag fields
  too_quiet?: boolean;
  original_rms?: number;
  scale?: number;
  hint?: string;
}

export interface VoiceTurnState {
  voiceEnabled: boolean;
  phase: TurnPhase;
  turnId: number | null;
  transcript: string;
  partialTranscript: string;
  response: string;
  lastError: string | null;
  lastVad: VadDiag | null;
  routeInfo: { model?: string; provider?: string; tier?: string } | null;
  micDiag: MicDiag | null;
  conversationTurns: number;
  inFollowUp: boolean;
}

export interface VoiceTurnActions {
  enableVoice: () => void;
  disableVoice: () => void;
  startTurn: (language?: string) => Promise<{ ok: boolean; error?: string }>;
  cancelTurn: () => Promise<void>;
  endRecordingNow: () => Promise<boolean>;
}

export type UseVoiceTurnReturn = VoiceTurnState & VoiceTurnActions;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const BASE = () => getBase();
const HEADERS = () => authHeaders();

export function useVoiceTurn(): UseVoiceTurnReturn {
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [phase, setPhase] = useState<TurnPhase>('idle');
  const [turnId, setTurnId] = useState<number | null>(null);
  const [transcript, setTranscript] = useState('');
  const [partialTranscript, setPartialTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastVad, setLastVad] = useState<VadDiag | null>(null);
  const [routeInfo, setRouteInfo] = useState<VoiceTurnState['routeInfo']>(null);
  const [micDiag, setMicDiag] = useState<MicDiag | null>(null);
  const [conversationTurns, setConversationTurns] = useState(0);
  const [inFollowUp, setInFollowUp] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const enabledRef = useRef(false);

  // ------------------------------------------------------------------
  // SSE connection
  // ------------------------------------------------------------------

  const connectSSE = useCallback(() => {
    if (esRef.current) return; // already connected

    const url = `${BASE()}/v1/voice/turn/events`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (evt) => {
      let data: TurnEvent;
      try {
        data = JSON.parse(evt.data) as TurnEvent;
      } catch {
        return;
      }

      if (data.type === 'keepalive') return;

      if (data.type === 'state' && data.state) {
        setPhase(data.state);
        if (data.turn_id != null) setTurnId(data.turn_id);
        if (data.state === 'follow_up_listening') {
          setInFollowUp(true);
          setPartialTranscript(''); // clear partial on follow-up entry
        }
        if (data.state === 'idle' || data.state === 'cancelled') {
          setInFollowUp(false);
        }
        if (data.state === 'recording') {
          // Clear per-turn display state when a follow-up recording starts
          setPartialTranscript('');
        }
        if (data.state === 'error' && data.reason) {
          setLastError(data.reason);
        }
      }

      if (data.type === 'follow_up_listening') {
        setInFollowUp(true);
        if (data.conversation_turns != null) {
          setConversationTurns(data.conversation_turns);
        }
      }

      if (data.type === 'conversation_ended') {
        setInFollowUp(false);
        if (data.conversation_turns != null) {
          setConversationTurns(data.conversation_turns);
        }
      }

      if (data.type === 'mic_diag') {
        setMicDiag({
          too_quiet: data.too_quiet ?? false,
          original_rms: data.original_rms,
          scale: data.scale,
          hint: data.hint,
        });
      }

      if (data.type === 'partial_transcript' && data.text != null) {
        setPartialTranscript(data.text);
      }

      if (data.type === 'transcript' && data.text != null) {
        setTranscript(data.text);
        setPartialTranscript(''); // final transcript replaces partial
      }

      if (data.type === 'transcript_rejected') {
        setLastError(`transcript rejected: ${data.reason ?? 'unknown'}`);
      }

      if (data.type === 'response' && data.text != null) {
        setResponse(data.text);
      }

      if (data.type === 'route') {
        setRouteInfo({
          model: data.model,
          provider: data.provider,
          tier: data.complexity_tier,
        });
      }

      if (data.type === 'vad') {
        setLastVad({
          stop_reason: data.stop_reason,
          duration_s: data.duration_s,
          silence_stop_ms: data.silence_stop_ms,
          noise_floor_rms: data.noise_floor_rms,
          effective_threshold: data.effective_threshold,
        });
      }

      if (data.type === 'error') {
        setLastError(data.reason ?? 'unknown error');
      }

      if (data.type === 'turn_done') {
        // phase already updated by the 'state' event that preceded this
      }
    };

    es.onerror = () => {
      // Reconnect only if voice is still enabled
      if (enabledRef.current) {
        esRef.current?.close();
        esRef.current = null;
        setTimeout(connectSSE, 2000);
      }
    };
  }, []);

  const disconnectSSE = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  // ------------------------------------------------------------------
  // Voice enable / disable
  // ------------------------------------------------------------------

  const enableVoice = useCallback(() => {
    enabledRef.current = true;
    setVoiceEnabled(true);
    setPhase('idle');
    setTranscript('');
    setPartialTranscript('');
    setResponse('');
    setLastError(null);
    setMicDiag(null);
    setConversationTurns(0);
    setInFollowUp(false);
    connectSSE();
  }, [connectSSE]);

  const disableVoice = useCallback(async () => {
    enabledRef.current = false;
    // Cancel any in-progress turn
    try {
      await fetch(`${BASE()}/v1/voice/turn/cancel`, {
        method: 'POST',
        headers: HEADERS(),
      });
    } catch {
      // ignore
    }
    disconnectSSE();
    setVoiceEnabled(false);
    setPhase('idle');
    setTurnId(null);
  }, [disconnectSSE]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      enabledRef.current = false;
      disconnectSSE();
    };
  }, [disconnectSSE]);

  // ------------------------------------------------------------------
  // Turn actions
  // ------------------------------------------------------------------

  const startTurn = useCallback(
    async (language = 'en'): Promise<{ ok: boolean; error?: string }> => {
      if (!enabledRef.current) {
        return { ok: false, error: 'Voice not enabled' };
      }
      try {
        const res = await fetch(`${BASE()}/v1/voice/turn/start`, {
          method: 'POST',
          headers: { ...HEADERS(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ language }),
        });
        const data = await res.json();
        if (!data.ok) {
          setLastError(data.error ?? 'start_turn failed');
        } else {
          // Clear per-turn artifacts when a new turn begins
          setTranscript('');
          setPartialTranscript('');
          setResponse('');
          setLastError(null);
          setLastVad(null);
          setRouteInfo(null);
        }
        return { ok: data.ok, error: data.error };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setLastError(msg);
        return { ok: false, error: msg };
      }
    },
    [],
  );

  const cancelTurn = useCallback(async (): Promise<void> => {
    try {
      await fetch(`${BASE()}/v1/voice/turn/cancel`, {
        method: 'POST',
        headers: HEADERS(),
      });
    } catch {
      // ignore
    }
  }, []);

  const endRecordingNow = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch(`${BASE()}/v1/voice/turn/end_recording`, {
        method: 'POST',
        headers: HEADERS(),
      });
      const data = await res.json();
      return data.ok === true;
    } catch {
      return false;
    }
  }, []);

  // ------------------------------------------------------------------
  // Return
  // ------------------------------------------------------------------

  return {
    // state
    voiceEnabled,
    phase,
    turnId,
    transcript,
    partialTranscript,
    response,
    lastError,
    lastVad,
    routeInfo,
    micDiag,
    conversationTurns,
    inFollowUp,
    // actions
    enableVoice,
    disableVoice,
    startTurn,
    cancelTurn,
    endRecordingNow,
  };
}

export default useVoiceTurn;
