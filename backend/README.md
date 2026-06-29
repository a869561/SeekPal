# SeekPal — Backend

Motor RAG local para búsqueda documental multimodal, implementado con FastAPI y Python.

## Arquitectura del pipeline RAG

```
Pregunta del usuario
   |
   v (opcional) expand_query (LLM) -> variantes   [multi-query: OFF por defecto]
   |
   v embed query (multilingual-e5-large) + [BM25 sparse]  -->  Qdrant hybrid search (RRF)
   |
   v Reranker (jina-reranker-v2-base-multilingual)
   |
   v MMR diversidad (lambda=0.7)
   |
   v GenerationService
prompt = qa_template + top-k chunks
   |
   v Ollama (gemma3:4b, streaming)
   |
SSE al frontend: retrieved -> thinking? -> token... -> done
```

## Estructura

```
backend/
├── app/
│   ├── core/              Config, DB (Beanie/Motor), seguridad (JWT/bcrypt), respuestas
│   ├── deps/              Dependencias inyectables (auth)
│   ├── models/            Documentos MongoDB: Source, FileDoc, Config (Beanie ODM)
│   ├── routers/           Endpoints FastAPI: auth, sources, ingest, ask, search, stats...
│   ├── schemas/           DTOs Pydantic (entrada/salida)
│   ├── services/
│   │   ├── rag/
│   │   │   ├── embedding_service.py    multilingual-e5-large (denso) + BM25 (sparse) via FastEmbed/ONNX
│   │   │   ├── vector_service.py       Qdrant hybrid search
│   │   │   ├── retrieval_service.py    RRF + reranker + MMR
│   │   │   ├── generation_service.py   Ollama streaming + filtro thinking
│   │   │   ├── chunking_service.py     Chunking recursivo (512/64)
│   │   │   ├── device_planner.py       Planificador VRAM-aware (ONNX/GPU)
│   │   │   ├── audio_service.py        Whisper (faster-whisper)
│   │   │   ├── image_service.py        Captioning con VLM (Ollama)
│   │   │   ├── index_service.py        Coordinación ingesta → Qdrant
│   │   │   └── extractors/             Extractores por formato (PDF, DOCX, PPTX, audio, imagen...)
│   │   ├── scanner_service.py          Escaneo de carpetas + orquestación SSE
│   │   └── watcher_service.py          Vigilancia watchdog para re-ingesta automática
│   └── main.py            Punto de entrada (FastAPI app + lifespan)
├── tests/                 Tests unitarios y de integración, y scripts de evaluación
├── requirements.txt
└── .env.example
```

## Requisitos

- Python 3.11+
- MongoDB 6+ (en local, por Docker o instalación directa)
- Ollama 0.4+ con el modelo LLM descargado (`ollama pull gemma3:4b`)

## Instalación

```bash
cd backend
python -m venv .venv

# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # ajustar si es necesario
```

Aceleración GPU opcional (NVIDIA):
```bash
pip install onnxruntime-gpu nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Aceleración GPU opcional (AMD/Intel, Windows):
```bash
pip install onnxruntime-directml
```

## Arranque

```bash
uvicorn app.main:app --host 127.0.0.1 --port 3000 --reload
```

OpenAPI interactivo: `http://localhost:3000/docs`

## Configuración (backend/.env)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | URI de conexión a MongoDB |
| `MONGO_DB` | `seekpal` | Nombre de la base de datos |
| `PORT` | `3000` | Puerto del backend |
| `JWT_SECRET` | `seekpal_secret_change_me` | Secreto JWT (cambiar en producción) |
| `JWT_EXPIRES_MINUTES` | `480` | TTL del token (minutos) |
| `DEFAULT_PASSWORD` | `user1111` | Contraseña inicial |
| `CORS_ORIGIN` | `http://localhost:5173` | Origen permitido por CORS |
| `OLLAMA_URL` | `http://localhost:11434` | URL de Ollama |
| `LLM_MODEL` | `gemma3:4b` | Modelo LLM para generación |
| `RAG_CHUNK_SIZE` | `512` | Tamaño de chunk (tokens) |
| `RAG_CHUNK_OVERLAP` | `64` | Solapamiento entre chunks (tokens) |
| `RAG_TOP_K` | `10` | Chunks recuperados por consulta |
| `RAG_RERANKER_DEVICE` | `auto` | Device del reranker: `auto`, `cpu`, `cuda` |
| `SEEKPAL_VISION_MODEL` | `qwen2.5vl:3b` | Modelo VLM para captioning de imágenes |

## Tests

```bash
pytest tests/rag/ -v        # tests unitarios del pipeline RAG (~210)
pytest tests/ -q            # todos los tests (~285)
```

Los tests unitarios no requieren modelos reales ni conexión a Qdrant/MongoDB.

## API principal

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/health` | No | Estado del servidor y MongoDB |
| `POST` | `/api/auth/login` | No | `{ password }` → `{ accessToken }` |
| `POST` | `/api/auth/change-password` | Sí | Cambio de contraseña |
| `GET` | `/api/sources` | Sí | Lista de fuentes indexadas |
| `POST` | `/api/sources` | Sí | Añadir directorio `{ name, path }` |
| `DELETE` | `/api/sources/:id` | Sí | Eliminar fuente y sus ficheros |
| `POST` | `/api/sources/:id/ingest` | Sí | Ingesta SSE (stream de progreso) |
| `GET` | `/api/ask` | Sí | Pregunta RAG (SSE streaming) |
| `GET` | `/api/search` | Sí | Búsqueda clásica por nombre/ruta |
| `GET` | `/api/stats/summary` | Sí | Totales y distribución por categoría |
| `GET` | `/api/settings` | Sí | Ajustes de usuario (tema, idioma...) |
| `GET` | `/api/system/status` | Sí | Estado de modelos y configuración |

Ver documentación completa en `/docs` (Swagger UI) al arrancar el backend.
