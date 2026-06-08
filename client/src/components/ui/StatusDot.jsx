/**
 * Punto de estado. Reemplaza marcos de color por una señal puntual y sobria.
 * tone: success | warning | danger | brand | neutral
 */
const TONE = {
  success: "bg-success",
  warning: "bg-warning",
  danger:  "bg-danger",
  brand:   "bg-brand",
  neutral: "bg-slate-400 dark:bg-slate-500",
};

export default function StatusDot({ tone = "neutral", pulse = false, className = "" }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full shrink-0 ${TONE[tone] ?? TONE.neutral} ${pulse ? "animate-pulse" : ""} ${className}`}
    />
  );
}
