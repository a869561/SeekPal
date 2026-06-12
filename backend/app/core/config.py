from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    port: int = 3000

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "seekpal"

    jwt_secret: str = "seekpal_secret_change_me"
    jwt_expires_minutes: int = 480
    jwt_algorithm: str = "HS256"

    default_password: str = "seekpal"
    cors_origin: str = "http://localhost:5173"

    # RAG
    ollama_url: str = "http://localhost:11434"
    qdrant_path: str = "./qdrant_data"
    llm_model: str = "qwen3:4b"
    embedding_model: str = "intfloat/multilingual-e5-large"
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    rag_top_k: int = 10
    rag_embed_batch: int = 8

    # Reranker (cross-encoder sobre el top-k inicial del hybrid search).
    # Eleva recall@k +5-10pp segun informe v3 §10.1 (perfil Calidad).
    # FastEmbed 0.8 no expone bge-reranker-v2-m3 todavia, asi que usamos
    # jina-reranker-v2 multilingue (~280 MB) como mejor alternativa.
    rag_reranker_enabled: bool = True
    rag_reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    # Donde corre el cross-encoder: "auto" usa GPU si hay; "cpu" lo fuerza a
    # CPU. En tarjetas de ~4 GB los pesos de embeddings+reranker llenan la
    # VRAM y las activaciones del rerank provocan OOM o thrashing — ahi "cpu"
    # rinde parecido (~0.5 s/pasaje), es estable y deja la VRAM para Ollama.
    rag_reranker_device: str = "auto"
    # Multiplicador para sobre-recuperar candidatos antes del rerank.
    # Vector search devuelve top_k * multiplier y el reranker filtra a top_k.
    # 2 (no 3): el coste del rerank es lineal en candidatos y domina la
    # latencia de cada query en GPUs modestas; el RRF ya ordena lo bastante
    # bien como para que los relevantes esten en los primeros top_k*2.
    rag_reranker_multiplier: int = 2
    # Suelo de relevancia: tras el rerank se descartan candidatos cuyo score
    # quede por debajo de este umbral, evitando alimentar al LLM con relleno
    # irrelevante en queries sin buen match. Calibracion empirica con
    # jina-reranker-v2 sobre corpus mixto ES/EN: documentos claramente
    # relevantes puntuan entre -0.04 y +1.5 (queries españolas tienden a
    # logits bajos), asi que 0.0 podaba resultados correctos ('propuesta TFG'
    # perdia 1 de 2). -1.0 conserva esos y sigue cortando el relleno profundo.
    # Siempre se conserva al menos 1 resultado. Solo aplica con reranker activo.
    rag_reranker_min_score: float = -1.0

    # MMR (Maximum Marginal Relevance): tras retrieval+rerank, reordena el
    # top_k para diversificar — evita que sean todos del mismo fichero.
    # lambda=1 -> solo relevancia (no diversifica), 0 -> solo diversidad.
    # 0.7 es el balance estandar de la literatura (Carbonell & Goldstein 1998).
    rag_mmr_enabled: bool = True
    rag_mmr_lambda: float = 0.7

    # Multi-query expansion: el LLM genera N reformulaciones de la pregunta
    # (sinonimos, distintos angulos) que se usan para recuperar candidatos
    # adicionales antes de RRF-fusionar. Mejora recall@k en corpus grandes.
    # n=3 genera 3 variantes + la pregunta original = 4 queries en total.
    rag_multi_query_enabled: bool = True
    rag_multi_query_n: int = 3

    # Thinking mode (Qwen3 / DeepSeek-R1): el LLM genera razonamiento extendido
    # antes de la respuesta. Mejora la calidad en preguntas complejas a costa
    # de mayor latencia (~2-5 s extra en CPU). Desactivado por defecto para
    # mantener la respuesta rapida en el caso de uso tipico de RAG.
    # El razonamiento se emite como eventos SSE {"type": "thinking"} separados.
    rag_thinking_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
