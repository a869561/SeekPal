import { ChevronDown } from "lucide-react";

/**
 * Cabecera de tarjeta que se puede plegar/desplegar. El título (con su icono y
 * un chevron) es el botón de plegado; las acciones de la derecha (p. ej.
 * refrescar) se pasan por `actions` y no disparan el plegado.
 */
export default function CollapsibleHeader({ icon: Icon, title, collapsed, onToggle, actions }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={!collapsed}
        className="group flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        <ChevronDown
          size={16}
          className={`shrink-0 text-slate-400 transition-transform ${collapsed ? "-rotate-90" : ""}`}
        />
        {Icon && <Icon size={18} className="shrink-0 text-brand" />}
        <h2 className="truncate font-semibold text-slate-800 transition-colors group-hover:text-brand dark:text-slate-100">
          {title}
        </h2>
      </button>
      {actions}
    </div>
  );
}
