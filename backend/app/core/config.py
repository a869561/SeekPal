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
    # Multiplicador para sobre-recuperar candidatos antes del rerank.
    # Vector search devuelve top_k * multiplier y el reranker filtra a top_k.
    rag_reranker_multiplier: int = 3

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
