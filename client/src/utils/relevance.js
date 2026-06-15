/**
 * Convierte el score del reranker en un porcentaje de relevancia 0–100%.
 *
 * El reranker (jina-reranker-v2) devuelve un logit sin acotar (~-1 a ~+1.5 en
 * este corpus), por eso el score crudo daba valores confusos al multiplicarlo
 * por 100 (p. ej. 109% o -46%). Una sigmoide lo mapea de forma monótona a
 * [0, 100]%: score alto → cerca de 100%, score 0 → 50%, score negativo → <50%.
 *
 * @param {number|null|undefined} score
 * @returns {number|null} porcentaje entero, o null si no hay score
 */
export function relevancePct(score) {
  if (score == null || Number.isNaN(score)) return null;
  return Math.round(100 / (1 + Math.exp(-score)));
}
