import { useEffect, useState, useCallback, ReactNode } from 'react';
import {
  Target,
  Check,
  X,
  Loader2,
  Bell,
  BellOff,
} from 'lucide-react';
import { apiFetch } from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Mission {
  id: string;
  title: string;
  objective: string;
  status: string;
  risk_level: string;
  summary: string;
  created_at: number;
  linked_task_ids: string[];
}

interface Task {
  id: string;
  mission_id: string;
  title: string;
  description: string;
  assigned_agent_id: string;
  status: string;
  priority: number;
  risk_level: string;
  created_at: number;
  updated_at: number;
}

interface MissionEventRecord {
  event_id: string;
  mission_id: string;
  task_id: string | null;
  agent_id: string | null;
  event_type: string;
  severity: string;
  message: string;
  created_at: number;
}

interface AgentSpec {
  agent_id: string;
  display_name: string;
  role: string;
  status: string;
  permission_level: string;
  capabilities: string[];
}

interface NotifyStatus {
  slack: { configured: boolean; channel: string | null; ready: boolean };
  telegram: { configured: boolean; chat_id: string | null; ready: boolean };
}

// ---------------------------------------------------------------------------
// Status / risk colour maps
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  queued: 'var(--color-text-tertiary)',
  planning: '#3b82f6',
  running: 'var(--color-success, #22c55e)',
  awaiting_approval: '#f59e0b',
  completed: 'var(--color-success, #22c55e)',
  failed: 'var(--color-error, #ef4444)',
  cancelled: 'var(--color-text-tertiary)',
  blocked: '#f97316',
  assigned: '#3b82f6',
  pending: 'var(--color-text-tertiary)',
  idle: 'var(--color-text-tertiary)',
  disabled: 'var(--color-text-tertiary)',
};

const RISK_COLORS: Record<string, string> = {
  low: 'var(--color-text-tertiary)',
  medium: '#3b82f6',
  high: '#f59e0b',
  critical: 'var(--color-error, #ef4444)',
};

// ---------------------------------------------------------------------------
// Small shared components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? 'var(--color-text-tertiary)';
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded capitalize shrink-0"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  const color = RISK_COLORS[risk] ?? 'var(--color-text-tertiary)';
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded capitalize shrink-0"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 10%, transparent)`,
      }}
    >
      {risk}
    </span>
  );
}

function Panel({
  title,
  children,
  className = '',
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl p-4 ${className}`}
      style={{
        background: 'var(--color-bg-secondary)',
        border: '1px solid var(--color-border)',
      }}
    >
      <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div
      className="flex items-center justify-center py-8 text-sm"
      style={{ color: 'var(--color-text-tertiary)' }}
    >
      {text}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function MissionControlPage() {
  // Mission list
  const [missions, setMissions] = useState<Mission[]>([]);
  const [missionsLoading, setMissionsLoading] = useState(true);
  const [missionsError, setMissionsError] = useState<string | null>(null);

  // Selected mission detail
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [missionTasks, setMissionTasks] = useState<Task[]>([]);
  const [missionEvents, setMissionEvents] = useState<MissionEventRecord[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<'tasks' | 'events'>('tasks');

  // Create mission
  const [newObjective, setNewObjective] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Approval queue
  const [pendingTasks, setPendingTasks] = useState<Task[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);
  const [inflightIds, setInflightIds] = useState<Set<string>>(new Set());

  // Agent roster
  const [agents, setAgents] = useState<AgentSpec[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);

  // Notification status
  const [notifyStatus, setNotifyStatus] = useState<NotifyStatus | null>(null);

  // -------------------------------------------------------------------------
  // Fetch helpers
  // -------------------------------------------------------------------------

  const fetchMissions = useCallback(async () => {
    try {
      const resp = await apiFetch('/v1/missions');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setMissions(data.missions ?? []);
      setMissionsError(null);
    } catch (e) {
      setMissionsError(String(e));
    } finally {
      setMissionsLoading(false);
    }
  }, []);

  const fetchPending = useCallback(async () => {
    try {
      const resp = await apiFetch('/v1/tasks/pending-approval');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setPendingTasks(data.tasks ?? []);
    } catch {
      // silent — panel stays with stale data
    } finally {
      setPendingLoading(false);
    }
  }, []);

  const fetchMissionDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    try {
      const resp = await apiFetch(`/v1/missions/${id}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setMissionTasks(data.tasks ?? []);
      const evResp = await apiFetch(`/v1/missions/${id}/events`);
      if (evResp.ok) {
        const evData = await evResp.json();
        setMissionEvents([...(evData.events ?? [])].reverse());
      }
    } catch {
      // silent — keep stale data
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const fetchAgents = useCallback(async () => {
    try {
      const resp = await apiFetch('/v1/agents');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setAgents(data.agents ?? []);
    } catch {
      // silent
    } finally {
      setAgentsLoading(false);
    }
  }, []);

  const fetchNotifyStatus = useCallback(async () => {
    try {
      const resp = await apiFetch('/v1/notify/status');
      if (resp.ok) setNotifyStatus(await resp.json());
    } catch {
      // silent
    }
  }, []);

  // -------------------------------------------------------------------------
  // Effects
  // -------------------------------------------------------------------------

  // Poll missions every 15 s
  useEffect(() => {
    fetchMissions();
    const id = setInterval(fetchMissions, 15_000);
    return () => clearInterval(id);
  }, [fetchMissions]);

  // Poll pending approvals every 10 s
  useEffect(() => {
    fetchPending();
    const id = setInterval(fetchPending, 10_000);
    return () => clearInterval(id);
  }, [fetchPending]);

  // Fetch agents once on mount
  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // Fetch notify status once on mount
  useEffect(() => {
    fetchNotifyStatus();
  }, [fetchNotifyStatus]);

  // Refresh detail when selection changes
  useEffect(() => {
    if (!selectedId) {
      setMissionTasks([]);
      setMissionEvents([]);
      return;
    }
    fetchMissionDetail(selectedId);
  }, [selectedId, fetchMissionDetail]);

  // -------------------------------------------------------------------------
  // Action handlers
  // -------------------------------------------------------------------------

  const handleCreateMission = async () => {
    if (!newObjective.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const resp = await apiFetch('/v1/missions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective: newObjective.trim(), title: '', owner: 'Bryan' }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setNewObjective('');
      await fetchMissions();
      setSelectedId((data as { mission: { id: string } }).mission.id);
    } catch (e) {
      setCreateError(String(e));
    } finally {
      setCreating(false);
    }
  };

  const handleApprove = async (taskId: string) => {
    const key = `approve-${taskId}`;
    setInflightIds(prev => new Set([...prev, key]));
    try {
      const resp = await apiFetch(`/v1/tasks/${taskId}/approve`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (resp.ok) {
        await Promise.all([
          fetchPending(),
          fetchMissions(),
          selectedId ? fetchMissionDetail(selectedId) : Promise.resolve(),
        ]);
      }
    } catch {
      // silent — polls will refresh
    } finally {
      setInflightIds(prev => {
        const s = new Set(prev);
        s.delete(key);
        return s;
      });
    }
  };

  const handleDeny = async (taskId: string) => {
    const key = `deny-${taskId}`;
    setInflightIds(prev => new Set([...prev, key]));
    try {
      const resp = await apiFetch(`/v1/tasks/${taskId}/deny`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (resp.ok) {
        await Promise.all([
          fetchPending(),
          fetchMissions(),
          selectedId ? fetchMissionDetail(selectedId) : Promise.resolve(),
        ]);
      }
    } catch {
      // silent
    } finally {
      setInflightIds(prev => {
        const s = new Set(prev);
        s.delete(key);
        return s;
      });
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const selectedMission = missions.find(m => m.id === selectedId) ?? null;

  return (
    <div className="flex-1 overflow-y-auto px-6 py-8">
      <div className="max-w-7xl mx-auto space-y-4">

        {/* ── Header ── */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Target size={18} style={{ color: 'var(--color-accent)' }} />
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              Mission Control
            </h1>
          </div>

          {/* Notification status chips */}
          <div className="flex items-center gap-2 text-xs">
            {notifyStatus ? (
              <>
                <span
                  className="flex items-center gap-1 px-2 py-1 rounded-full"
                  style={{
                    background: notifyStatus.slack.ready
                      ? 'color-mix(in srgb, var(--color-success, #22c55e) 10%, var(--color-bg-secondary))'
                      : 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border)',
                    color: notifyStatus.slack.ready
                      ? 'var(--color-success, #22c55e)'
                      : 'var(--color-text-tertiary)',
                  }}
                >
                  {notifyStatus.slack.ready ? <Bell size={11} /> : <BellOff size={11} />}
                  Slack
                </span>
                <span
                  className="flex items-center gap-1 px-2 py-1 rounded-full"
                  style={{
                    background: notifyStatus.telegram.ready
                      ? 'color-mix(in srgb, var(--color-success, #22c55e) 10%, var(--color-bg-secondary))'
                      : 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border)',
                    color: notifyStatus.telegram.ready
                      ? 'var(--color-success, #22c55e)'
                      : 'var(--color-text-tertiary)',
                  }}
                >
                  {notifyStatus.telegram.ready ? <Bell size={11} /> : <BellOff size={11} />}
                  Telegram
                </span>
              </>
            ) : (
              <span style={{ color: 'var(--color-text-tertiary)' }}>Checking notifications…</span>
            )}
          </div>
        </div>

        {/* ── Top row: Mission list + Detail ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

          {/* Missions panel (40 %) */}
          <div className="lg:col-span-2">
            <Panel title="Missions">
              {/* Create form */}
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={newObjective}
                  onChange={e => setNewObjective(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCreateMission(); }}
                  placeholder="Describe a new mission objective…"
                  disabled={creating}
                  className="flex-1 text-xs px-2 py-1.5 rounded-lg outline-none"
                  style={{
                    background: 'var(--color-bg)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text)',
                  }}
                />
                <button
                  onClick={handleCreateMission}
                  disabled={creating || !newObjective.trim()}
                  className="px-3 py-1.5 text-xs rounded-lg font-medium disabled:opacity-40 cursor-pointer flex items-center gap-1"
                  style={{ background: 'var(--color-accent)', color: '#fff' }}
                >
                  {creating ? <Loader2 size={12} className="animate-spin" /> : 'Create'}
                </button>
              </div>

              {createError && (
                <p className="text-xs mb-2" style={{ color: 'var(--color-error, #ef4444)' }}>
                  {createError}
                </p>
              )}

              {/* List */}
              {missionsLoading ? (
                <div className="flex justify-center py-4">
                  <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
                </div>
              ) : missionsError ? (
                <div className="text-xs py-2" style={{ color: 'var(--color-error, #ef4444)' }}>
                  Server unreachable — start <code>jarvis serve</code>
                </div>
              ) : missions.length === 0 ? (
                <EmptyState text="No missions yet — create one above" />
              ) : (
                <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                  {missions.map(m => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedId(m.id)}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs transition-colors cursor-pointer"
                      style={{
                        background: selectedId === m.id ? 'var(--color-accent-subtle)' : 'var(--color-bg)',
                        border: `1px solid ${selectedId === m.id ? 'var(--color-accent)' : 'var(--color-border)'}`,
                        color: 'var(--color-text)',
                      }}
                    >
                      <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                        <StatusBadge status={m.status} />
                        <RiskBadge risk={m.risk_level} />
                      </div>
                      <div className="font-medium truncate">{m.title || m.objective}</div>
                      <div className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
                        {m.linked_task_ids?.length ?? 0} task(s)
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          {/* Mission detail panel (60 %) */}
          <div className="lg:col-span-3">
            <Panel title={selectedMission ? (selectedMission.title || selectedMission.objective) : 'Mission Detail'}>
              {!selectedMission ? (
                <EmptyState text="Select a mission to view tasks and events" />
              ) : (
                <>
                  {/* Mission meta */}
                  <div className="flex items-center gap-2 flex-wrap mb-3">
                    <StatusBadge status={selectedMission.status} />
                    <RiskBadge risk={selectedMission.risk_level} />
                    {selectedMission.summary && (
                      <span className="text-[10px] truncate" style={{ color: 'var(--color-text-tertiary)' }}>
                        {selectedMission.summary}
                      </span>
                    )}
                  </div>

                  {/* Tabs */}
                  <div className="flex items-center gap-1 mb-3">
                    {(['tasks', 'events'] as const).map(tab => (
                      <button
                        key={tab}
                        onClick={() => setDetailTab(tab)}
                        className="px-3 py-1 text-xs rounded-lg capitalize cursor-pointer"
                        style={{
                          background: detailTab === tab ? 'var(--color-accent-subtle)' : 'transparent',
                          color: detailTab === tab ? 'var(--color-text)' : 'var(--color-text-secondary)',
                          fontWeight: detailTab === tab ? 500 : 400,
                        }}
                      >
                        {tab}
                      </button>
                    ))}
                    {detailLoading && (
                      <Loader2
                        size={12}
                        className="animate-spin ml-1"
                        style={{ color: 'var(--color-text-tertiary)' }}
                      />
                    )}
                  </div>

                  {/* Tasks tab */}
                  {detailTab === 'tasks' && (
                    missionTasks.length === 0 ? (
                      <EmptyState text="No tasks for this mission" />
                    ) : (
                      <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                        {missionTasks.map(task => (
                          <div
                            key={task.id}
                            className="px-3 py-2 rounded-lg"
                            style={{
                              background: 'var(--color-bg)',
                              border: '1px solid var(--color-border)',
                            }}
                          >
                            <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
                              <StatusBadge status={task.status} />
                              <RiskBadge risk={task.risk_level} />
                              <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                                → {task.assigned_agent_id}
                              </span>
                            </div>
                            <div className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                              {task.title}
                            </div>
                          </div>
                        ))}
                      </div>
                    )
                  )}

                  {/* Events tab */}
                  {detailTab === 'events' && (
                    missionEvents.length === 0 ? (
                      <EmptyState text="No events yet" />
                    ) : (
                      <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
                        {missionEvents.map(evt => (
                          <div
                            key={evt.event_id}
                            className="px-2 py-1.5 rounded"
                            style={{ background: 'var(--color-bg)' }}
                          >
                            <div className="flex items-center gap-1.5 text-xs">
                              <span
                                className="text-[10px] font-mono shrink-0"
                                style={{
                                  color:
                                    evt.severity === 'warning'
                                      ? '#f59e0b'
                                      : evt.severity === 'error' || evt.severity === 'critical'
                                      ? 'var(--color-error, #ef4444)'
                                      : 'var(--color-accent)',
                                }}
                              >
                                {evt.event_type}
                              </span>
                              <span
                                className="truncate"
                                style={{ color: 'var(--color-text-secondary)' }}
                              >
                                {evt.message}
                              </span>
                            </div>
                            <div
                              className="text-[10px] mt-0.5"
                              style={{ color: 'var(--color-text-tertiary)' }}
                            >
                              {new Date(evt.created_at * 1000).toLocaleTimeString()}
                            </div>
                          </div>
                        ))}
                      </div>
                    )
                  )}
                </>
              )}
            </Panel>
          </div>
        </div>

        {/* ── Bottom row: Approval Queue + Agent Roster ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* Approval queue */}
          <Panel title="Approval Queue">
            {pendingLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
              </div>
            ) : pendingTasks.length === 0 ? (
              <EmptyState text="No pending approvals" />
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {pendingTasks.map(task => {
                  const approving = inflightIds.has(`approve-${task.id}`);
                  const denying = inflightIds.has(`deny-${task.id}`);
                  const busy = approving || denying;
                  return (
                    <div
                      key={task.id}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg"
                      style={{
                        background: 'var(--color-bg)',
                        border: '1px solid color-mix(in srgb, #f59e0b 25%, var(--color-border))',
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <div
                          className="text-xs font-medium truncate"
                          style={{ color: 'var(--color-text)' }}
                        >
                          {task.title}
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span
                            className="text-[10px]"
                            style={{ color: 'var(--color-text-tertiary)' }}
                          >
                            {task.assigned_agent_id}
                          </span>
                          <RiskBadge risk={task.risk_level} />
                        </div>
                      </div>
                      <div className="flex gap-1 shrink-0">
                        <button
                          onClick={() => handleApprove(task.id)}
                          disabled={busy}
                          title="Approve"
                          className="p-1.5 rounded-lg disabled:opacity-40 cursor-pointer"
                          style={{
                            background: 'color-mix(in srgb, var(--color-success, #22c55e) 12%, transparent)',
                            color: 'var(--color-success, #22c55e)',
                          }}
                        >
                          {approving
                            ? <Loader2 size={12} className="animate-spin" />
                            : <Check size={12} />
                          }
                        </button>
                        <button
                          onClick={() => handleDeny(task.id)}
                          disabled={busy}
                          title="Deny"
                          className="p-1.5 rounded-lg disabled:opacity-40 cursor-pointer"
                          style={{
                            background: 'color-mix(in srgb, var(--color-error, #ef4444) 12%, transparent)',
                            color: 'var(--color-error, #ef4444)',
                          }}
                        >
                          {denying
                            ? <Loader2 size={12} className="animate-spin" />
                            : <X size={12} />
                          }
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          {/* Agent roster */}
          <Panel title="Agent Roster">
            {agentsLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
              </div>
            ) : agents.length === 0 ? (
              <EmptyState text="Agent registry unavailable" />
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {agents.map(agent => (
                  <div
                    key={agent.agent_id}
                    className="flex items-center justify-between px-3 py-1.5 rounded-lg"
                    style={{ background: 'var(--color-bg)' }}
                  >
                    <div className="min-w-0">
                      <div
                        className="text-xs font-medium"
                        style={{ color: 'var(--color-text)' }}
                      >
                        {agent.display_name}
                      </div>
                      <div
                        className="text-[10px]"
                        style={{ color: 'var(--color-text-tertiary)' }}
                      >
                        {agent.role} · {agent.permission_level}
                      </div>
                    </div>
                    <StatusBadge status={agent.status} />
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

      </div>
    </div>
  );
}
