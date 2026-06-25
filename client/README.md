# SeekPal — Frontend

Interfaz web de SeekPal, construida con React + Vite + Tailwind CSS. Consume la API REST del backend FastAPI en `http://localhost:3000`.

## Desarrollo

```bash
npm install
npm run dev   # http://localhost:5173
```

El proxy Vite reenvía `/api/*` → `http://localhost:3000` (configurado en `vite.config.js`). No se necesitan variables de entorno adicionales en desarrollo.

## Build de producción

```bash
npm run build   # genera dist/
npm run preview # sirve dist/ localmente
```

## Tests E2E

```bash
npx playwright install   # primera vez
npm run test:e2e
```

## Vistas principales

| Ruta | Vista |
|------|-------|
| `/login` | Formulario de contraseña |
| `/sources` | Gestión de fuentes + ingesta con progreso SSE |
| `/search` | Búsqueda clásica y asistente RAG (streaming) |
| `/stats` | Gráficos y tabla paginada de ficheros indexados |
| `/settings` | Ajustes de usuario, hardware y gestión de modelos |

## Stack

- **Framework**: React 19 + Vite 8
- **Estilos**: Tailwind CSS 4
- **Routing**: React Router 7
- **HTTP**: Axios
- **Gráficos**: Recharts
- **i18n**: i18next + react-i18next (español e inglés)
- **Tests E2E**: Playwright
