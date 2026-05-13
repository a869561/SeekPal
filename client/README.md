# SeekPal — Frontend

React + Vite + Tailwind CSS. Consume la API Express en `http://localhost:3000`.

## Desarrollo

```bash
npm install
npm run dev   # http://localhost:5173
```

## Vistas

| Ruta | Vista |
|------|-------|
| `/login` | Formulario de contraseña |
| `/sources` | Gestión de directorios + ingesta con progreso SSE |
| `/stats` | Gráficos (tarta + barras) + tabla paginada de ficheros |
| `/settings` | Cambio de contraseña |

## Variables

El proxy Vite reenvía `/api/*` → `http://localhost:3000` (configurado en `vite.config.js`). No hay variables de entorno necesarias en desarrollo.
