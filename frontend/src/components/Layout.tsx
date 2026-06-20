/**
 * Plan 2 Layout — slim icon rail + main canvas + collapsible diagnostics drawer.
 *
 * Structure:
 *   <div flex-row h-screen>
 *     <NavRail />          // 48px icon column, always visible
 *     <div flex-col flex-1>
 *       <TopBar />         // slim top bar with model, status, search
 *       <main canvas />    // Outlet fills the rest
 *     </div>
 *     <DiagnosticsDrawer /> // collapsible right panel, hidden by default
 *   </div>
 *
 * The permanent bottom chat bar is GONE. Input goes through UniversalComposer (Cmd+K).
 */

import { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import {
  MessageSquare,
  BarChart3,
  Settings,
  Bot,
  Database,
  ScrollText,
  Target,
  Code2,
  Rocket,
  Command,
  Activity,
  X,
} from 'lucide-react';
import { ApprovalBell } from './ApprovalBell';
import { SystemPulse } from './SystemPulse';
import { AmbientCore } from './AmbientCore';
import { useAppStore } from '../lib/store';
import { checkHealth } from '../lib/api';
import { usePlan2ModeSync } from '../hooks/usePlan2Adapter';

interface NavItem {
  path: string;
  icon: React.ReactNode;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', icon: <MessageSquare size={18} />, label: 'Chat' },
  { path: '/dashboard', icon: <BarChart3 size={18} />, label: 'Dashboard' },
  { path: '/mission-control', icon: <Target size={18} />, label: 'Mission Control' },
  { path: '/workbench', icon: <Code2 size={18} />, label: 'Workbench' },
  { path: '/data-sources', icon: <Database size={18} />, label: 'Data Sources' },
  { path: '/agents', icon: <Bot size={18} />, label: 'Agents' },
  { path: '/logs', icon: <ScrollText size={18} />, label: 'Logs' },
];

const NAV_BOTTOM: NavItem[] = [
  { path: '/get-started', icon: <Rocket size={18} />, label: 'Get Started' },
  { path: '/settings', icon: <Settings size={18} />, label: 'Settings' },
];

// ---------------------------------------------------------------------------
// NavRail
// ---------------------------------------------------------------------------

function NavRail({ apiReachable }: { apiReachable: boolean | null }) {
  const navigate = useNavigate();
  const location = useLocation();
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);
  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);
  const systemPanelOpen = useAppStore((s) => s.systemPanelOpen);

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <nav
      className="flex flex-col items-center py-3 shrink-0 h-full z-20"
      style={{
        width: '52px',
        background: 'var(--color-sidebar)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      {/* Wordmark / logo dot */}
      <button
        onClick={() => setComposerOpen(true)}
        className="w-8 h-8 rounded-xl flex items-center justify-center mb-4 cursor-pointer transition-all"
        style={{
          background: 'var(--color-accent)',
          color: '#fff',
        }}
        title="Open composer (⌘K)"
      >
        <Command size={15} />
      </button>

      {/* System pulse indicator */}
      <div className="mb-2">
        <SystemPulse apiReachable={apiReachable} />
      </div>

      {/* Main nav */}
      <div className="flex flex-col gap-1 flex-1 w-full px-1.5">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              title={item.label}
              className="w-full flex items-center justify-center rounded-lg transition-colors cursor-pointer"
              style={{
                padding: '9px 0',
                background: active ? 'var(--color-accent-subtle)' : 'transparent',
                color: active ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = 'var(--color-bg-secondary)';
                e.currentTarget.style.color = active ? 'var(--color-accent)' : 'var(--color-text-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = active ? 'var(--color-accent-subtle)' : 'transparent';
                e.currentTarget.style.color = active ? 'var(--color-accent)' : 'var(--color-text-tertiary)';
              }}
            >
              {item.icon}
            </button>
          );
        })}
      </div>

      {/* Bottom nav */}
      <div className="flex flex-col gap-1 w-full px-1.5 mb-2">
        {/* Diagnostics toggle */}
        <button
          onClick={toggleSystemPanel}
          title="Diagnostics"
          className="w-full flex items-center justify-center rounded-lg transition-colors cursor-pointer"
          style={{
            padding: '9px 0',
            background: systemPanelOpen ? 'var(--color-accent-subtle)' : 'transparent',
            color: systemPanelOpen ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
          }}
          onMouseEnter={(e) => {
            if (!systemPanelOpen) e.currentTarget.style.background = 'var(--color-bg-secondary)';
            e.currentTarget.style.color = systemPanelOpen ? 'var(--color-accent)' : 'var(--color-text-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = systemPanelOpen ? 'var(--color-accent-subtle)' : 'transparent';
            e.currentTarget.style.color = systemPanelOpen ? 'var(--color-accent)' : 'var(--color-text-tertiary)';
          }}
        >
          <Activity size={18} />
        </button>

        {NAV_BOTTOM.map((item) => {
          const active = isActive(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              title={item.label}
              className="w-full flex items-center justify-center rounded-lg transition-colors cursor-pointer"
              style={{
                padding: '9px 0',
                background: active ? 'var(--color-accent-subtle)' : 'transparent',
                color: active ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = 'var(--color-bg-secondary)';
                e.currentTarget.style.color = active ? 'var(--color-accent)' : 'var(--color-text-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = active ? 'var(--color-accent-subtle)' : 'transparent';
                e.currentTarget.style.color = active ? 'var(--color-accent)' : 'var(--color-text-tertiary)';
              }}
            >
              {item.icon}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// TopBar — slim, clean, non-dominant
// ---------------------------------------------------------------------------

function TopBar({ apiReachable }: { apiReachable: boolean | null }) {
  const navigate = useNavigate();
  const location = useLocation();
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const streamState = useAppStore((s) => s.streamState);

  const pageLabel = () => {
    const path = location.pathname;
    if (path === '/') return 'Chat';
    if (path.startsWith('/dashboard')) return 'Dashboard';
    if (path.startsWith('/mission-control')) return 'Mission Control';
    if (path.startsWith('/workbench')) return 'Workbench';
    if (path.startsWith('/data-sources')) return 'Data Sources';
    if (path.startsWith('/agents')) return 'Agents';
    if (path.startsWith('/logs')) return 'Logs';
    if (path.startsWith('/settings')) return 'Settings';
    if (path.startsWith('/get-started')) return 'Get Started';
    return 'Jarvis';
  };

  return (
    <div
      className="flex items-center gap-3 px-4 shrink-0"
      style={{
        height: '44px',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-sidebar)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
      }}
    >
      {/* Page label */}
      <span
        className="text-sm font-medium flex-1"
        style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-hud)', letterSpacing: '0.02em' }}
      >
        {pageLabel().toUpperCase()}
      </span>

      {/* Status: streaming indicator */}
      {streamState.isStreaming && (
        <span
          className="text-[11px] px-2 py-0.5 rounded-full animate-pulse"
          style={{
            background: 'var(--color-accent-subtle)',
            color: 'var(--color-accent)',
            border: '1px solid var(--color-accent)',
            fontFamily: 'var(--font-hud)',
          }}
        >
          {streamState.phase || 'Generating…'}
        </span>
      )}

      {/* API unreachable badge */}
      {apiReachable === false && (
        <button
          onClick={() => navigate('/settings')}
          className="text-[11px] px-2 py-0.5 rounded-full cursor-pointer"
          style={{
            background: 'color-mix(in srgb, var(--color-error) 10%, transparent)',
            color: 'var(--color-error)',
            border: '1px solid color-mix(in srgb, var(--color-error) 25%, transparent)',
          }}
        >
          Backend offline
        </button>
      )}

      {/* Model pill */}
      {selectedModel && (
        <button
          onClick={() => setComposerOpen(true)}
          className="text-[11px] px-2.5 py-1 rounded-full cursor-pointer transition-colors hidden sm:block"
          style={{
            background: 'var(--color-bg-tertiary)',
            color: 'var(--color-text-tertiary)',
            border: '1px solid var(--color-border)',
          }}
          title="Open composer (⌘K)"
        >
          {selectedModel.length > 20 ? selectedModel.slice(0, 20) + '…' : selectedModel}
        </button>
      )}

      {/* Approval bell */}
      <ApprovalBell />

      {/* Cmd+K hint */}
      <button
        onClick={() => setComposerOpen(true)}
        className="hidden sm:flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg cursor-pointer transition-colors"
        style={{
          background: 'var(--color-bg-tertiary)',
          color: 'var(--color-text-tertiary)',
          border: '1px solid var(--color-border)',
        }}
        title="Open composer"
      >
        <Command size={11} />
        <span>K</span>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout root
// ---------------------------------------------------------------------------

export function Layout() {
  const systemPanelOpen = useAppStore((s) => s.systemPanelOpen);
  const uiMode = useAppStore((s) => s.uiMode);
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);

  // Plan 2 mode A/B auto-transition (must be called once in tree)
  usePlan2ModeSync();

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

  // Mode A/B: ambient intensity — higher in B, low in A
  const ambientIntensity = uiMode === 'B' ? 0.35 : 0.12;

  // Determine ambient mood from store state (keep Layout self-contained)
  const isStreaming = useAppStore((s) => s.streamState.isStreaming);
  const pendingApprovalsCount = useAppStore((s) => s.pendingApprovalsCount);
  const ambientMood = isStreaming
    ? ('processing' as const)
    : pendingApprovalsCount > 0
    ? ('approval' as const)
    : ('idle' as const);

  return (
    <div
      className="flex h-full w-full overflow-hidden p2-mode-transition"
      data-ui-mode={uiMode}
      style={{ paddingTop: '3px' }}
    >
      <div className="hud-backdrop" aria-hidden="true" />

      {/* Plan 2 ambient identity layer — behind everything */}
      <AmbientCore mood={ambientMood} intensity={ambientIntensity} />

      {/* Slim nav rail */}
      <NavRail apiReachable={apiReachable} />

      {/* Main column: top bar + canvas */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden">
        <TopBar apiReachable={apiReachable} />

        <main
          className="flex-1 min-h-0 overflow-hidden relative z-[2]"
          style={{ background: 'transparent' }}
        >
          {/* Diagnostics drawer: slides in from the right inside the canvas */}
          <div className="flex h-full">
            <div className="flex-1 min-w-0 flex flex-col min-h-0 overflow-hidden">
              <Outlet />
            </div>

            {/* Diagnostics/System panel — collapsible */}
            {systemPanelOpen && (
              <SystemPanelDrawer />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SystemPanelDrawer — lazy import the heavy SystemPanel, wrap in collapsible
// ---------------------------------------------------------------------------

function SystemPanelDrawer() {
  const setSystemPanelOpen = useAppStore((s) => s.setSystemPanelOpen);

  // Lazy-load the system panel to keep initial bundle clean
  const [SystemPanel, setSystemPanel] = useState<React.ComponentType | null>(null);
  useEffect(() => {
    import('./Chat/SystemPanel').then((m) => setSystemPanel(() => m.SystemPanel));
  }, []);

  return (
    <div
      className="shrink-0 flex flex-col min-h-0 overflow-hidden relative"
      style={{
        width: '280px',
        borderLeft: '1px solid var(--color-border)',
        background: 'var(--color-sidebar)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
      }}
    >
      {/* Close button */}
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <span
          className="text-[10px] font-medium tracking-wider"
          style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-hud)' }}
        >
          DIAGNOSTICS
        </span>
        <button
          onClick={() => setSystemPanelOpen(false)}
          className="p-1 rounded cursor-pointer"
          style={{ color: 'var(--color-text-tertiary)' }}
          title="Close diagnostics"
        >
          <X size={12} />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        {SystemPanel ? <SystemPanel /> : (
          <div className="p-4 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            Loading…
          </div>
        )}
      </div>
    </div>
  );
}
