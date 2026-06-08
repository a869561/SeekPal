/**
 * Tiempo relativo legible ("hace 3 h", "ayer") con Intl.RelativeTimeFormat
 * (nativo, sin dependencias). Devuelve "" si no hay fecha.
 */
const UNITS = [
  ["year",   60 * 60 * 24 * 365],
  ["month",  60 * 60 * 24 * 30],
  ["day",    60 * 60 * 24],
  ["hour",   60 * 60],
  ["minute", 60],
  ["second", 1],
];

export function relativeTime(date, locale = "es") {
  if (!date) return "";
  const then = new Date(date).getTime();
  if (Number.isNaN(then)) return "";

  const diffSec = Math.round((then - Date.now()) / 1000); // negativo = pasado
  const abs = Math.abs(diffSec);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  for (const [unit, secs] of UNITS) {
    if (abs >= secs || unit === "second") {
      return rtf.format(Math.round(diffSec / secs), unit);
    }
  }
  return "";
}

/** Fecha+hora absoluta para tooltips. */
export function absoluteDateTime(date, locale = "es-ES") {
  if (!date) return "";
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}
