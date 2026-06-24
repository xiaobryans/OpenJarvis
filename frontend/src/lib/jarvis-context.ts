/**
 * Jarvis PA identity, system prompt, and chat context builder.
 *
 * Shared by normal chat (JarvisCockpitPage) and Cmd+K chat (InputArea) so
 * Jarvis PA identity, conversation history, and memory context are always
 * consistent across all chat surfaces.
 */
import { searchMemory } from './api';
import type { ChatMessage } from '../types';

// ---------------------------------------------------------------------------
// Jarvis PA base system prompt
// ---------------------------------------------------------------------------

export const JARVIS_PA_BASE_PROMPT = `You are Jarvis PA — Bryan Aw's personal AI assistant and the single user-facing front door for the OpenJarvis system.

IDENTITY:
- Your name is Jarvis. Bryan may call you Jarvis, J, or Jarvis PA.
- You are NOT ChatGPT, GPT-4o, Claude, Gemini, or any third-party AI product. Never identify as such.
- Never reveal the underlying model, provider, or API routing. These are internal implementation details.
- Always speak as Jarvis PA — the front door. You are Bryan's assistant, not any backend worker, vendor model, or commercial AI.

CAPABILITIES AND ROUTING:
- You route internally: direct answer, memory retrieval, conversation history, project context, connector, worker team, approval escalation.
- If a capability is unavailable (key missing, connector unconfigured, pending Plan 2/3/4/5+), state the exact blocker clearly and honestly.
- Never fake recall. Only say "I remember" if the fact is present in this conversation or in retrieved memory context below.
- If you cannot retrieve something and have no data, say so directly without guessing.

ACTIVE PROJECT STATUS:
- Plan 1 (desktop cockpit): RUNNING — cloud routing active, openai/gpt-4o default
- Plan 2 (MacBook-off parity): PENDING — cloud runtime not yet deployed
- Apple notarization: ACCEPTED for internal/development builds
- Memory store: Active — 179+ entries, S3 cloud sync enabled
- Connectors: 26 registered, metadata setup required for most

CONVERSATION RULES:
- Remember and use everything in this conversation transcript.
- For follow-up questions, refer back to prior turns naturally without re-asking for information already provided.
- Topic switches do not erase prior context — keep everything from this session unless Bryan explicitly asks to start fresh.`;

// ---------------------------------------------------------------------------
// Memory retrieval with graceful degradation
// ---------------------------------------------------------------------------

export interface MemoryItem {
  content: string;
  score: number;
}

/**
 * Fetch relevant memory items for a query with graceful failure.
 * Returns empty array if memory backend is unavailable.
 */
export async function fetchRelevantMemory(
  query: string,
  topK = 3,
): Promise<MemoryItem[]> {
  try {
    const results = await searchMemory(query, topK);
    return results
      .filter((r) => r.content && r.content.trim().length > 0)
      .map((r) => ({ content: r.content.trim(), score: r.score ?? 1.0 }));
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// System prompt builder
// ---------------------------------------------------------------------------

/**
 * Build the Jarvis PA system prompt, optionally enriched with retrieved memory.
 */
export function buildJarvisSystemPrompt(memoryItems: MemoryItem[] = []): string {
  if (memoryItems.length === 0) return JARVIS_PA_BASE_PROMPT;
  const memSection = memoryItems.map((m) => `• ${m.content}`).join('\n');
  return `${JARVIS_PA_BASE_PROMPT}\n\nRELEVANT MEMORY (retrieved for this query):\n${memSection}`;
}

// ---------------------------------------------------------------------------
// Full Jarvis PA messages builder
// ---------------------------------------------------------------------------

/**
 * Build the complete messages array for a Jarvis PA chat request.
 *
 * @param userMessage  Current user turn text.
 * @param priorTurns   Prior conversation turns (user + assistant) EXCLUDING the
 *                     current user message — to avoid duplication.
 * @param memoryItems  Memory items retrieved for this query.
 */
export function buildJarvisMessages(
  userMessage: string,
  priorTurns: ChatMessage[],
  memoryItems: MemoryItem[] = [],
): Array<{ role: string; content: string }> {
  const systemContent = buildJarvisSystemPrompt(memoryItems);

  const messages: Array<{ role: string; content: string }> = [
    { role: 'system', content: systemContent },
  ];

  // Include prior turns (limit to last 30 to stay within token budget).
  // Skip empty assistant turns (e.g. streaming placeholders that were never filled).
  const history = priorTurns.slice(-30);
  for (const turn of history) {
    if ((turn.role === 'user' || turn.role === 'assistant') && turn.content.trim()) {
      messages.push({ role: turn.role, content: turn.content });
    }
  }

  messages.push({ role: 'user', content: userMessage });
  return messages;
}
