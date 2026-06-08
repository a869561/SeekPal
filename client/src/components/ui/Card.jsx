/**
 * Superficie base. Radio único (16px), borde hairline + sombra tintada (slate).
 * `interactive` añade elevación al hover (sombra tintada de marca + lift sutil).
 */
export default function Card({ interactive = false, className = "", children, ...props }) {
  const base =
    "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 " +
    "rounded-2xl shadow-card";
  const hover = interactive
    ? "transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-card-hover"
    : "";
  return (
    <div className={`${base} ${hover} ${className}`} {...props}>
      {children}
    </div>
  );
}
