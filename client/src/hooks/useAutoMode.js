/**
 * Clasificador automático de queries: "ask" (respuesta IA) vs "search" (buscar documentos).
 *
 * Orden de evaluación:
 *   1. Señales fuertes de ASK   → pregunta directa, verbo imperativo, frase informativa
 *   2. Señales fuertes de SEARCH → extensión de fichero, código/referencia documental
 *   3. Heurísticas estructurales → longitud de la query
 *   4. Default ambiguo (3–6 palabras) → "ask"
 *      Razonamiento: con búsqueda semántica en ambos modos, "ask" da una respuesta
 *      directa mientras que "search" muestra la lista de documentos relevantes.
 *      Para una base de conocimiento, responder directamente es más útil por defecto.
 */

// ── Señales de ASK ─────────────────────────────────────────────────────────

/** Signo de interrogación (ES o EN) */
const RE_QUESTION_MARK = /[?¿]/;

/** Empieza con palabra interrogativa */
const RE_QUESTION_WORD = /^\s*(qué|que|cómo|como|cuándo|cuando|dónde|donde|por\s+qué|cuál|cual|quién|quien|cuántos?|cuantos?|what|how|when|where|why|which|who|is\s+there|are\s+there|can\s+you)\b/i;

/** Verbos imperativos que indican solicitud de información */
const RE_IMPERATIVE_VERB = /\b(explica|expl[ií]came|resume|res[uú]meme|describe|analiza|compara|lista|extrae|define|diferencia|relaciona|cu[eé]ntame|dime|mu[eé]strame|h[aá]blame|ay[uú]dame|necesito\s+saber|quiero\s+saber|dame\s+información|busca\s+información|tell\s+me|explain|summarize|describe|compare|analyze|show\s+me|help\s+me|find\s+out)\b/i;

/** Frases que implican búsqueda de información (no de fichero) */
const RE_INFO_PHRASE = /\b(qué\s+es|qué\s+son|cómo\s+(es|funciona|se\s+hace|fue|eran)|por\s+qué|para\s+qué|en\s+qué\s+(consiste|se\s+diferencia)|cuál\s+es\s+(la|el)|quién\s+(es|fue|era|inventó|creó|fundó)|qué\s+diferencia|qué\s+(pasó|ocurrió|sucedió)|información\s+(sobre|de|acerca\s+de)|datos\s+sobre|historia\s+de|cómo\s+funciona|how\s+(does|is|was)|what\s+is|who\s+(is|was)|why\s+(is|did|was))\b/i;

// ── Señales de SEARCH ──────────────────────────────────────────────────────

/** Termina con extensión de fichero (.pdf, .docx, .xlsx…) */
const RE_FILE_EXTENSION = /\.\w{2,5}(?:\s|$)/;

/**
 * Patrones de código o referencia documental:
 *   - Código alfanumérico: ABC-1234, REF-00X, EXP 2023/01
 *   - Trimestre + año: Q3 2024
 *   - Identificadores explícitos: ID: 42, ref. 001
 */
const RE_DOC_CODE = /\b([A-Z]{1,4}-?\d{3,}|Q[1-4]\s*\d{4}|ref\.?\s*[\w-]+|ID\s*:?\s*\d+|exp\.?\s*\d{4}[/-]\d+)\b/i;

// ── Clasificador ───────────────────────────────────────────────────────────

/**
 * Clasifica una query como "ask" o "search".
 * @param {string} query
 * @returns {"ask"|"search"}
 */
export function classifyQuery(query) {
  const q = query.trim();
  if (!q) return "search";

  // 1 — Señales fuertes de ASK
  if (RE_QUESTION_MARK.test(q))   return "ask";
  if (RE_QUESTION_WORD.test(q))   return "ask";
  if (RE_IMPERATIVE_VERB.test(q)) return "ask";
  if (RE_INFO_PHRASE.test(q))     return "ask";

  // 2 — Señales fuertes de SEARCH (buscar un fichero concreto)
  if (RE_FILE_EXTENSION.test(q)) return "search";
  if (RE_DOC_CODE.test(q))       return "search";

  // 3 — Heurísticas estructurales (longitud)
  const wordCount = q.split(/\s+/).filter(Boolean).length;

  if (wordCount <= 2) return "search"; // muy corto → probablemente nombre de fichero
  if (wordCount >= 7) return "ask";    // muy largo → seguramente una pregunta o contexto

  // 4 — Zona ambigua (3–6 palabras, sin señales claras) → "ask"
  return "ask";
}
