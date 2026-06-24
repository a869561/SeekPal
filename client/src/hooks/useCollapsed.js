import { useCallback, useState } from "react";

// Estado de plegado de una sección, persistido en localStorage. Es una
// preferencia de interfaz (no de backend): se aplica al instante y no requiere
// reiniciar. Por defecto la sección está DESPLEGADA si no hay valor guardado,
// salvo que se pase defaultCollapsed=true.
export default function useCollapsed(key, defaultCollapsed = false) {
  const storageKey = `seekpal.collapsed.${key}`;
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null) return stored === "1";
      return defaultCollapsed;
    } catch {
      return defaultCollapsed;
    }
  });
  const toggle = useCallback(() => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* almacenamiento no disponible: el estado vive solo en memoria */
      }
      return next;
    });
  }, [storageKey]);
  return [collapsed, toggle];
}
