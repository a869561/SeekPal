import { Loader2 } from "lucide-react";

/**
 * Indicador de carga centrado (círculo + texto opcional).
 *
 * Único para toda la app, de modo que los modos búsqueda y pregunta (y por
 * tanto auto) muestren exactamente el mismo "rosco" mientras procesan.
 */
export default function LoadingSpinner({ label }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-slate-400 dark:text-slate-500">
      <Loader2 size={28} className="text-brand animate-spin" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
