# SeekPal — Buscador inteligente de ficheros

Aplicación web local para indexar y explorar directorios de ficheros con extracción automática de metadatos. TFG — fase 1: gestión de fuentes y estadísticas (sin IA).

## Stack

- **Backend**: Node.js + Express + Mongoose (MongoDB)
- **Frontend**: React + Vite + Tailwind CSS + Recharts
- **Auth**: Contraseña única global (bcrypt) + JWT

## Requisitos

- Node.js 20+
- Docker (para MongoDB)

## Arranque

```bash
# 1. MongoDB
docker compose up -d

# 2. Variables de entorno
cp .env.example .env

# 3. Backend (puerto 3000)
npm install
npm run dev

# 4. Frontend (puerto 5173)
cd client
npm install
npm run dev
```

La primera vez que arranca el backend se crea la contraseña por defecto (`seekpal`).

## API

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | /health | No | Estado del servidor + MongoDB |
| POST | /api/auth/login | No | `{ password }` → `{ token }` |
| POST | /api/auth/change-password | Sí | `{ currentPassword, newPassword }` |
| GET | /api/sources | Sí | Lista de fuentes |
| POST | /api/sources | Sí | Añadir directorio `{ name, path }` |
| DELETE | /api/sources/:id | Sí | Eliminar fuente y sus ficheros |
| POST | /api/sources/:id/ingest | Sí | Inicia ingesta (SSE stream) |
| GET | /api/stats | Sí | Resumen estadístico |
| GET | /api/stats/files | Sí | Ficheros paginados con filtros |

### SSE de ingesta

El endpoint `POST /api/sources/:id/ingest` devuelve `text/event-stream` con eventos:

```
data: {"type":"progress","current":5,"total":120,"file":"doc.pdf"}
data: {"type":"done","fileCount":120}
data: {"type":"error","message":"..."}
```

## Variables de entorno

Ver `.env.example`.

## Categorías de ficheros

| Categoría | Metadatos extraídos |
|-----------|---------------------|
| text | wordCount, charCount |
| document | wordCount, charCount (pdf, docx, odt, pptx) |
| image | width, height, ppi |
| audio | duration (s), bitrate (kbps) |
| video | duration (s), width, height, fps |
| other | — |
