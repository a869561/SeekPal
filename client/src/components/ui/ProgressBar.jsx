/**
 * Barra de progreso. Transición suave del ancho + shimmer mientras está activa.
 * tone: brand | success | danger.  indeterminate → animación de barrido.
 */
const TONE = {
  brand:   "bg-brand",
  success: "bg-success",
  danger:  "bg-danger",
};

export default function ProgressBar({
  value = 0,
  tone = "brand",
  indeterminate = false,
  active = false,
  className = "",
}) {
  const fill = TONE[tone] ?? TONE.brand;
  return (
    <div className={`relative h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden ${className}`}>
      {indeterminate ? (
        <div className={`h-full w-1/3 rounded-full ${fill} animate-[scanning_1.2s_ease-in-out_infinite]`} />
      ) : (
        <div
          className={`relative h-full rounded-full ${fill} transition-[width] duration-500 ease-out`}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        >
          {active && <span className="progress-shimmer" />}
        </div>
      )}
    </div>
  );
}
