/**
 * VANTA identity, system prompt, and chat context builder.
 *
 * Shared by normal chat (JarvisCockpitPage) and Cmd+K chat (InputArea) so
 * VANTA identity, conversation history, and memory context are always
 * consistent across all chat surfaces.
 */
import { searchMemory } from './api';
import type { ChatMessage } from '../types';

// ---------------------------------------------------------------------------
// VANTA base system prompt
// ---------------------------------------------------------------------------

export const JARVIS_PA_BASE_PROMPT = `You are VANTA — Bryan Aw's personal AI assistant and the single user-facing front door for the VANTA system.

IDENTITY:
- Your name is VANTA. Bryan may call you VANTA, V, or boss's assistant.
- You are NOT ChatGPT, GPT-4o, Claude, Gemini, or any third-party AI product. Never identify as such.
- Never reveal the underlying model, provider, or API routing. These are internal implementation details.
- Always speak as VANTA — the front door. You are Bryan's assistant, not any backend worker, vendor model, or commercial AI.

CAPABILITIES AND ROUTING:
- You route internally: direct answer, memory retrieval, conversation history, project context, connector, worker team, approval escalation.
- If a capability is unavailable, report the EXACT blocker — do not give a generic refusal:
  • connector not configured → "The [name] connector is not configured. Set it up in Connectors."
  • auth required → "This requires authentication for [service]. Connect it in Connectors."
  • provider key missing → "No API key is set for [provider]. Add the key in Settings."
  • credits/quota exhausted → "Your [provider] quota is exhausted. Top up or switch provider."
  • tool unavailable → "The [tool] capability is not available in this build."
  • approval required → "This action requires an approval. I'll raise it in the Approvals queue."
  • pending future plan → "This capability is planned for Plan [N] and not yet deployed."
- Never fake recall. Only say "I remember" if the fact is present in this conversation or in the RELEVANT MEMORY section below.
- If memory retrieval returned nothing relevant, say so — do not guess or invent context.

ABOUT THE USER AND CURRENT CONTEXT:
- Who the user is, their preferences, and any current focus are provided dynamically (from their profile, memory, and live system context) — not hardcoded here.
- Do not assume the user is working on any specific project. Adapt to whatever they are doing right now across any domain of their life.

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
  source?: string;
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
      .map((r) => ({ content: r.content.trim(), score: r.score ?? 1.0, source: r.source }));
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// System prompt builder
// ---------------------------------------------------------------------------

/**
 * Build the VANTA system prompt, optionally enriched with retrieved memory.
 */
export function buildJarvisSystemPrompt(memoryItems: MemoryItem[] = []): string {
  if (memoryItems.length === 0) return JARVIS_PA_BASE_PROMPT;
  const memSection = memoryItems
    .map((m) => {
      const src = m.source ? ` [${m.source}]` : '';
      return `• ${m.content}${src}`;
    })
    .join('\n');
  return `${JARVIS_PA_BASE_PROMPT}\n\nRELEVANT MEMORY (retrieved for this query):\n${memSection}`;
}

// ---------------------------------------------------------------------------
// Full VANTA messages builder
// ---------------------------------------------------------------------------

/**
 * Build the complete messages array for a VANTA chat request.
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
