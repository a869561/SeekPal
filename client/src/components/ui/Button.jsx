/**
 * Botón base reutilizable. Centraliza estilo, variantes semánticas y el feedback
 * de pulsación (scale en :active). Las páginas NO repiten clases de botón.
 *
 * variant: primary | brand | neutral | ghost | success | warning | danger
 *   - primary  → acción principal sólida (morado de marca)
 *   - brand    → tonal morado (acción secundaria con identidad)
 *   - neutral  → informativo / sin carga semántica (p. ej. pausar)
 *   - ghost    → mínimo, solo hover
 *   - success/warning/danger → SOLO con su significado (completar / avisar / destruir)
 */

const BASE =
  "inline-flex items-center justify-center gap-1.5 font-medium rounded-lg " +
  "transition-[transform,background-color,color,filter] duration-150 ease-out " +
  "active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50";

const VARIANTS = {
  primary: "bg-brand text-white hover:brightness-110",
  brand:   "bg-brand-soft text-brand hover:bg-brand/20",
  neutral: "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600",
  ghost:   "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700",
  success: "bg-success-soft text-success hover:bg-success/20",
  warning: "bg-warning-soft text-warning hover:bg-warning/20",
  danger:  "bg-danger-soft text-danger hover:bg-danger/20",
};

const SIZES = {
  sm: "px-2 py-1 text-xs",
  md: "px-3 py-1.5 text-sm",
  lg: "px-4 py-2.5 text-sm",
};

export default function Button({
  variant = "neutral",
  size = "md",
  className = "",
  type = "button",
  children,
  ...props
}) {
  return (
    <button
      type={type}
      className={`${BASE} ${VARIANTS[variant] ?? VARIANTS.neutral} ${SIZES[size] ?? SIZES.md} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
