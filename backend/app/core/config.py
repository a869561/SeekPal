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
    llm_model: str = "llama3.2:3b"
    embedding_model: str = "bge-m3"
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    rag_top_k: int = 5
    rag_embed_batch: int = 32

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
