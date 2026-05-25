/**
 * Tests para el clasificador automático useAutoMode.js
 *
 * Ejecutar desde la raíz del proyecto:
 *   node backend/tests/test_auto_mode.mjs
 *
 * No requiere dependencias externas (Node.js nativo).
 */

import { readFileSync } from "fs";
import { fileURLToPath, pathToFileURL } from "url";
import { dirname, join, resolve } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Ruta al módulo bajo prueba (relativa a este fichero)
const HOOK_PATH = resolve(__dirname, "../../client/src/hooks/useAutoMode.js");

// Cargar dinámicamente el módulo ES (es un módulo con export)
let classifyQuery;
try {
  const mod = await import(pathToFileURL(HOOK_PATH));
  classifyQuery = mod.classifyQuery;
} catch (e) {
  console.error(`❌ No se pudo importar useAutoMode.js: ${e.message}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Mini test runner
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;
const failures = [];

function expect(query, expectedMode) {
  const result = classifyQuery(query);
  if (result === expectedMode) {
    passed++;
  } else {
    failed++;
    failures.push(`  FAIL: classifyQuery("${query}") → "${result}" (esperado "${expectedMode}")`);
  }
}

// ══════════════════════════════════════════════════════════════════════════
// Layer 1: Señales fuertes de ASK — signo de interrogación
// ══════════════════════════════════════════════════════════════════════════

expect("¿Qué es el cambio climático?",       "ask");
expect("¿Cómo funciona un motor?",            "ask");
expect("¿Cuándo fue la Revolución Francesa?", "ask");
expect("What is machine learning?",           "ask");
expect("How does Python handle memory?",      "ask");
expect("Is there a summary of the report?",   "ask");

// ── Layer 1: palabras interrogativas sin signo ─────────────────────────

expect("qué es el sistema solar",              "ask");
expect("cómo funciona la fotosíntesis",        "ask");
expect("cuándo ocurrió la Primera Guerra",     "ask");
expect("quién inventó la imprenta",            "ask");
expect("cuántos planetas hay en el sistema solar", "ask");
expect("what is the difference between RAM and ROM", "ask");
expect("how does encryption work",             "ask");
expect("why is the sky blue",                  "ask");

// ── Layer 1: verbos imperativos ───────────────────────────────────────

expect("explica la teoría de la relatividad",  "ask");
expect("resume el informe anual",              "ask");
expect("describe el proceso de fotosíntesis",  "ask");
expect("analiza los resultados del estudio",   "ask");
expect("compara las distintas propuestas",     "ask");
expect("lista las causas del cambio climático","ask");
expect("dime cuáles son los requisitos",       "ask");
expect("tell me about the project deadline",   "ask");
expect("explain the budget breakdown",         "ask");

// ── Layer 1: frases informativas ─────────────────────────────────────

expect("qué es la inteligencia artificial",    "ask");
expect("qué son los anticuerpos monoclonales", "ask");
expect("cómo funciona el corazón",             "ask");
expect("información sobre el Acuerdo de París","ask");
expect("historia de la computación",           "ask");
expect("cómo se hace la pasta carbonara",      "ask");
expect("what is the capital of Germany",       "ask");

// ══════════════════════════════════════════════════════════════════════════
// Layer 2: Señales fuertes de SEARCH — extensión de fichero
// ══════════════════════════════════════════════════════════════════════════

expect("informe_anual_2024.pdf",               "search");
expect("presupuesto.xlsx",                     "search");
expect("contrato_empresa.docx",                "search");
expect("presentacion_board.pptx",              "search");
expect("readme.md",                            "search");
expect("notas.txt",                            "search");
expect("economia_basica.doc",                  "search");
expect("foto_reunion.jpg",                     "search");
expect("video_demo.mp4",                       "search");

// ── Layer 2: códigos de documento ─────────────────────────────────────

expect("EXP 2024/001",                         "search");
expect("REF-20230415",                         "search");
expect("ID: 12345",                            "search");
expect("Q3 2023",                              "search");
expect("ABC-999",                              "search");

// ══════════════════════════════════════════════════════════════════════════
// Layer 3: Heurísticas de longitud
// ══════════════════════════════════════════════════════════════════════════

// ≤ 2 palabras → search
expect("python",                               "search");
expect("informe anual",                        "search");
expect("machine learning",                     "search");
expect("budget 2024",                          "search");

// ≥ 7 palabras (sin señales ask/search) → ask
expect("necesito información detallada sobre el proyecto nuevo del departamento", "ask");
expect("the quarterly results for the european division last year", "ask");
expect("cuál fue el resultado del análisis de riesgos del tercer trimestre", "ask");

// ══════════════════════════════════════════════════════════════════════════
// Layer 4: Zona ambigua (3-6 palabras sin señales) → "ask"
// ══════════════════════════════════════════════════════════════════════════

expect("impacto del cambio climático",         "ask");
expect("energías renovables en Europa",        "ask");
expect("evolución de la IA",                   "ask");
expect("deep learning neural networks",        "ask");
expect("sistema solar planetas satélites",     "ask");
expect("política monetaria banco central",     "ask");

// ══════════════════════════════════════════════════════════════════════════
// Casos del dataset de evaluación (qa_dataset.json)
// ══════════════════════════════════════════════════════════════════════════

// Preguntas directas del dataset → ask
expect("¿Qué porcentaje de la masa del sistema solar concentra el Sol?", "ask");
expect("¿Qué lenguaje de programación creó Guido van Rossum?",            "ask");
expect("¿Cuántos países firmaron el Acuerdo de París?",                   "ask");
expect("¿Qué fue ARPANET?",                                              "ask");
expect("¿Cuántas válvulas de vacío tenía el ENIAC?",                     "ask");
expect("¿Qué organelo celular produce energía en forma de ATP?",         "ask");
expect("¿Quién enunció el principio de incertidumbre?",                  "ask");

// Búsquedas de fichero → search
expect("economia_basica.doc",                  "search");
expect("historia_computacion.epub",            "search");
expect("tabla_periodica.ods",                  "search");

// ══════════════════════════════════════════════════════════════════════════
// Casos edge
// ══════════════════════════════════════════════════════════════════════════

expect("",                                     "search");  // vacío → search
expect("   ",                                  "search");  // solo espacios → search (trim → vacío)
expect("a",                                    "search");  // 1 palabra muy corta
expect("ab cd",                                "search");  // 2 palabras

// ══════════════════════════════════════════════════════════════════════════
// Resultados
// ══════════════════════════════════════════════════════════════════════════

const total = passed + failed;
console.log(`\n${"═".repeat(60)}`);
console.log(`Auto-mode classifier — ${total} tests`);
console.log(`${"═".repeat(60)}`);
console.log(`  ✅ Passed: ${passed}`);
if (failed > 0) {
  console.log(`  ❌ Failed: ${failed}`);
  console.log("\nFailed cases:");
  failures.forEach(f => console.log(f));
}
console.log(`${"═".repeat(60)}\n`);

process.exit(failed > 0 ? 1 : 0);
