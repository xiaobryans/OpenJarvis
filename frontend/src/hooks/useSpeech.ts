import { useState, useCallback, useRef, useEffect } from 'react';
import { transcribeAudio, fetchSpeechHealth, isTauri } from '../lib/api';

export type SpeechState = 'idle' | 'recording' | 'transcribing';

export function useSpeech() {
  const [state, setState] = useState<SpeechState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // Check if speech backend is available on mount
  useEffect(() => {
    fetchSpeechHealth()
      .then((health) => setAvailable(health.available))
      .catch(() => setAvailable(false));
  }, []);

  const startRecording = useCallback(async (): Promise<void> => {
    setError(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        isTauri()
          ? 'Microphone API unavailable in packaged app — relaunch OpenJarvis after granting mic access in System Settings → Privacy & Security → Microphone'
          : 'Microphone not supported in this browser'
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Prefer webm/opus (browsers) then mp4/aac (WKWebView on macOS packaged app).
      // Without this, WKWebView defaults to audio/mp4 silently while we send
      // filename 'recording.webm' → backend reads wrong format → garbage transcript.
      const preferredTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4;codecs=mp4a.40.2',
        'audio/mp4',
      ];
      const supportedMime = preferredTypes.find(
        (t) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)
      );
      const recorderOptions = supportedMime ? { mimeType: supportedMime } : {};

      const recorder = new MediaRecorder(stream, recorderOptions);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setState('recording');
    } catch (err) {
      const domErr = err as DOMException;
      const name = domErr?.name ?? '';
      const message = domErr?.message ?? '';
      let msg: string;
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        msg = isTauri()
          ? 'Microphone permission denied — open System Settings → Privacy & Security → Microphone, enable OpenJarvis, then relaunch'
          : 'Microphone access denied';
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        msg = 'No microphone found — check your audio input device';
      } else if (name === 'NotSupportedError' || message.toLowerCase().includes('not available')) {
        msg = isTauri()
          ? 'Microphone permission missing — open System Settings → Privacy & Security → Microphone, enable OpenJarvis, then relaunch'
          : 'Microphone not supported in this browser';
      } else {
        msg = isTauri()
          ? `Microphone unavailable in packaged app: ${message || name || 'unknown error'}`
          : 'Microphone access denied';
      }
      setError(msg);
      setState('idle');
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<string> => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state !== 'recording') {
        reject(new Error('Not recording'));
        return;
      }

      recorder.onstop = async () => {
        setState('transcribing');

        // Stop all audio tracks
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;

        // Derive filename from the ACTUAL recorded MIME type so the backend
        // decodes correctly. WKWebView records audio/mp4 (m4a); browsers
        // record audio/webm. Sending 'recording.webm' for mp4 data causes
        // the STT backend to parse the wrong container → garbage transcript.
        const actualMime = recorder.mimeType || 'audio/webm';
        const ext =
          actualMime.includes('mp4') || actualMime.includes('m4a') ? 'm4a'
          : actualMime.includes('ogg') ? 'ogg'
          : 'webm';
        const filename = `recording.${ext}`;

        const blob = new Blob(chunksRef.current, { type: actualMime });
        chunksRef.current = [];

        // Dev diagnostics — never logged in production builds
        if (import.meta.env.DEV) {
          console.debug(
            '[useSpeech] mimeType:', actualMime,
            'ext:', ext,
            'bytes:', blob.size,
            'filename:', filename,
          );
        }

        // Reject recordings that are too short to contain real speech
        if (blob.size < 1000) {
          const msg = 'Recording too short — hold the mic button while speaking';
          setError(msg);
          setState('idle');
          reject(new Error(msg));
          return;
        }

        try {
          const result = await transcribeAudio(blob, filename);
          setState('idle');
          resolve(result.text);
        } catch (err) {
          setState('idle');
          const msg = err instanceof Error ? err.message : 'Transcription failed';
          setError(msg);
          reject(err);
        }
      };

      recorder.stop();
    });
  }, []);

  return {
    state,
    error,
    available,
    startRecording,
    stopRecording,
    isRecording: state === 'recording',
    isTranscribing: state === 'transcribing',
  };
}
