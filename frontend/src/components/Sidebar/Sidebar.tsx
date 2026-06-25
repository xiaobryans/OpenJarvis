import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router';
import {
  MessageSquare,
  Plus,
  BarChart3,
  Settings,
  Search,
  PanelLeftClose,
  PanelLeft,
  Cpu,
  Rocket,
  Bot,
  Sun,
  Moon,
  Monitor,
  Loader2,
  ScrollText,
  Database,
  Cloud,
  Target,
  Code2,
  ShieldCheck,
  BookOpen,
  Users,
  Activity,
  ListTodo,
  Bell,
  RefreshCw,
  Brain,
  Command,
  Package,
  Zap,
  Lightbulb,
  Briefcase,
  BarChart2,
  Flag,
  DollarSign,
  Globe,
  Share2,
  ShoppingBag,
  UserPlus,
  Building2,
  Crosshair,
  ClipboardCheck,
  Layers,
  AlertTriangle,
  Radio,
  Shield,
  GitBranch,
  Scale,
  Plug,
  Smartphone,
  FlaskConical,
  Star,
  Trophy,
} from 'lucide-react';
import { ConversationList } from './ConversationList';
import { useAppStore } from '../../lib/store';
import { useCloudStatus } from '../Cloud/useCloudStatus';

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');
  const { nodeStatus, bundle, error } = useCloudStatus();

  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const createConversation = useAppStore((s) => s.createConversation);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const serverInfo = useAppStore((s) => s.serverInfo);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const modelLoading = useAppStore((s) => s.modelLoading);
  const deepResearch = useAppStore((s) => s.deepResearch);

  const settings = useAppStore((s) => s.settings);
  const updateSettings = useAppStore((s) => s.updateSettings);

  const ThemeIcon = settings.theme === 'light' ? Sun : settings.theme === 'dark' ? Moon : Monitor;
  const nextTheme = settings.theme === 'light' ? 'dark' : settings.theme === 'dark' ? 'system' : 'light';

  const messages = useAppStore((s) => s.messages);
  const handleNewChat = () => {
    // Don't create a new chat if the current one is empty
    if (messages.length === 0) {
      navigate('/');
      return;
    }
    createConversation(selectedModel);
    navigate('/');
  };

  const navItems = [
    { path: '/', icon: MessageSquare, label: 'Chat', badge: null },
    { path: '/mission-control', icon: Target, label: 'Cockpit', badge: null },
    { path: '/authority', icon: ShieldCheck, label: 'Authority', badge: null },
    { path: '/dashboard', icon: BarChart3, label: 'Dashboard', badge: null },
    { path: '/workbench', icon: Code2, label: 'Workbench', badge: null },
    { path: '/data-sources', icon: Database, label: 'Connectors', badge: '4 blocked' },
    { path: '/rules', icon: BookOpen, label: 'Rules', badge: null },
    { path: '/expert-roles', icon: Users, label: 'Expert Roles', badge: null },
    { path: '/capabilities', icon: Activity, label: 'Capabilities', badge: null },
    { path: '/delegation', icon: ListTodo, label: 'Delegation', badge: null },
    { path: '/follow-ups', icon: Bell, label: 'Follow-Ups', badge: null },
    { path: '/routines', icon: RefreshCw, label: 'Routines', badge: null },
    { path: '/memory-os', icon: Brain, label: 'Memory OS', badge: null },
    { path: '/command-center', icon: Command, label: 'Command Center', badge: null },
    { path: '/skills-plugins', icon: Package, label: 'Skills & Plugins', badge: null },
    { path: '/connector-workflows', icon: Zap, label: 'Connector Flows', badge: null },
    { path: '/proactive', icon: Lightbulb, label: 'Proactive', badge: null },
    { path: '/business-admin', icon: Briefcase, label: 'Business OS', badge: null },
    { path: '/observability', icon: BarChart2, label: 'Observability', badge: null },
    { path: '/long-horizon', icon: Flag, label: 'Long-Horizon', badge: null },
    { path: '/finance-admin', icon: DollarSign, label: 'Finance OS', badge: null },
    { path: '/research-os', icon: BookOpen, label: 'Research OS', badge: null },
    { path: '/browser-operator', icon: Globe, label: 'Browser Ops', badge: null },
    { path: '/memory-graph', icon: Share2, label: 'Memory Graph', badge: null },
    { path: '/multi-device', icon: Monitor, label: 'Multi-Device', badge: null },
    { path: '/marketplace', icon: ShoppingBag, label: 'Marketplace', badge: null },
    { path: '/org-mode', icon: UserPlus, label: 'Org Mode', badge: null },
    { path: '/device-controller', icon: Cpu, label: 'Device Ctrl', badge: null },
    { path: '/autonomous-org', icon: Building2, label: 'Autonomous Org', badge: null },
    { path: '/mission-control-c', icon: Crosshair, label: 'Mission Control', badge: null },
    { path: '/review-governance', icon: ShieldCheck, label: 'Gov & Review', badge: null },
    { path: '/product-readiness', icon: ClipboardCheck, label: 'Prod Readiness', badge: null },
    { path: '/marketplace-governance', icon: ShoppingBag, label: 'MKT Governance', badge: null },
    { path: '/enterprise-governance', icon: Shield, label: 'Enterprise Gov', badge: null },
    { path: '/scale-control', icon: Layers, label: 'Scale Control', badge: null },
    { path: '/company-os', icon: Building2, label: 'Company OS', badge: null },
    { path: '/safety-simulation', icon: AlertTriangle, label: 'Safety Sim', badge: null },
    { path: '/control-tower', icon: Radio, label: 'Control Tower', badge: null },
    { path: '/execution-readiness', icon: Zap, label: 'Execution Readiness', badge: null },
    { path: '/action-planner', icon: GitBranch, label: 'Action Planner', badge: null },
    { path: '/policy-compiler', icon: Scale, label: 'Policy Compiler', badge: null },
    { path: '/connector-readiness', icon: Plug, label: 'Connector Readiness', badge: null },
    { path: '/ios-readiness', icon: Smartphone, label: 'iOS Readiness', badge: null },
    { path: '/signing-readiness', icon: ShieldCheck, label: 'Signing Readiness', badge: null },
    { path: '/cloud-readiness', icon: Cloud, label: 'Cloud Readiness', badge: null },
    { path: '/final-smoke', icon: FlaskConical, label: 'Final Smoke', badge: null },
    { path: '/daily-driver', icon: Star, label: 'Daily Driver', badge: null },
    { path: '/core-completion', icon: Trophy, label: 'Core OS Completion', badge: null },
    { path: '/agents', icon: Bot, label: 'Agents', badge: null },
    { path: '/logs', icon: ScrollText, label: 'Logs', badge: null },
    { path: '/settings', icon: Settings, label: 'Settings', badge: null },
    { path: '/get-started', icon: Rocket, label: 'Onboarding', badge: null },
  ];

  return (
    <>
      {/* Collapse button when sidebar is closed */}
      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          className="fixed top-3 left-3 z-30 p-2 rounded-lg transition-colors cursor-pointer"
          style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-secondary)' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
        >
          <PanelLeft size={18} />
        </button>
      )}

      <aside
        className={`
          flex flex-col h-full shrink-0 transition-all duration-200 ease-in-out overflow-hidden
          fixed md:relative z-30
          ${sidebarOpen ? 'w-[260px]' : 'w-0'}
        `}
        style={{
          background: 'var(--color-sidebar)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRight: sidebarOpen ? '1px solid var(--color-border)' : 'none',
        }}
      >
        <div className="flex flex-col h-full w-[260px]">
          {/* Header */}
          <div className="flex items-center justify-between px-3 pt-3 pb-2">
            <button
              onClick={toggleSidebar}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: 'var(--color-text-secondary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <PanelLeftClose size={18} />
            </button>
            <div className="flex items-center gap-1">
              <button
                onClick={() => updateSettings({ theme: nextTheme })}
                className="p-2 rounded-lg transition-colors cursor-pointer"
                style={{ color: 'var(--color-text-secondary)' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                title={`Theme: ${settings.theme} (click for ${nextTheme})`}
              >
                <ThemeIcon size={16} />
              </button>
              <button
                onClick={handleNewChat}
                className="p-2 rounded-lg transition-colors cursor-pointer"
                style={{ color: 'var(--color-text-secondary)' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                title="New chat"
              >
                <Plus size={18} />
              </button>
            </div>
          </div>

          {/* Model badge */}
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="mx-3 mb-2 flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors cursor-pointer"
            style={{
              background: 'var(--color-bg-secondary)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
          >
            {modelLoading ? (
              <Loader2 size={14} className="animate-spin" style={{ color: 'var(--color-accent)' }} />
            ) : (
              <Cpu size={14} />
            )}
            <div className="flex-1 min-w-0">
              <span
                className="truncate block text-left"
                style={{ color: deepResearch ? 'var(--color-accent)' : 'var(--color-text)' }}
              >
                {deepResearch
                  ? 'Deep Research'
                  : selectedModel || serverInfo?.model || 'Select model'}
              </span>
              {modelLoading && (
                <span className="text-[10px] block text-left" style={{ color: 'var(--color-accent)' }}>
                  Loading model...
                </span>
              )}
            </div>
            {!modelLoading && (
              <kbd
                className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-tertiary)' }}
              >
                ⌘K
              </kbd>
            )}
          </button>

          {/* Search */}
          <div className="px-3 mb-2">
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm"
              style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
            >
              <Search size={14} style={{ color: 'var(--color-text-tertiary)' }} />
              <input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: 'var(--color-text)' }}
              />
            </div>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto px-2">
            <ConversationList searchQuery={searchQuery} />
          </div>

          {/* Cloud status badge */}
          {(() => {
            // "desktop app only" is an informational state, not an error
            const isWebMode = error?.includes('desktop app');
            const isOnline = nodeStatus === 'online';
            const isError = nodeStatus === 'offline' && !isWebMode;
            const badgeBg = isOnline
              ? 'color-mix(in srgb, var(--color-success, #22c55e) 8%, var(--color-bg-secondary))'
              : isError
              ? 'color-mix(in srgb, var(--color-error, #ef4444) 8%, var(--color-bg-secondary))'
              : 'var(--color-bg-secondary)';
            const iconColor = isOnline
              ? 'var(--color-success, #22c55e)'
              : isError
              ? 'var(--color-error, #ef4444)'
              : 'var(--color-text-tertiary)';
            return (
              <div
                className="mx-2 mb-1 px-2 py-1.5 rounded-lg flex items-center gap-2 text-xs shrink-0"
                style={{ background: badgeBg, border: '1px solid var(--color-border)' }}
              >
                <Cloud size={12} style={{ color: iconColor, flexShrink: 0 }} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate" style={{ color: 'var(--color-text)' }}>
                    Cloud Node
                  </div>
                  <div className="truncate" style={{ color: isOnline ? 'var(--color-success, #22c55e)' : isError ? 'var(--color-error, #ef4444)' : 'var(--color-text-tertiary)' }}>
                    {isOnline
                      ? `Cloud Active · ${bundle?.hostname ?? 'openclaw-mobile'} · ${bundle?.tailscale_ip ?? '100.118.81.37'}`
                      : isWebMode
                      ? 'Desktop app only'
                      : error || 'Cloud Unreachable'}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Bottom nav */}
          <nav className="px-2 pb-3 pt-2 flex flex-col gap-0.5" style={{ borderTop: '1px solid var(--color-border)' }}>
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className="relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors w-full text-left cursor-pointer"
                  style={{
                    background: isActive ? 'var(--color-accent-subtle)' : 'transparent',
                    color: isActive ? 'var(--color-text)' : 'var(--color-text-secondary)',
                    fontWeight: isActive ? 500 : 400,
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = 'var(--color-bg-secondary)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full"
                      style={{
                        background: 'var(--color-accent)',
                        boxShadow: '0 0 8px var(--color-accent-glow)',
                      }}
                    />
                  )}
                  <item.icon size={16} style={isActive ? { color: 'var(--color-accent)' } : undefined} />
                  <span className="flex-1 text-left">{item.label}</span>
                  {item.badge && (
                    <span
                      className="text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0"
                      style={{
                        background: 'color-mix(in srgb, var(--color-status-blocked, #f5a524) 12%, transparent)',
                        color: 'var(--color-status-blocked, #f5a524)',
                        border: '1px solid color-mix(in srgb, var(--color-status-blocked, #f5a524) 22%, transparent)',
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </aside>
    </>
  );
}
