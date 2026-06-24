// Caché de sesión con deduplicación de peticiones en vuelo.
//
// Pensado para datos del backend costosos de obtener y que cambian poco
// (hardware, lista de modelos, ajustes, estado de Docling). Devuelve el valor
// cacheado en visitas posteriores en lugar de volver a sondear el equipo en
// cada montaje de una tarjeta.
//
//   get(force)  → promesa con el dato. force=true ignora la caché (botón
//                 refrescar, polling de un estado que está cambiando, o espera
//                 de un reinicio que debe llegar a red).
//   invalidate  → descarta el valor cacheado tras una mutación (guardar,
//                 instalar, borrar) o al reiniciar el backend.
export function makeSessionCache(fetcher) {
  let cache = null;     // null = nunca cargado todavía
  let inflight = null;  // petición en curso, para deduplicar llamadas paralelas

  const get = (force = false) => {
    if (!force && cache !== null) return Promise.resolve(cache);
    if (!force && inflight) return inflight;
    inflight = Promise.resolve()
      .then(fetcher)
      .then((data) => {
        cache = data;
        return data;
      })
      .finally(() => {
        inflight = null;
      });
    return inflight;
  };

  const invalidate = () => {
    cache = null;
  };

  return { get, invalidate };
}
