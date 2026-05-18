# SeekPal — Buscador inteligente de ficheros

Aplicación web local para indexar, explorar y buscar ficheros en repositorios documentales con extracción automática de metadatos. TFG — fase 1: gestión de fuentes, estadísticas y búsqueda básica. La fase 2 incorporará un pipeline RAG (embeddings + LLM local).

## Stack

- **Backend**: Python 3.11+ · FastAPI · Beanie (MongoDB ODM) · Motor · sse-starlette · watchdog
- **Frontend**: React + Vite + Tailwind CSS + Recharts + i18next
- **Base de datos**: MongoDB 7
- **Auth**: Contraseña única global (bcrypt) + JWT

## Estructura del proyecto

```
SeekPal/
├── backend/                  Backend Python (FastAPI)
│   ├── app/
│   │   ├── core/             Config, DB, seguridad, respuestas
│   │   ├── models/           Documentos Mongo (Beanie)
│   │   ├── schemas/          DTOs Pydantic
│   │   ├── routers/          Endpoints HTTP
│   │   ├── services/         Lógica de negocio
│   │   ├── utils/            Utilidades transversales
│   │   ├── deps/             Dependencias inyectables (auth)
│   │   └── main.py           Punto de entrada
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── client/                   Frontend React + Vite
├── docs/                     Documentación del TFG
├── docker-compose.yml        MongoDB (+ backend opcional con --profile full)
└── start.bat                 Launcher Windows (Docker + backend + frontend)
```

## Requisitos

- Python 3.11+
- Node.js 20+ (frontend)
- Docker Desktop (MongoDB)
- (Opcional) `ffmpeg` en PATH para metadatos de vídeo. Si no está, los vídeos se indexan sin duración/resolución pero no falla la ingesta.

## Arranque rápido (Windows)

Doble click en `start.bat`. El script:
1. Comprueba/arranca Docker Desktop
2. Levanta MongoDB
3. Crea el venv del backend e instala dependencias (primera vez)
4. Arranca uvicorn (backend) y vite (frontend) en ventanas separadas

## Arranque manual

```bash
# 1. MongoDB
docker compose up -d mongodb

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 3000

# 3. Frontend (en otra terminal)
cd client
npm install
npm run dev
```

- Backend en `http://localhost:3000` (docs OpenAPI en `/docs`)
- Frontend en `http://localhost:5173`
- Contraseña por defecto la primera vez: `seekpal`

## API

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | /health | No | Estado del servidor + MongoDB |
| POST | /api/auth/login | No | `{ password }` → `{ accessToken, ... }` |
| POST | /api/auth/change-password | Sí | `{ currentPassword, newPassword }` |
| GET | /api/sources | Sí | Lista de fuentes |
| POST | /api/sources | Sí | Añadir directorio `{ name, path }` |
| DELETE | /api/sources/:id | Sí | Eliminar fuente y sus ficheros |
| PATCH | /api/sources/:id/auto-index | Sí | Activar/desactivar auto-reindexación |
| POST | /api/sources/:id/ingest | Sí | Inicia ingesta (SSE stream) |
| GET | /api/stats/summary | Sí | Resumen estadístico (totales, por categoría) |
| GET | /api/stats/files | Sí | Ficheros paginados con filtros y ordenación |
| GET | /api/search | Sí | Búsqueda por nombre/ruta (`q`, `category`, `sourceId`) |
| GET | /api/settings | Sí | Ajustes UI (tema, idioma, tamaño texto) |
| PATCH | /api/settings | Sí | Actualizar ajustes |
| GET | /api/system/folder-picker | Sí | Abre diálogo nativo de selección de carpeta |

Documentación OpenAPI interactiva autogenerada en `/docs` (Swagger UI) y `/redoc`.

### SSE de ingesta

El endpoint `POST /api/sources/:id/ingest` devuelve `text/event-stream`:

```
data: {"type":"scanning"}
data: {"type":"progress","current":5,"total":120,"file":"doc.pdf"}
data: {"type":"done"}
data: {"type":"error","message":"..."}
```

## Variables de entorno

Ver `backend/.env.example`.

| Variable | Default | Descripción |
|----------|---------|-------------|
| MONGO_URI | mongodb://localhost:27017 | URI de conexión a Mongo |
| MONGO_DB | seekpal | Nombre de la base de datos |
| PORT | 3000 | Puerto del backend |
| JWT_SECRET | seekpal_secret_change_me | Secreto para firmar JWT (CAMBIAR en producción) |
| JWT_EXPIRES_MINUTES | 480 | TTL del token |
| DEFAULT_PASSWORD | seekpal | Contraseña inicial cuando no hay Config en Mongo |
| CORS_ORIGIN | http://localhost:5173 | Origen permitido por CORS |

## Categorías de ficheros y metadatos

| Categoría | Metadatos | Librerías |
|-----------|-----------|-----------|
| text | wordCount, charCount | stdlib |
| document | wordCount, charCount | pypdf, python-docx, zipfile + regex |
| image | width, height, ppi | Pillow |
| audio | duration (s), bitrate (kbps) | mutagen |
| video | duration, width, height, fps | ffmpeg-python (ffprobe) |
| other | — | — |

## Roadmap

- **Fase 1 (actual)**: Gestión de fuentes + ingesta + estadísticas + búsqueda por nombre.
- **Fase 2**: Pipeline RAG local (Ollama + Llama 3.2 3B + BGE-M3 + Qdrant + Docling + LlamaIndex) para respuestas en lenguaje natural con citación de fuentes.
- **Fase 3**: Conectores externos (Google Drive, S3) y modo "remoto" opcional con APIs cloud.
