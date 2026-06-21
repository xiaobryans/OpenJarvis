import { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { ApprovalBell } from './ApprovalBell';
import { Sidebar } from './Sidebar/Sidebar';
import { SystemPulse } from './SystemPulse';
import { VoiceOverlay } from './VoiceOverlay';
import { ConnectorStatusBar } from './ConnectorStatusBar';
import { useAppStore } from '../lib/store';
import { checkHealth } from '../lib/api';

export function Layout() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () => checkHealth().then(setApiReachable);
    check();
    const interval = setInterval(check, 30000);
    const onFocus = () => check();
    window.addEventListener('focus', onFocus);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, []);

  const navigate = useNavigate();
  const location = useLocation();
  const isVoiceHome = location.pathname === '/';

  return (
    <div className="flex flex-col h-full w-full overflow-hidden relative" style={{ paddingTop: '3px' }}>
      <div className="hud-backdrop" aria-hidden="true" />
      <SystemPulse apiReachable={apiReachable} />
      <ApprovalBell />

      {/* Health check banner */}
      {apiReachable === false && (
        <div
          className="flex items-center gap-3 px-4 py-2 text-sm shrink-0"
          style={{
            background: 'color-mix(in srgb, var(--color-error) 8%, transparent)',
            borderBottom: '1px solid color-mix(in srgb, var(--color-error) 18%, transparent)',
            color: 'var(--color-text)',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: 'var(--color-error)', boxShadow: '0 0 6px var(--color-error)' }}
          />
          <span className="font-medium">Backend unreachable</span>
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            — start <code className="font-mono">jarvis serve</code> to connect
          </span>
          <button
            onClick={() => navigate('/settings')}
            className="text-xs underline cursor-pointer ml-auto shrink-0"
            style={{ color: 'var(--color-accent)' }}
          >
            Change URL
          </button>
        </div>
      )}

      {/* Connector status strip — always visible */}
      <ConnectorStatusBar />

      <div className="flex flex-1 min-h-0 relative z-10">
        <Sidebar />
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-20 bg-black/40 md:hidden"
            onClick={() => useAppStore.getState().setSidebarOpen(false)}
          />
        )}
        <main className="flex-1 flex flex-col min-w-0 h-full relative overflow-hidden" style={{ background: 'transparent' }}>
          <div className="flex-1 flex flex-col min-w-0 min-h-0 relative z-[2]">
            <Outlet />
          </div>
        </main>
      </div>
      {!isVoiceHome && <VoiceOverlay />}
    </div>
  );
}
