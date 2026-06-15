import { useEffect, useState, useCallback } from 'react';

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
}

export function useCloudStatus(): CloudStatus {
  const [cloudUrl] = useState<string>(
    () => localStorage.getItem(CLOUD_URL_KEY) || DEFAULT_CLOUD_URL,
  );
  const [nodeStatus, setNodeStatus] = useState<CloudNodeStatus>('checking');
  const [bundle, setBundle] = useState<CloudStatusBundle | null>(null);
  const [lastChecked, setLastChecked] = useState<string>('—');

  const poll = useCallback(async () => {
    setNodeStatus('checking');
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(`${cloudUrl}/api/jarvis/status-bundle`, {
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const data: CloudStatusBundle = await res.json();
      setBundle(data);
      setNodeStatus('online');
    } catch {
      setNodeStatus('offline');
      setBundle(null);
    }
    setLastChecked(new Date().toLocaleTimeString());
  }, [cloudUrl]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [poll]);

  return { nodeStatus, bundle, lastChecked, cloudUrl };
}
