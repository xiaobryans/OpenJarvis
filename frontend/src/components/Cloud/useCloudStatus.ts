import { useEffect, useState, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';

const DEFAULT_CLOUD_URL = 'http://100.118.81.37:3091';
const CLOUD_URL_KEY = 'jarvis-cloud-node-url';
const CLOUD_URL_KEY_LEGACY = 'omnix-cloud-node-url';
const POLL_INTERVAL = 30000;

export interface CloudStatusBundle {
  hostname: string;
  runtime: string;
  tailscale: string;
  storage: string;
  action_gate?: string;
  tailscale_ip?: string;
}

export type CloudNodeStatus = 'online' | 'offline' | 'checking';

export interface CloudStatus {
  nodeStatus: CloudNodeStatus;
  bundle: CloudStatusBundle | null;
  lastChecked: string;
  cloudUrl: string;
  error: string | null;
}

export function useCloudStatus(): CloudStatus {
  const [cloudUrl] = useState<string>(() => {
    let storedValue = localStorage.getItem(CLOUD_URL_KEY);
    // Migrate from legacy key if needed
    if (!storedValue) {
      const legacyValue = localStorage.getItem(CLOUD_URL_KEY_LEGACY);
      if (legacyValue) {
        localStorage.setItem(CLOUD_URL_KEY, legacyValue);
        localStorage.removeItem(CLOUD_URL_KEY_LEGACY);
        storedValue = legacyValue;
      }
    }
    return storedValue || DEFAULT_CLOUD_URL;
  });
  const [nodeStatus, setNodeStatus] = useState<CloudNodeStatus>('checking');
  const [bundle, setBundle] = useState<CloudStatusBundle | null>(null);
  const [lastChecked, setLastChecked] = useState<string>('—');
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
    // Tauri invoke is only available inside the packaged desktop app.
    // Tauri v1 exposes __TAURI_IPC__, Tauri v2 exposes __TAURI_INTERNALS__.
    // In web/hosted mode both are undefined — skip the call cleanly.
    const isTauriApp =
      typeof window !== 'undefined' &&
      (// eslint-disable-next-line @typescript-eslint/no-explicit-any
       typeof (window as any).__TAURI_INTERNALS__ !== 'undefined' ||
       // eslint-disable-next-line @typescript-eslint/no-explicit-any
       typeof (window as any).__TAURI_IPC__ !== 'undefined');

    if (!isTauriApp) {
      setNodeStatus('offline');
      setBundle(null);
      setError('Cloud node only available in the desktop app.');
      setLastChecked(new Date().toLocaleTimeString());
      return;
    }

    setNodeStatus('checking');
    setError(null);
    try {
      const data = await invoke<CloudStatusBundle>('fetch_cloud_status', {
        url: `${cloudUrl}/api/jarvis/status-bundle`,
      });
      setBundle(data);
      setNodeStatus('online');
    } catch (e) {
      setNodeStatus('offline');
      setBundle(null);
      // Sanitize: never show raw JS TypeError messages to the user
      const msg = String(e);
      setError(
        msg.startsWith('TypeError') || msg.startsWith('ReferenceError')
          ? 'Cloud node unreachable'
          : msg,
      );
    }
    setLastChecked(new Date().toLocaleTimeString());
  }, [cloudUrl]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [poll]);

  return { nodeStatus, bundle, lastChecked, cloudUrl, error };
}
