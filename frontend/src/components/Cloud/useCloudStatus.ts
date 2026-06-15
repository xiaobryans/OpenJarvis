import { useEffect, useState, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';

const DEFAULT_CLOUD_URL = 'http://100.118.81.37:3091';
const CLOUD_URL_KEY = 'omnix-cloud-node-url';
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
  const [cloudUrl] = useState<string>(
    () => localStorage.getItem(CLOUD_URL_KEY) || DEFAULT_CLOUD_URL,
  );
  const [nodeStatus, setNodeStatus] = useState<CloudNodeStatus>('checking');
  const [bundle, setBundle] = useState<CloudStatusBundle | null>(null);
  const [lastChecked, setLastChecked] = useState<string>('—');
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
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
      setError(String(e));
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
