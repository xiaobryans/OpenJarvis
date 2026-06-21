/**
 * GetStartedPage — Jarvis OS Onboarding + Capability Tour.
 *
 * Covers:
 *   • What Jarvis is
 *   • What's live now (Post Plan-7C status)
 *   • What's blocked / needs credentials
 *   • How approvals work
 *   • Mobile / desktop continuity
 *   • Limitations and honest status
 *   • Roadmap: Plan 8, final cutover
 *   • Install instructions (collapsible for self-hosted / desktop)
 */

import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router';
import {
  Target,
  Shield,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Brain,
  GitBranch,
  Smartphone,
  Database,
  Bell,
  AlertCircle,
  ArrowRight,
  RefreshCw,
  Lock,
  Download,
  Terminal,
  Globe,
  Monitor,
  Apple,
  Copy,
  Check,
  Cpu,
} from 'lucide-react';
import { isTauri, checkHealth } from '../lib/api';

// ---------------------------------------------------------------------------
// Types and helpers
// ---------------------------------------------------------------------------

type DeployContext = 'hosted' | 'desktop' | 'selfhosted';

function detectContext(): DeployContext {
  if (isTauri()) return 'desktop';
  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') return 'selfhosted';
  return 'hosted';
}

function detectPlatform(): string {
  const ua = navigator.userAgent.toLowerCase();
  const platform = navigator.platform?.toLowerCase() || '';
  if (platform.includes('mac') || ua.includes('macintosh')) return 'mac-arm';
  if (platform.includes('win') || ua.includes('windows')) return 'windows';
  return 'linux-deb';
}

const GITHUB_BASE = 'https://github.com/open-jarvis/OpenJarvis/releases/latest/download';

const PLATFORMS = [
  { id: 'mac-arm',    label: 'macOS (Apple Silicon)',  file: 'OpenJarvis_aarch64.dmg',      icon: Apple },
  { id: 'mac-intel',  label: 'macOS (Intel)',           file: 'OpenJarvis_x64.dmg',          icon: Apple },
  { id: 'windows',    label: 'Windows (64-bit)',        file: 'OpenJarvis_x64-setup.msi',    icon: Monitor },
  { id: 'linux-deb',  label: 'Linux (DEB)',             file: 'OpenJarvis_amd64.deb',        icon: Terminal },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Section({
  icon: Icon,
  title,
  children,
  defaultOpen = false,
  accent = false,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  accent?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const Chevron = open ? ChevronDown : ChevronRight;

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        border: accent
          ? '1px solid color-mix(in srgb, var(--color-accent) 25%, var(--color-border))'
          : '1px solid var(--color-border)',
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 w-full px-4 py-3.5 text-left cursor-pointer"
        style={{ background: open ? 'var(--color-bg-secondary)' : 'var(--color-surface)' }}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.background = 'var(--color-bg-secondary)'; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.background = 'var(--color-surface)'; }}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{
            background: accent ? 'var(--color-accent-subtle)' : 'var(--color-bg-tertiary)',
            color: accent ? 'var(--color-accent)' : 'var(--color-text-secondary)',
          }}
        >
          <Icon size={14} />
        </div>
        <span className="text-sm font-medium flex-1" style={{ color: 'var(--color-text)' }}>{title}</span>
        <Chevron size={14} style={{ color: 'var(--color-text-tertiary)' }} />
      </button>
      {open && (
        <div className="px-4 pb-4 pt-3 flex flex-col gap-3" style={{ background: 'var(--color-surface)' }}>
          {children}
        </div>
      )}
    </div>
  );
}

function StatusRow({
  label,
  status,
  note,
}: {
  label: string;
  status: 'live' | 'blocked' | 'parked' | 'pending' | 'not_started';
  note: string;
}) {
  const colors: Record<string, string> = {
    live: 'var(--color-status-live)',
    blocked: 'var(--color-status-blocked)',
    parked: 'var(--color-status-parked)',
    pending: 'var(--color-status-pending)',
    not_started: 'var(--color-text-tertiary)',
  };
  const labels: Record<string, string> = {
    live: 'LIVE',
    blocked: 'BLOCKED',
    parked: 'PARKED',
    pending: 'PENDING',
    not_started: 'NOT STARTED',
  };
  const color = colors[status];
  return (
    <div
      className="flex items-start gap-3 px-3 py-2 rounded-lg"
      style={{ background: 'var(--color-bg-secondary)' }}
    >
      <span
        style={{
          width: 7, height: 7, borderRadius: '50%',
          background: color,
          boxShadow: status === 'live' ? `0 0 6px ${color}` : 'none',
          flexShrink: 0, marginTop: 5,
        }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>{label}</span>
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 rounded"
            style={{ color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
          >
            {labels[status]}
          </span>
        </div>
        <p className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{note}</p>
      </div>
    </div>
  );
}

function CapabilityCard({
  icon: Icon,
  title,
  description,
  examples,
  live,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  examples: string[];
  live: boolean;
}) {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: 'var(--color-bg-secondary)',
        border: live
          ? '1px solid color-mix(in srgb, var(--color-status-live) 20%, var(--color-border))'
          : '1px solid var(--color-border)',
        opacity: live ? 1 : 0.7,
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{
            background: live
              ? 'color-mix(in srgb, var(--color-status-live) 12%, transparent)'
              : 'var(--color-bg-tertiary)',
            color: live ? 'var(--color-status-live)' : 'var(--color-text-tertiary)',
          }}
        >
          <Icon size={14} />
        </div>
        <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{title}</span>
        {live
          ? <CheckCircle2 size={12} style={{ color: 'var(--color-status-live)', marginLeft: 'auto', flexShrink: 0 }} />
          : <XCircle size={12} style={{ color: 'var(--color-status-parked)', marginLeft: 'auto', flexShrink: 0 }} />
        }
      </div>
      <p className="text-xs mb-2" style={{ color: 'var(--color-text-secondary)' }}>{description}</p>
      <ul className="space-y-1">
        {examples.map((ex, i) => (
          <li key={i} className="text-[11px] flex items-start gap-1.5" style={{ color: 'var(--color-text-tertiary)' }}>
            <span style={{ color: 'var(--color-accent)', flexShrink: 0, marginTop: 1 }}>›</span>
            {ex}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div
      className="relative group rounded-lg px-4 py-3 text-sm font-mono overflow-x-auto"
      style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text)' }}
    >
      <pre className="whitespace-pre-wrap break-all">{code}</pre>
      <button
        onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
        className="absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
        style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-tertiary)' }}
        title="Copy"
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Onboarding Content
// ---------------------------------------------------------------------------

function OnboardingContent({ healthy }: { healthy: boolean | null }) {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-5">

      {/* Hero */}
      <div className="glass-panel p-6 text-center">
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
          style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}
        >
          <Target size={28} />
        </div>
        <h1 className="text-2xl font-bold mb-2 tracking-tight" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-display)' }}>
          Jarvis OS
        </h1>
        <p className="text-sm mb-4 max-w-lg mx-auto leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
          A futuristic personal AI operating platform — not just a chatbot.
          Jarvis manages missions, coordinates agents, remembers everything, and acts on your behalf
          with explicit approval for sensitive operations.
        </p>
        <div className="flex items-center justify-center gap-2 flex-wrap">
          {healthy === true ? (
            <>
              <span className="neon-chip neon-chip-live"><span className="status-dot-live" />Backend live</span>
              <button
                onClick={() => navigate('/')}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium cursor-pointer"
                style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)' }}
              >
                <MessageSquare size={15} /> Open Jarvis <ArrowRight size={14} />
              </button>
            </>
          ) : healthy === false ? (
            <span className="neon-chip neon-chip-blocked"><span className="status-dot-blocked" />Backend offline — start jarvis serve</span>
          ) : (
            <span className="neon-chip neon-chip-parked">Checking backend…</span>
          )}
        </div>
      </div>

      {/* Live capabilities */}
      <Section icon={CheckCircle2} title="What's Live Now (Post Plan-7C)" defaultOpen accent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <CapabilityCard
            icon={GitBranch}
            title="GitHub Connector"
            description="Read/search repos, issues, PRs, code via gh CLI keyring."
            examples={['Search code across repos', 'List open issues and PRs', 'Read file contents', 'Create issues from tasks']}
            live
          />
          <CapabilityCard
            icon={Brain}
            title="Memory OS"
            description="Semantic search across your stored memories, cross-device sync via S3."
            examples={['Store and retrieve context across sessions', 'AI distillation of past conversations', 'Cross-device state continuity', 'Vector search across memory entries']}
            live
          />
          <CapabilityCard
            icon={Target}
            title="Mission Control"
            description="Multi-step autonomous missions with task delegation and approval gates."
            examples={['Create and run multi-step missions', 'Delegate tasks to specialized agents', 'Track progress with event log', 'Approve/deny sensitive actions']}
            live
          />
          <CapabilityCard
            icon={Smartphone}
            title="AWS Secure Runtime"
            description="Always-on backend on AWS ECS Fargate — MacBook-off capable."
            examples={['Jarvis runs even when MacBook is off', 'HTTPS via API Gateway TLS', 'Mobile-accessible from anywhere', 'Cross-device continuity via Gist + S3']}
            live
          />
          <CapabilityCard
            icon={Zap}
            title="Tools & Skills"
            description="Registered tool/skill registry with capability-aware routing."
            examples={['GitHub tools (live)', 'Web search', 'Memory read/write', 'Slack/Telegram (when configured)']}
            live
          />
          <CapabilityCard
            icon={Shield}
            title="Approval System"
            description="Every sensitive action requires Bryan's explicit approval before execution."
            examples={['Risk-level classification (low/medium/high/critical)', 'Approve or deny via any device', 'Audit trail of all approvals', 'Hard gates: no bypassing']}
            live
          />
        </div>
      </Section>

      {/* Blocked / needs credentials */}
      <Section icon={AlertCircle} title="What Needs Credentials (Blocked)">
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          These connectors and features are architecturally implemented but require credentials to activate.
          No fake functionality — they show blocked status until configured.
        </p>
        <div className="flex flex-col gap-2">
          <StatusRow label="Gmail" status="blocked" note="Needs OAuth credentials (Google Cloud App Password or OAuth client). Set up via Data Sources." />
          <StatusRow label="Google Calendar" status="blocked" note="Needs OAuth credentials (Google Cloud OAuth client ID + secret). Set up via Data Sources." />
          <StatusRow label="Slack" status="blocked" note="Needs xoxp user token. Set up via Data Sources → Slack." />
          <StatusRow label="Telegram" status="blocked" note="Needs bot token from @BotFather. Set up via Data Sources or Settings." />
          <StatusRow label="Voice (US13)" status="parked" note="Parked/UNSAFE until dedicated voice safety sprint. Not available — parked status shown honestly." />
          <StatusRow label="Apple Signing / Auto-Updater" status="pending" note="Apple Developer enrollment pending. Auto-updater blocked until enrolled." />
        </div>
        <button
          onClick={() => navigate('/data-sources')}
          className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg cursor-pointer w-fit"
          style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)', border: '1px solid color-mix(in srgb, var(--color-accent) 25%, transparent)' }}
        >
          <Database size={13} /> Set up connectors <ArrowRight size={12} />
        </button>
      </Section>

      {/* How approvals work */}
      <Section icon={Shield} title="How Approvals Work">
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Jarvis never takes a sensitive action without your explicit approval. Here's the flow:
        </p>
        <div className="flex flex-col gap-2">
          {[
            { step: '1', label: 'Jarvis proposes an action', detail: 'Description, risk level (low → critical), and which agent will execute it.' },
            { step: '2', label: 'Approval required', detail: 'High/critical actions pause until you approve. Low-risk actions may proceed automatically.' },
            { step: '3', label: 'Approve or Deny', detail: 'Via Mission Control on desktop or mobile. Approve lets it proceed. Deny cancels it permanently.' },
            { step: '4', label: 'Audit trail', detail: 'Every approval and denial is logged in the execution log. No action can bypass this gate.' },
            { step: '5', label: 'Hard gates', detail: 'Production deploys, secret changes, force-push to main — always require explicit approval. No exception.' },
          ].map(({ step, label, detail }) => (
            <div key={step} className="flex items-start gap-3 px-3 py-2 rounded-lg" style={{ background: 'var(--color-bg-secondary)' }}>
              <span
                className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5"
                style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}
              >
                {step}
              </span>
              <div>
                <div className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>{label}</div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{detail}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-[10px] italic" style={{ color: 'var(--color-text-tertiary)' }}>
          Plan 8 (Trusted Delegation) will expand what actions Jarvis can take autonomously —
          but only after Bryan reviews and explicitly enables it. Not started yet.
        </p>
      </Section>

      {/* Mobile / desktop continuity */}
      <Section icon={Smartphone} title="Mobile & Desktop Continuity">
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          Jarvis runs on AWS ECS Fargate. When your MacBook is off, Jarvis keeps running.
          You can reach it from your phone via the mobile PWA.
        </p>
        <div className="flex flex-col gap-2">
          {[
            { label: 'Backend runtime', note: 'AWS ECS Fargate — always-on, MacBook-off capable (HTTPS via API Gateway).' },
            { label: 'State sync', note: 'Cross-device continuity via GitHub Gist + S3 memory sync.' },
            { label: 'Mobile PWA', note: 'Full-capability mobile view — same actions as desktop, compact layout.' },
            { label: 'Approval on mobile', note: 'Approve / deny Jarvis actions from your phone while away from desktop.' },
          ].map(({ label, note }) => (
            <div key={label} className="flex items-start gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <CheckCircle2 size={12} style={{ color: 'var(--color-status-live)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <span className="font-medium" style={{ color: 'var(--color-text)' }}>{label}</span>
                {' — '}
                <span>{note}</span>
              </div>
            </div>
          ))}
        </div>
        <button
          onClick={() => navigate('/mobile')}
          className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg cursor-pointer w-fit"
          style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
        >
          <Smartphone size={13} /> Open Mobile View <ArrowRight size={12} />
        </button>
      </Section>

      {/* Honest limitations */}
      <Section icon={Lock} title="Honest Limitations — Do Not Trust Yet">
        <div className="flex flex-col gap-2">
          {[
            'Voice / US13: parked and unsafe. Not shown as available.',
            'Apple Signing: enrollment pending. Auto-updater will not work until enrolled.',
            'Gmail / Calendar / Slack / Telegram: blocked until credentials are set up.',
            'Plan 8 (Trusted Delegation): not started. Jarvis does not have expanded autonomous authority.',
            'Final hostile/lazy-user cutover: not started. Not ready for adversarial use.',
            'Sensitive data actions (billing, deletions, production deploys): hard-gated, require explicit approval.',
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <AlertCircle size={12} style={{ color: 'var(--color-status-blocked)', flexShrink: 0, marginTop: 2 }} />
              {item}
            </div>
          ))}
        </div>
      </Section>

      {/* Roadmap */}
      <Section icon={RefreshCw} title="What's Next — Roadmap">
        <div className="flex flex-col gap-2">
          {[
            { label: 'Plan 8 — Trusted Delegation', status: 'not_started' as const, note: 'Expands what Jarvis can do autonomously. Requires Bryan review before starting.' },
            { label: 'Voice Safety Sprint (US13)', status: 'parked' as const, note: 'Dedicated sprint to safely implement voice. Cannot start until current parked status is resolved.' },
            { label: 'Apple Signing', status: 'pending' as const, note: 'Waiting for Apple Developer enrollment. Unblocks auto-updater.' },
            { label: 'Gmail / Calendar OAuth', status: 'blocked' as const, note: 'Set up Google Cloud OAuth credentials to activate.' },
            { label: 'Final Hostile/Lazy-User Cutover Certification', status: 'not_started' as const, note: 'Full adversarial certification — not started. Requires Plan 8 and all blockers resolved.' },
          ].map(({ label, status, note }) => (
            <StatusRow key={label} label={label} status={status} note={note} />
          ))}
        </div>
      </Section>

    </div>
  );
}

// ---------------------------------------------------------------------------
// Install sections (collapsible, for self-hosted / desktop)
// ---------------------------------------------------------------------------

function InstallSection() {
  const detectedId = useMemo(() => detectPlatform(), []);
  const primary = PLATFORMS.find(p => p.id === detectedId) || PLATFORMS[0];
  const others = PLATFORMS.filter(p => p.id !== primary.id);

  return (
    <Section icon={Download} title="Installation / Self-Hosting">
      <div className="flex flex-col gap-3">
        <a
          href={`${GITHUB_BASE}/${primary.file}`}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium cursor-pointer"
          style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)' }}
        >
          <Download size={16} />
          Download for {primary.label}
        </a>
        {others.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {others.map(p => (
              <a
                key={p.id}
                href={`${GITHUB_BASE}/${p.file}`}
                className="text-xs underline underline-offset-2"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {p.label}
              </a>
            ))}
          </div>
        )}
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>CLI setup:</p>
        <CodeBlock code={"git clone https://github.com/open-jarvis/OpenJarvis.git\ncd OpenJarvis\nuv sync\njarvis init && jarvis serve"} />
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function GetStartedPage() {
  const context = useMemo(detectContext, []);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem('oj-onboarding-dismissed') === '1'
  );

  useEffect(() => {
    checkHealth().then(setHealthy);
  }, []);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-10">

        {/* Skip banner */}
        {!dismissed && (
          <div
            className="flex items-center gap-3 px-4 py-2.5 rounded-xl mb-5 text-xs"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
          >
            <RefreshCw size={12} style={{ color: 'var(--color-text-tertiary)' }} />
            <span>Onboarding — revisit any time via the Get Started link</span>
            <button
              onClick={() => { localStorage.setItem('oj-onboarding-dismissed', '1'); setDismissed(true); }}
              className="ml-auto text-xs cursor-pointer underline"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              Dismiss
            </button>
          </div>
        )}

        <OnboardingContent healthy={healthy} />

        {/* Install section — shown for desktop/selfhosted contexts */}
        {context !== 'hosted' && (
          <div className="mt-5">
            <InstallSection />
          </div>
        )}

        {/* Keyboard shortcuts */}
        {context === 'desktop' && (
          <div className="mt-5">
            <Section icon={Cpu} title="Keyboard Shortcuts" defaultOpen>
              <div className="grid grid-cols-2 gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <div><kbd className="font-mono px-1.5 py-0.5 rounded" style={{ background: 'var(--color-bg-tertiary)' }}>⌘K</kbd> Text fallback / transcript</div>
                <div><kbd className="font-mono px-1.5 py-0.5 rounded" style={{ background: 'var(--color-bg-tertiary)' }}>⌘I</kbd> System panel</div>
              </div>
            </Section>
          </div>
        )}

      </div>
    </div>
  );
}
