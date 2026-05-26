# SeekPal

Motor de busqueda y asistente de documentos local basado en RAG (Retrieval-Augmented Generation). Indexa carpetas de ficheros (PDF, Word, PowerPoint, Excel, audio, imagenes, etc.) y permite hacer preguntas en lenguaje natural sobre su contenido.

Todo corre **en tu maquina**: los modelos de embedding y el LLM se ejecutan con Ollama sin enviar datos a ningun servidor externo.

---

## Arquitectura

```
+----------------------------------------------------------------------+
|                          CLIENTE (React + Vite)                      |
|  +----------+  +----------+  +---------------+  +---------------+   |
|  |  Search  |  |   Ask    |  |   Sources     |  |   Settings    |   |
|  |  (SSE)   |  |  (SSE)   |  |   (ingest)    |  |  (hardware)   |   |
|  +----+-----+  +----+-----+  +------+--------+  +-------+-------+   |
+-------+--------------+---------------+-------------------+-----------+
        |              |               |                   | HTTP/SSE
+-------v--------------v---------------v-------------------v-----------+
|                        BACKEND (FastAPI)                             |
|                                                                      |
|  /api/ask                                                            |
|    1. GenerationService.expand_query()  -> 3 variantes              |
|    2. RetrievalService.retrieve_multi()                              |
|         +- EmbeddingService (BGE-M3 dense, ONNX)  -+               |
|         +- SparseEmbeddingService (BM25)            +-> Qdrant      |
|         +- VectorService.search() hybrid RRF        |   (local)     |
|         +- RerankerService (jina-reranker)                          |
|         +- MMR diversity selection                                   |
|    3. GenerationService.generate_stream() -> Ollama                 |
|         +- _think_filter() -> "token" / "thinking"                  |
|    SSE: retrieved -> thinking? -> token... -> done                  |
|                                                                      |
|  /api/ingest                                                         |
|    ScannerService                                                    |
|      +- walk + classify (MIME)                                       |
|      +- Extractor (PDF/DOCX/PPTX/XLS/TXT/audio/image)              |
|      +- ChunkingService (recursive 512/64)                           |
|      +- EmbeddingService.embed_texts() (dense)                       |
|      +- SparseEmbeddingService.embed_texts() (BM25)                  |
|      +- VectorService.upsert() -> Qdrant                             |
|                                                                      |
|  WatcherService (watchdog, unico Observer compartido)                |
|  MongoDB (Beanie ODM) -- Sources, Files, Config                      |
+----------------------------------------------------------------------+
        |                   |
   +----v----+         +----v----+
   | Qdrant  |         | Ollama  |
   | (local) |         | (local) |
   | dense + |         | Qwen3:4b|
   |  BM25   |         +---------+
   +---------+
```

### Pipeline RAG detallado

```
Pregunta del usuario
   |
   v expand_query (LLM)
[q original, variante1, variante2, variante3]
   |
   v retrieve_multi (paralelo)
[dense embed] + [BM25 sparse]  -->  Qdrant hybrid search (RRF)
   |              (por variante)           |
   +--------------------------------------------> RRF fusion
                                           |
                               v Reranker (jina-reranker)
                                           |
                               v MMR diversidad (lambda=0.7)
                                           |
                                      top-k chunks
                                           |
                               v GenerationService
                         prompt = qa_template + chunks
                                           |
                              Ollama (Qwen3:4b, stream)
                                           |
                            [thinking]  [token] [token] ...
                                           |
                                     SSE al frontend
```

---

## Requisitos

| Componente | Minimo | Recomendado |
|-----------|--------|-------------|
| Python | 3.11+ | 3.12+ |
| RAM | 8 GB | 16 GB |
| Almacenamiento | 5 GB libres | 20 GB |
| Ollama | 0.4+ | ultima |
| MongoDB | 6+ | 7+ |
| Node.js | 18+ | 20+ |

**GPU**: opcional. Ollama usa CUDA/ROCm automaticamente. Embeddings usan ONNX Runtime (CUDA, DirectML o CPU).

---

## Instalacion

### 1. Requisitos previos

```bash
# Instalar Ollama: https://ollama.com
ollama pull qwen3:4b          # LLM (~2.5 GB)
ollama pull moondream          # Opcional: captioning de imagenes

# MongoDB corriendo en localhost:27017
```

### 2. Backend

```bash
cd backend
python -m venv .venv

# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
```

GPU opcional:
```bash
pip install onnxruntime-gpu nvidia-cublas-cu12 nvidia-cudnn-cu12  # NVIDIA
pip install onnxruntime-directml                                    # AMD/Intel (Windows)
```

### 3. Frontend

```bash
cd client
npm install
```

### 4. Configuracion (backend/.env)

```env
MONGO_URI=mongodb://localhost:27017
OLLAMA_URL=http://localhost:11434
LLM_MODEL=qwen3:4b

# Opcionales
RAG_THINKING_ENABLED=false
RAG_MULTI_QUERY_ENABLED=true
RAG_MMR_ENABLED=true
RAG_RERANKER_ENABLED=true
```

### 5. Arrancar

```bash
# Backend
cd backend && uvicorn app.main:app --port 8000 --reload

# Frontend
cd client && npm run dev
```

Abre http://localhost:5173

---

## Uso rapido

1. **Fuentes** -> **Nueva fuente** -> selecciona carpeta -> **Indexar**
2. **Asistente** -> escribe tu pregunta -> respuesta con citas

---

## Tests

```bash
cd backend
pytest tests/rag/ -v    # ~70 tests unitarios, sin modelos reales
```

---

## Estructura

```
SeekPal/
+-- backend/
|   +-- app/
|   |   +-- core/          # Config, DB
|   |   +-- models/        # MongoDB ODM
|   |   +-- routers/       # FastAPI endpoints
|   |   +-- services/
|   |       +-- rag/
|   |           +-- embedding_service.py    # BGE-M3 + BM25
|   |           +-- vector_service.py       # Qdrant hybrid
|   |           +-- retrieval_service.py    # Search + reranker + MMR + multi-query
|   |           +-- generation_service.py   # Ollama + thinking filter
|   |           +-- benchmark_service.py    # Recall@k, MRR, latency
|   +-- tests/rag/         # 70+ tests
+-- client/                # React + Vite
```

---

## Modelos descargados automaticamente

| Modelo | Tam | Proposito |
|--------|-----|-----------|
| intfloat/multilingual-e5-large | ~560 MB | Embeddings densos |
| Qdrant/bm25 | ~2 MB | BM25 sparse |
| jinaai/jina-reranker-v2-base-multilingual | ~280 MB | Reranker |
| faster-whisper/small | ~244 MB | Transcripcion audio |
| qwen3:4b (Ollama) | ~2.5 GB | Generacion (pull manual) |

---

## Licencia

MIT
