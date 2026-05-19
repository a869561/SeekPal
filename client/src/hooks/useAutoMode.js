const QUESTION_PATTERN = /\b(qué|que|cómo|como|cuándo|cuando|dónde|donde|por\s+qué|cuál|cual|quién|quien|what|how|when|where|why|which|who)\b/i;

/**
 * Heuristic: classify a query as "ask" (RAG) or "search" (classic).
 */
export function classifyQuery(query) {
  const q = query.trim();
  if (!q) return "search";
  if (q.includes("?")) return "ask";
  if (QUESTION_PATTERN.test(q)) return "ask";
  if (q.length > 60) return "ask";
  return "search";
}
