/**
 * UniversalComposer — Plan 2 front door.
 *
 * Shown/hidden via Cmd+K or Esc. Accepts text, files, images, slash commands,
 * approvals, project switching, search/history. Voice integrated via
 * useVoiceTurn — not patched on the side.
 *
 * Voice mic stays separate from the text input (voice on/off only).
 * Speak command lives inside composer flow.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import {
  Send,
  Square,
  Paperclip,
  Search,
  Code2,
  Loader2,
  Mic,
  MicOff,
  Volume2,
  Brain,
  AlertTriangle,
  X,
  Play,
  ChevronDown,
  ChevronRight,
  Hash,
  Settings,
  BarChart3,
  Target,
  Database,
  Bot,
  ScrollText,
  Rocket,
  Image,
  FileText,
  Terminal,
  Bell,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAppStore, generateId } from '../lib/store';
import { streamChat, streamResearch } from '../lib/sse';
import { apiFetch, fetchSavings, getBase } from '../lib/api';
import { useVoiceTurn, type TurnPhase } from '../hooks/useVoiceTurn';
import { useSpeech } from '../hooks/useSpeech';
import type {
  ChatMessage,
  MessageTelemetry,
  ResearchSearchTrace,
  ResearchSource,
  TokenUsage,
  ToolCallInfo,
} from '../types';

const WORKBENCH_FRONTDOOR_KEY = 'openjarvis-workbench-frontdoor';
const DEFAULT_WORKBENCH_REPO = '/Users/user/OpenJarvis';

// ---------------------------------------------------------------------------
// Slash commands registry
// ---------------------------------------------------------------------------

interface SlashCommand {
  name: string;
  description: string;
  icon: React.ReactNode;
  action?: 'navigate' | 'toggle';
  path?: string;
}

const SLASH_COMMANDS: SlashCommand[] = [
  { name: '/research', description: 'Toggle deep research mode', icon: <Search size={14} />, action: 'toggle' },
  { name: '/workbench', description: 'Plan in workbench', icon: <Code2 size={14} />, action: 'navigate', path: '/workbench' },
  { name: '/agents', description: 'View agents', icon: <Bot size={14} />, action: 'navigate', path: '/agents' },
  { name: '/dashboard', description: 'Dashboard', icon: <BarChart3 size={14} />, action: 'navigate', path: '/dashboard' },
  { name: '/mission', description: 'Mission Control', icon: <Target size={14} />, action: 'navigate', path: '/mission-control' },
  { name: '/logs', description: 'System logs', icon: <ScrollText size={14} />, action: 'navigate', path: '/logs' },
  { name: '/data', description: 'Data sources', icon: <Database size={14} />, action: 'navigate', path: '/data-sources' },
  { name: '/settings', description: 'Settings', icon: <Settings size={14} />, action: 'navigate', path: '/settings' },
  { name: '/start', description: 'Get started', icon: <Rocket size={14} />, action: 'navigate', path: '/get-started' },
];

// ---------------------------------------------------------------------------
// Voice state label
// ---------------------------------------------------------------------------

const TURN_LABEL: Record<TurnPhase, string> = {
  idle: 'Ready — press Speak',
  recording: 'Recording…',
  waiting_for_silence: 'Waiting for silence…',
  transcribing: 'Transcribing…',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
  error: 'Voice error',
  cancelled: 'Cancelled',
};

function VoiceStateIcon({ phase, enabled }: { phase: TurnPhase; enabled: boolean }) {
  const cls = 'w-4 h-4';
  if (!enabled) return <MicOff className={cls} style={{ color: 'var(--color-text-tertiary)' }} />;
  switch (phase) {
    case 'recording':
    case 'waiting_for_silence':
      return <Mic className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    case 'transcribing':
    case 'thinking':
      return <Brain className={cls} style={{ color: 'var(--color-accent)' }} />;
    case 'speaking':
      return <Volume2 className={cls} style={{ color: 'var(--color-success, #22c55e)' }} />;
    case 'error':
      return <AlertTriangle className={cls} style={{ color: 'var(--color-error, #ef4444)' }} />;
    default:
      return <Mic className={cls} style={{ color: 'var(--color-text-secondary)' }} />;
  }
}

// ---------------------------------------------------------------------------
// Main composer
// ---------------------------------------------------------------------------

export function UniversalComposer() {
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<File[]>([]);
  const [slashMatches, setSlashMatches] = useState<SlashCommand[]>([]);
  const [slashIdx, setSlashIdx] = useState(0);
  const [showVoicePanel, setShowVoicePanel] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const navigate = useNavigate();
  const composerOpen = useAppStore((s) => s.composerOpen);
  const setComposerOpen = useAppStore((s) => s.setComposerOpen);
  const activeId = useAppStore((s) => s.activeId);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const streamState = useAppStore((s) => s.streamState);
  const speechEnabled = useAppStore((s) => s.settings.speechEnabled);
  const maxTokens = useAppStore((s) => s.settings.maxTokens);
  const temperature = useAppStore((s) => s.settings.temperature);
  const createConversation = useAppStore((s) => s.createConversation);
  const addMessage = useAppStore((s) => s.addMessage);
  const updateLastAssistant = useAppStore((s) => s.updateLastAssistant);
  const setStreamState = useAppStore((s) => s.setStreamState);
  const resetStream = useAppStore((s) => s.resetStream);
  const modelLoading = useAppStore((s) => s.modelLoading);
  const deepResearch = useAppStore((s) => s.deepResearch);
  const setDeepResearch = useAppStore((s) => s.setDeepResearch);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);

  // Voice turn
  const {
    voiceEnabled,
    enableVoice,
    disableVoice,
    phase: voicePhase,
    lastError: voiceError,
    startTurn,
    cancelTurn,
    endRecordingNow,
  } = useVoiceTurn();

  const isRecording = voicePhase === 'recording' || voicePhase === 'waiting_for_silence';
  const isActiveTurn = voicePhase !== 'idle' && voicePhase !== 'error' && voicePhase !== 'cancelled';

  // Dictation speech (for text field)
  const { state: speechState, error: speechError, available: speechAvailable, startRecording, stopRecording } = useSpeech();

  useEffect(() => {
    if (speechError) toast.error(speechError);
  }, [speechError]);

  // Focus textarea when composer opens; read prefill from sessionStorage
  useEffect(() => {
    if (composerOpen) {
      const prefill = sessionStorage.getItem('composer-prefill');
      if (prefill) {
        setInput(prefill);
        sessionStorage.removeItem('composer-prefill');
      }
      setTimeout(() => {
        textareaRef.current?.focus();
        // Place cursor at end
        const el = textareaRef.current;
        if (el) el.selectionStart = el.selectionEnd = el.value.length;
      }, 50);
    } else {
      setInput('');
      setAttachments([]);
      setSlashMatches([]);
    }
  }, [composerOpen]);

  // Slash command matching
  useEffect(() => {
    if (input.startsWith('/') && !input.includes(' ')) {
      const q = input.toLowerCase();
      setSlashMatches(SLASH_COMMANDS.filter((c) => c.name.startsWith(q)));
      setSlashIdx(0);
    } else {
      setSlashMatches([]);
    }
  }, [input]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  }, [input]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    resetStream();
  }, [resetStream]);

  const sendMessage = useCallback(async () => {
    const content = input.trim();
    if (!content || streamState.isStreaming) return;
    if (!selectedModel) {
      toast.error('Pick a model first (⌘K → model)');
      return;
    }

    setInput('');
    setAttachments([]);
    setComposerOpen(false);

    let convId = activeId;
    if (!convId) {
      convId = createConversation(selectedModel);
    }

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    addMessage(convId, userMsg);

    const currentMessages = useAppStore.getState().messages;
    const apiMessages = currentMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const assistantMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isResearch: deepResearch || undefined,
    };
    addMessage(convId, assistantMsg);

    const startTime = Date.now();
    const timer = setInterval(() => {
      setStreamState({ elapsedMs: Date.now() - startTime });
    }, 100);
    timerRef.current = timer;

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedContent = '';
    let usage: TokenUsage | undefined;
    const toolCalls: ToolCallInfo[] = [];
    const researchTraces: ResearchSearchTrace[] = [];
    const researchSourcesByRef = new Map<number, ResearchSource>();
    const flushSources = () =>
      Array.from(researchSourcesByRef.values()).sort((a, b) => a.ref - b.ref);
    let lastFlush = 0;
    let ttftMs: number | undefined;

    setStreamState({
      isStreaming: true,
      phase: deepResearch ? 'Researching...' : 'Generating...',
      elapsedMs: 0,
      activeToolCalls: [],
      content: '',
    });

    useAppStore.getState().addLogEntry({
      timestamp: Date.now(),
      level: 'info',
      category: 'chat',
      message: deepResearch
        ? `Research: "${content.slice(0, 80)}${content.length > 80 ? '...' : ''}"`
        : `Request: "${content.slice(0, 80)}${content.length > 80 ? '...' : ''}" → ${selectedModel}`,
    });

    try {
      if (deepResearch) {
        for await (const ev of streamResearch(content, controller.signal)) {
          if (ev.type === 'search_call') {
            const trace: ResearchSearchTrace = {
              id: generateId(),
              query: ev.arguments?.query ?? '',
              person: ev.arguments?.person,
              timeRange: ev.arguments?.time_range,
              status: 'pending',
            };
            researchTraces.push(trace);
            setStreamState({ phase: `Searching: ${trace.query}` });
            updateLastAssistant(convId, accumulatedContent, undefined, undefined, undefined, undefined, [...researchTraces], flushSources());
          } else if (ev.type === 'search_result') {
            const pending = [...researchTraces].reverse().find((t) => t.status === 'pending');
            if (pending) {
              pending.status = 'complete';
              pending.numHits = ev.num_hits;
              pending.topTitles = ev.top_titles;
            }
            if (ev.sources) {
              for (const src of ev.sources) {
                if (src && typeof src.ref === 'number' && !researchSourcesByRef.has(src.ref)) {
                  researchSourcesByRef.set(src.ref, src);
                }
              }
            }
            updateLastAssistant(convId, accumulatedContent, undefined, undefined, undefined, undefined, [...researchTraces], flushSources());
          } else if (ev.type === 'synthesis') {
            if (!ttftMs) ttftMs = Date.now() - startTime;
            accumulatedContent += ev.text ?? '';
            setStreamState({ content: accumulatedContent });
            const now = Date.now();
            if (now - lastFlush >= 80) {
              updateLastAssistant(convId, accumulatedContent, undefined, undefined, undefined, undefined, [...researchTraces], flushSources());
              lastFlush = now;
            }
          } else if (ev.type === 'done') {
            usage = ev.usage;
          }
        }
      } else {
        const res = await fetch(`${getBase()}/v1/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: apiMessages,
            model: selectedModel,
            stream: true,
            temperature,
            max_tokens: maxTokens,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.text();
          throw new Error(`API error ${res.status}: ${err}`);
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let buf = '';

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const lines = buf.split('\n');
            buf = lines.pop() ?? '';
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              const raw = line.slice(6).trim();
              if (raw === '[DONE]') break;
              try {
                const data = JSON.parse(raw);
                const delta = data.choices?.[0]?.delta?.content;
                if (delta) {
                  if (!ttftMs) ttftMs = Date.now() - startTime;
                  accumulatedContent += delta;
                  setStreamState({ content: accumulatedContent });
                  const now = Date.now();
                  if (now - lastFlush >= 80) {
                    updateLastAssistant(convId, accumulatedContent, toolCalls.length > 0 ? [...toolCalls] : undefined);
                    lastFlush = now;
                  }
                }
                if (data.usage) usage = data.usage;
                if (data.choices?.[0]?.finish_reason === 'stop') break;
              } catch {}
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        if (!accumulatedContent) accumulatedContent = '(Generation stopped)';
      } else {
        const errMsg = err?.message || String(err);
        accumulatedContent = accumulatedContent || `Error: ${errMsg}`;
        useAppStore.getState().addLogEntry({
          timestamp: Date.now(), level: 'error', category: 'chat',
          message: `Stream error: ${errMsg}`,
        });
      }
      useAppStore.getState().setLiveEnergy(null);
    } finally {
      if (!accumulatedContent) {
        accumulatedContent = 'No response was generated. Please try again.';
      }
      const totalMs = Date.now() - startTime;
      const _CLOUD_PREFIXES = ['gpt-', 'o1-', 'o3-', 'o4-', 'claude-', 'gemini-', 'openrouter/', 'MiniMax-', 'chatgpt-'];
      const engineLabel = _CLOUD_PREFIXES.some((p) => selectedModel.startsWith(p)) ? 'cloud' : 'ollama';
      const telemetry: MessageTelemetry = {
        engine: engineLabel,
        model_id: selectedModel,
        total_ms: totalMs,
        ttft_ms: ttftMs,
        tokens_per_sec: usage?.completion_tokens ? usage.completion_tokens / (totalMs / 1000) : undefined,
      };
      let audioMeta: { url: string } | undefined;
      try {
        const digestRes = await fetch(`${getBase()}/api/digest`);
        if (digestRes.ok) {
          const digest = await digestRes.json();
          if (digest.audio_available) audioMeta = { url: `${getBase()}/api/digest/audio` };
        }
      } catch {}

      updateLastAssistant(
        convId,
        accumulatedContent,
        toolCalls.length > 0 ? toolCalls : undefined,
        usage,
        telemetry,
        audioMeta,
        researchTraces.length > 0 ? researchTraces : undefined,
        researchSourcesByRef.size > 0 ? flushSources() : undefined,
      );
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
      resetStream();
      abortRef.current = null;
      if (!deepResearch) {
        fetchSavings().then((data) => useAppStore.getState().setSavings(data)).catch(() => {});
      }
    }
  }, [
    input, activeId, selectedModel, streamState.isStreaming, createConversation,
    addMessage, updateLastAssistant, setStreamState, resetStream, deepResearch,
    temperature, maxTokens, setComposerOpen,
  ]);

  const planInWorkbench = useCallback(async () => {
    const content = input.trim();
    if (!content || streamState.isStreaming) return;
    try {
      const res = await apiFetch('/v1/workbench/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: content, repo_path: DEFAULT_WORKBENCH_REPO, dry_run: true, stop_on_blocker: true }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok || !data.plan) throw new Error(data?.detail ?? `Workbench plan failed (${res.status})`);
      window.localStorage.setItem(WORKBENCH_FRONTDOOR_KEY, JSON.stringify({
        prompt: content, repoPath: DEFAULT_WORKBENCH_REPO, dryRun: true, stopOnBlocker: true,
        plan: data.plan, createdAt: Date.now(),
      }));
      toast.success('Workbench plan created');
      setComposerOpen(false);
      navigate('/workbench');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Workbench plan failed');
    }
  }, [input, navigate, streamState.isStreaming, setComposerOpen]);

  const handleSlashSelect = useCallback((cmd: SlashCommand) => {
    if (cmd.action === 'navigate' && cmd.path) {
      setComposerOpen(false);
      navigate(cmd.path);
    } else if (cmd.name === '/research') {
      setDeepResearch(!deepResearch);
      setInput('');
    }
    setSlashMatches([]);
  }, [navigate, setComposerOpen, deepResearch, setDeepResearch]);

  const handleFileAttach = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) setAttachments((prev) => [...prev, ...files]);
    e.target.value = '';
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      if (slashMatches.length > 0) { setSlashMatches([]); return; }
      setComposerOpen(false);
      return;
    }
    if (slashMatches.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSlashIdx((i) => Math.min(i + 1, slashMatches.length - 1)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSlashIdx((i) => Math.max(i - 1, 0)); return; }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); handleSlashSelect(slashMatches[slashIdx]); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }, [slashMatches, slashIdx, handleSlashSelect, sendMessage, setComposerOpen]);

  if (!composerOpen) return null;

  const hasInput = input.trim().length > 0 || attachments.length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
        animation: 'p2-mode-b-in var(--p2-dur-base) var(--p2-ease-smooth)',
      }}
      onClick={() => setComposerOpen(false)}
    >
      <div
        className="relative w-full mx-4 rounded-2xl overflow-hidden flex flex-col"
        style={{
          maxWidth: '680px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--p2-elev-4), var(--p2-glow-teal)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Top bar: wordmark + model pill + mode badges ── */}
        <div
          className="flex items-center justify-between px-4 py-2.5 gap-3"
          style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
        >
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            {/* Teal dot wordmark */}
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: 'var(--p2-teal)', boxShadow: 'var(--p2-glow-teal)' }}
            />
            <span className="text-[11px] font-semibold tracking-[0.18em]" style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-hud)' }}>
              JARVIS
            </span>
            {selectedModel && (
              <button
                onClick={() => { setComposerOpen(false); setCommandPaletteOpen(true); }}
                className="text-[10px] px-2 py-0.5 rounded-full transition-all cursor-pointer truncate max-w-[160px]"
                style={{
                  background: 'var(--color-bg-tertiary)',
                  color: 'var(--color-text-tertiary)',
                  border: '1px solid var(--color-border)',
                }}
                title="Switch model"
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--p2-teal)'; e.currentTarget.style.color = 'var(--p2-teal)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-tertiary)'; }}
              >
                {selectedModel.length > 26 ? selectedModel.slice(0, 26) + '…' : selectedModel}
              </button>
            )}
            {deepResearch && (
              <span
                className="text-[10px] px-2 py-0.5 rounded-full shrink-0"
                style={{ background: 'var(--p2-teal-dim)', color: 'var(--p2-teal)', border: '1px solid var(--p2-teal)' }}
              >
                Research
              </span>
            )}
          </div>
          <button
            onClick={() => setComposerOpen(false)}
            className="p-1 rounded-lg cursor-pointer shrink-0"
            style={{ color: 'var(--color-text-tertiary)' }}
            title="Close (Esc)"
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-bg-tertiary)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            <X size={14} />
          </button>
        </div>

        {/* ── Slash command suggestions ── */}
        {slashMatches.length > 0 && (
          <div
            className="px-2 py-1"
            style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            {slashMatches.map((cmd, i) => (
              <button
                key={cmd.name}
                onClick={() => handleSlashSelect(cmd)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors cursor-pointer"
                style={{
                  background: i === slashIdx ? 'var(--color-accent-subtle)' : 'transparent',
                  color: i === slashIdx ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                }}
                onMouseEnter={() => setSlashIdx(i)}
              >
                <span style={{ color: i === slashIdx ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}>
                  {cmd.icon}
                </span>
                <span className="text-sm font-medium">{cmd.name}</span>
                <span className="text-xs ml-auto" style={{ color: 'var(--color-text-tertiary)' }}>{cmd.description}</span>
              </button>
            ))}
          </div>
        )}

        {/* ── Main text input ── */}
        <div className="px-4 pt-4 pb-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              !selectedModel
                ? 'Pick a model first — press model button above…'
                : deepResearch
                ? 'Ask anything — deep research mode…'
                : 'Message Jarvis… or type / for commands'
            }
            rows={1}
            className="w-full bg-transparent outline-none resize-none text-base leading-relaxed"
            style={{ color: 'var(--color-text)', maxHeight: '180px', minHeight: '28px' }}
            disabled={streamState.isStreaming || modelLoading}
          />
        </div>

        {/* ── Attachment chips ── */}
        {attachments.length > 0 && (
          <div className="px-4 pb-2 flex flex-wrap gap-2">
            {attachments.map((f, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
                style={{ background: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
              >
                {f.type.startsWith('image/') ? <Image size={11} /> : <FileText size={11} />}
                <span className="max-w-[120px] truncate">{f.name}</span>
                <button
                  onClick={() => setAttachments((a) => a.filter((_, j) => j !== i))}
                  className="cursor-pointer ml-0.5"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── Voice panel (expandable) ── */}
        {showVoicePanel && (
          <div
            className="mx-4 mb-3 rounded-xl overflow-hidden"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
          >
            <div className="px-3 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <VoiceStateIcon phase={voicePhase} enabled={voiceEnabled} />
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {voiceEnabled ? TURN_LABEL[voicePhase] : 'Voice disabled'}
                </span>
                {voiceError && (
                  <span className="text-[11px]" style={{ color: 'var(--color-error)' }}>{voiceError}</span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                {/* Mic on/off toggle */}
                <button
                  onClick={() => voiceEnabled ? disableVoice() : enableVoice()}
                  className="p-1.5 rounded-lg transition-colors cursor-pointer"
                  style={{
                    background: voiceEnabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                    color: voiceEnabled ? '#fff' : 'var(--color-text-secondary)',
                    border: '1px solid var(--color-border)',
                  }}
                  title={voiceEnabled ? 'Turn off voice' : 'Turn on voice'}
                >
                  {voiceEnabled ? <Mic size={13} /> : <MicOff size={13} />}
                </button>
              </div>
            </div>

            {voiceEnabled && (
              <div className="px-3 pb-2.5 flex items-center gap-2">
                {/* Speak now */}
                {!isActiveTurn && (
                  <button
                    onClick={() => startTurn()}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                    style={{ background: 'var(--color-accent)', color: '#fff' }}
                  >
                    <Play size={11} />
                    Speak now
                  </button>
                )}

                {/* Recording controls */}
                {isRecording && (
                  <>
                    <button
                      onClick={() => endRecordingNow()}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                      style={{
                        background: 'color-mix(in srgb, var(--color-success, #22c55e) 12%, transparent)',
                        color: 'var(--color-success, #22c55e)',
                        border: '1px solid color-mix(in srgb, var(--color-success, #22c55e) 25%, transparent)',
                      }}
                    >
                      End &amp; send
                    </button>
                    <button
                      onClick={cancelTurn}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                      style={{
                        background: 'color-mix(in srgb, var(--color-error, #ef4444) 10%, transparent)',
                        color: 'var(--color-error, #ef4444)',
                        border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 25%, transparent)',
                      }}
                    >
                      <X size={11} />
                      Cancel
                    </button>
                  </>
                )}

                {/* Cancel during STT/thinking/speaking */}
                {isActiveTurn && !isRecording && (
                  <button
                    onClick={cancelTurn}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                    style={{
                      background: 'color-mix(in srgb, var(--color-error, #ef4444) 8%, transparent)',
                      color: 'var(--color-error, #ef4444)',
                      border: '1px solid color-mix(in srgb, var(--color-error, #ef4444) 20%, transparent)',
                    }}
                  >
                    <X size={11} />
                    Cancel
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Bottom toolbar ── */}
        <div
          className="flex items-center gap-2 px-4 py-3"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          {/* Left: attach, voice, research toggle */}
          <div className="flex items-center gap-1.5 flex-1">
            {/* File attach */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept="image/*,.txt,.md,.log,.json,.csv,.pdf"
              onChange={handleFileAttach}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
              title="Attach files, images, or logs"
            >
              <Paperclip size={16} />
            </button>

            {/* Voice panel toggle */}
            <button
              onClick={() => setShowVoicePanel((v) => !v)}
              className="p-2 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
              style={{
                color: showVoicePanel || voiceEnabled ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
                background: showVoicePanel ? 'var(--color-accent-subtle)' : 'transparent',
              }}
              title="Voice"
            >
              <Mic size={16} />
              {voiceEnabled && voicePhase !== 'idle' && (
                <span
                  className={`w-1.5 h-1.5 rounded-full ${voicePhase === 'recording' ? 'animate-pulse' : ''}`}
                  style={{
                    background: isRecording ? 'var(--color-error, #ef4444)' : voicePhase === 'speaking' ? 'var(--color-success, #22c55e)' : 'var(--color-accent)',
                  }}
                />
              )}
            </button>

            {/* Deep research toggle */}
            <button
              onClick={() => setDeepResearch(!deepResearch)}
              disabled={streamState.isStreaming}
              className="p-2 rounded-lg transition-colors cursor-pointer"
              style={{
                color: deepResearch ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
                background: deepResearch ? 'var(--color-accent-subtle)' : 'transparent',
              }}
              title={deepResearch ? 'Deep research: on' : 'Deep research: off'}
            >
              <Search size={16} />
            </button>

            {/* Slash hint */}
            <button
              onClick={() => setInput('/')}
              className="hidden sm:flex p-2 rounded-lg transition-colors cursor-pointer"
              style={{ color: 'var(--color-text-tertiary)' }}
              title="Slash commands"
            >
              <Hash size={16} />
            </button>
          </div>

          {/* Right: workbench plan + send/stop */}
          <div className="flex items-center gap-2">
            <button
              onClick={planInWorkbench}
              disabled={!hasInput || streamState.isStreaming}
              className="p-2 rounded-lg transition-colors cursor-pointer disabled:opacity-30"
              style={{
                color: hasInput ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
                background: hasInput ? 'var(--color-bg-tertiary)' : 'transparent',
                border: '1px solid var(--color-border)',
              }}
              title="Create Workbench plan"
            >
              <Code2 size={16} />
            </button>

            {streamState.isStreaming ? (
              <button
                onClick={stopStreaming}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium cursor-pointer"
                style={{ background: 'var(--color-error)', color: '#fff' }}
                title="Stop generating"
              >
                <Square size={14} />
                Stop
              </button>
            ) : (
              <button
                onClick={sendMessage}
                disabled={!hasInput || modelLoading || !selectedModel}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium cursor-pointer disabled:opacity-30 transition-all"
                style={{
                  background: hasInput && selectedModel ? 'var(--p2-teal)' : 'var(--color-bg-tertiary)',
                  color: hasInput && selectedModel ? '#fff' : 'var(--color-text-tertiary)',
                  boxShadow: hasInput && selectedModel ? 'var(--p2-glow-teal)' : 'none',
                }}
                title={selectedModel ? 'Send (Enter)' : 'Pick a model first'}
              >
                <Send size={14} />
                Send
              </button>
            )}
          </div>
        </div>

        {/* ── Footer: hints ── */}
        <div
          className="flex items-center justify-between px-4 py-1.5 gap-4"
          style={{ borderTop: '1px solid var(--color-border)', background: 'var(--color-bg-secondary)' }}
        >
          <span className="text-[10px] truncate" style={{ color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-hud)' }}>
            <kbd className="font-mono">↵</kbd> send ·{' '}
            <kbd className="font-mono">⇧↵</kbd> newline ·{' '}
            <kbd className="font-mono">/</kbd> commands ·{' '}
            <kbd className="font-mono">Esc</kbd> close
          </span>
          {!selectedModel && (
            <button
              onClick={() => { setComposerOpen(false); setCommandPaletteOpen(true); }}
              className="text-[10px] cursor-pointer shrink-0 px-2 py-0.5 rounded-full transition-all"
              style={{
                color: 'var(--p2-amber)',
                background: 'var(--p2-amber-dim)',
                border: '1px solid var(--p2-amber)',
              }}
            >
              Pick a model →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
