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
import { CloudStatusChip } from './Cloud/CloudStatusStrip';
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
      aria-label="Main navigation"
    >
      {/* Composer button — top logo */}
      <button
        onClick={() => setComposerOpen(true)}
        className="w-8 h-8 rounded-xl flex items-center justify-center mb-3 cursor-pointer transition-all"
        style={{
          background: 'var(--p2-teal)',
          color: '#fff',
          boxShadow: 'var(--p2-glow-teal)',
        }}
        title="Open composer (⌘K)"
        aria-label="Open Jarvis composer"
      >
        <Command size={15} />
      </button>

      {/* System pulse */}
      <div className="mb-3">
        <SystemPulse apiReachable={apiReachable} />
      </div>

      {/* Main nav group */}
      <div className="flex flex-col gap-0.5 flex-1 w-full">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.path);
          return (
            <RailButton
              key={item.path}
              icon={item.icon}
              label={item.label}
              active={active}
              onClick={() => navigate(item.path)}
            />
          );
        })}
      </div>

      {/* Separator */}
      <div
        className="w-6 my-2 shrink-0"
        style={{ height: '1px', background: 'var(--color-border)' }}
      />

      {/* Bottom nav group */}
      <div className="flex flex-col gap-0.5 w-full mb-1">
        {/* Diagnostics toggle */}
        <RailButton
          icon={<Activity size={18} />}
          label="Diagnostics (⌘I)"
          active={systemPanelOpen}
          onClick={toggleSystemPanel}
        />
        {NAV_BOTTOM.map((item) => {
          const active = isActive(item.path);
          return (
            <RailButton
              key={item.path}
              icon={item.icon}
              label={item.label}
              active={active}
              onClick={() => navigate(item.path)}
            />
          );
        })}
      </div>
    </nav>
  );
}

/**
 * RailButton — a single nav rail item with left accent bar when active.
 */
function RailButton({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-current={active ? 'page' : undefined}
      className="relative w-full flex items-center justify-center cursor-pointer transition-all"
      style={{
        padding: '9px 0',
        background: active ? 'var(--p2-teal-dim)' : 'transparent',
        color: active ? 'var(--p2-teal)' : 'var(--color-text-tertiary)',
        borderRadius: '6px',
        transition: 'background var(--p2-dur-fast) var(--p2-ease-smooth), color var(--p2-dur-fast) var(--p2-ease-smooth)',
      }}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.background = 'var(--color-bg-secondary)';
          e.currentTarget.style.color = 'var(--color-text-secondary)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = active ? 'var(--p2-teal-dim)' : 'transparent';
        e.currentTarget.style.color = active ? 'var(--p2-teal)' : 'var(--color-text-tertiary)';
      }}
    >
      {/* Active accent bar — left edge */}
      {active && (
        <span
          className="absolute left-0 top-1/2 rounded-r"
          style={{
            width: '2px',
            height: '18px',
            transform: 'translateY(-50%)',
            background: 'var(--p2-teal)',
            boxShadow: '0 0 6px var(--p2-teal)',
          }}
        />
      )}
      {icon}
    </button>
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

      {/* Streaming badge — Mode B indicator */}
      {streamState.isStreaming && (
        <div
          className="flex items-center gap-1.5 text-[10px] px-2 py-0.5 rounded-full"
          style={{
            background: 'var(--p2-indigo-dim)',
            border: '1px solid var(--p2-indigo)',
            color: 'var(--p2-indigo)',
            fontFamily: 'var(--font-hud)',
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full p2-status-pulse" style={{ background: 'var(--p2-indigo)', flexShrink: 0 }} />
          {(streamState.phase || 'Generating').replace(/\.\.\.$/, '…').slice(0, 28)}
        </div>
      )}

      {/* API unreachable badge */}
      {apiReachable === false && (
        <button
          onClick={() => navigate('/settings')}
          className="text-[10px] px-2 py-0.5 rounded-full cursor-pointer"
          style={{
            background: 'var(--p2-coral-dim)',
            color: 'var(--p2-coral)',
            border: '1px solid var(--p2-coral)',
          }}
          title="Local backend unreachable — click to check settings"
        >
          Backend offline
        </button>
      )}

      {/* Model pill */}
      {selectedModel && (
        <button
          onClick={() => setComposerOpen(true)}
          className="text-[10px] px-2 py-0.5 rounded-full cursor-pointer transition-all hidden sm:block"
          style={{
            background: 'var(--color-bg-tertiary)',
            color: 'var(--color-text-tertiary)',
            border: '1px solid var(--color-border)',
          }}
          title="Switch model (⌘K)"
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--p2-teal)'; e.currentTarget.style.color = 'var(--p2-teal)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-tertiary)'; }}
        >
          {selectedModel.length > 22 ? selectedModel.slice(0, 22) + '…' : selectedModel}
        </button>
      )}

      {/* Cloud status chip */}
      <CloudStatusChip />

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

  // Sync mode attr to <body> for global CSS targeting
  useEffect(() => {
    document.body.setAttribute('data-ui-mode', uiMode);
  }, [uiMode]);

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
