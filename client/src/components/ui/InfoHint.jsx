import { HelpCircle } from "lucide-react";

/**
 * Icono "?" con tooltip al pasar el ratón (o al enfocar con teclado).
 *
 * Sustituye a las descripciones en línea de los ajustes: mantiene la
 * información a un click/hover de distancia sin saturar el panel. Tooltip
 * puramente CSS (group-hover / focus-within), sin estado JS.
 */
export default function InfoHint({ text }) {
  if (!text) return null;
  return (
    <span className="relative inline-flex group align-middle">
      <HelpCircle
        size={13}
        tabIndex={0}
        aria-label={text}
        className="text-slate-400 hover:text-brand focus:text-brand cursor-help outline-none shrink-0"
      />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-1.5 w-60 -translate-x-1/2
                   rounded-lg bg-slate-800 dark:bg-slate-900 px-2.5 py-1.5 text-[11px] leading-snug
                   text-slate-100 shadow-lg ring-1 ring-black/5 opacity-0 transition-opacity duration-150
                   group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}
