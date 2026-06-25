# SeekPal

Asistente documental local con RAG (Retrieval-Augmented Generation). Indexa carpetas de ficheros (PDF, Word, PowerPoint, Excel, imágenes, audio, vídeo, etc.) y permite hacer preguntas en lenguaje natural sobre su contenido, con citación de fuentes. Todo el procesamiento ocurre en el equipo del usuario, sin enviar datos a servidores externos.

Proyecto de Trabajo de Fin de Grado (TFG).

## Características principales

- **Búsqueda semántica**: embeddings densos (BGE-M3) + BM25 sparse + fusión híbrida (RRF) + reranker.
- **Preguntas en lenguaje natural**: generación con LLM local (Ollama), streaming y citación de fuentes.
- **Multimodal**: extrae texto de PDFs (Docling/PyMuPDF + OCR), documentos Office, audio (Whisper), imágenes (captioning con VLM) y más.
- **Privado y local**: ningún dato sale del equipo; modelos de embedding, reranker y LLM corren localmente.
- **Arranque con un clic** en Windows (`start.bat`): instala dependencias, levanta Docker/MongoDB, descarga modelos Ollama y arranca backend y frontend automáticamente.

## Arquitectura

```
Cliente (React + Vite)
      |  HTTP / SSE
Backend (FastAPI + Python)
  ├─ Ingesta: Docling/PyMuPDF · Whisper · RapidOCR · Pillow · VLM captioning
  ├─ Embeddings: FastEmbed (BGE-M3 denso + BM25 sparse)
  ├─ Almacén vectorial: Qdrant (local, fichero)
  ├─ Reranker: jina-reranker-v2-base-multilingual
  └─ Generación: Ollama (Qwen3:4b por defecto, streaming)
Base de datos: MongoDB (metadatos de fuentes y ficheros)
```

## Requisitos previos

| Componente | Mínimo | Recomendado |
|-----------|--------|-------------|
| Python | 3.11+ | 3.12+ |
| Node.js | 18+ | 20+ |
| Docker Desktop | — | última versión |
| Ollama | 0.4+ | última versión |
| RAM | 8 GB | 16 GB |
| Almacenamiento libre | 5 GB | 20 GB |

GPU opcional: Ollama usa CUDA/ROCm automáticamente; los embeddings usan ONNX Runtime (CUDA, DirectML o CPU).

## Arranque rápido (Windows)

Doble clic en `start.bat`. El script:
1. Comprueba Python, Node.js y Docker e instala dependencias (primera vez).
2. Levanta MongoDB con Docker Compose.
3. Instala y arranca Ollama; descarga los modelos de IA (primera vez, varios minutos).
4. Pre-descarga los modelos de embeddings (~2 GB, primera vez).
5. Arranca el backend (uvicorn) y el frontend (Vite) en ventanas separadas.

Accesos una vez arrancado:
- Frontend: `http://localhost:5173`
- Backend / OpenAPI: `http://localhost:3000/docs`
- Contraseña inicial: `seekpal` (recomendado cambiarla desde Ajustes en el primer uso).

## Arranque manual

```bash
# 1. MongoDB
docker compose up -d mongodb

# 2. Backend
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ajustar variables si es necesario
uvicorn app.main:app --host 127.0.0.1 --port 3000 --reload

# 3. Frontend (en otra terminal)
cd client
npm install
npm run dev
```

## Uso básico

1. **Fuentes** → **Nueva fuente** → selecciona una carpeta → **Indexar**.
   El backend extrae texto, genera embeddings y los almacena en Qdrant.
2. **Asistente** → escribe una pregunta en lenguaje natural → respuesta con citas.
3. **Buscar** → búsqueda clásica por nombre/ruta de fichero.

## Configuración

Las variables de entorno se configuran en `backend/.env` (copiar desde `backend/.env.example`).

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | URI de conexión a MongoDB |
| `MONGO_DB` | `seekpal` | Nombre de la base de datos |
| `PORT` | `3000` | Puerto del backend |
| `JWT_SECRET` | `seekpal_secret_change_me` | Secreto JWT (cambiar en producción) |
| `JWT_EXPIRES_MINUTES` | `480` | TTL del token (minutos) |
| `DEFAULT_PASSWORD` | `seekpal` | Contraseña inicial |
| `CORS_ORIGIN` | `http://localhost:5173` | Origen permitido por CORS |
| `OLLAMA_URL` | `http://localhost:11434` | URL de Ollama |
| `LLM_MODEL` | `qwen3:4b` | Modelo LLM (Ollama) |
| `RAG_RERANKER_DEVICE` | `auto` | Device del reranker: `auto`, `cpu`, `cuda` |
| `SEEKPAL_VISION_MODEL` | `qwen2.5vl:3b` | Modelo de visión para captioning |

## Tests

```bash
cd backend
pytest tests/rag/ -v    # ~70 tests unitarios, sin modelos reales
```

## Estructura del proyecto

```
SeekPal/
├── backend/              Backend Python (FastAPI)
│   ├── app/
│   │   ├── core/         Config, DB, seguridad, respuestas
│   │   ├── models/       Documentos Mongo (Beanie ODM)
│   │   ├── schemas/      DTOs Pydantic
│   │   ├── routers/      Endpoints HTTP
│   │   ├── services/     Lógica de negocio (RAG, ingesta, etc.)
│   │   └── main.py       Punto de entrada
│   ├── tests/            Tests unitarios y de integración
│   ├── requirements.txt
│   └── .env.example
├── client/               Frontend React + Vite + Tailwind CSS
├── docker-compose.yml    MongoDB
└── start.bat             Launcher Windows
```

## Modelos descargados automáticamente

| Modelo | Tamaño aprox. | Propósito |
|--------|--------------|-----------|
| `intfloat/multilingual-e5-large` | ~560 MB | Embeddings densos (FastEmbed/ONNX) |
| `Qdrant/bm25` | ~2 MB | Embeddings sparse BM25 |
| `jinaai/jina-reranker-v2-base-multilingual` | ~280 MB | Reranker cross-encoder |
| `faster-whisper small` | ~244 MB | Transcripción de audio |
| `qwen3:4b` (Ollama) | ~2.5 GB | Generación de respuestas (pull manual o `start.bat`) |

## Licencia

MIT — ver [LICENSE](LICENSE).

Autor: Adrián Jorge Nasarre Sánchez.
