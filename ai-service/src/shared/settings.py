from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    nvidia_api_key: str = ""
    llama_cloud_api_key: str

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str

    database_url: str

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "documents"
    minio_use_ssl: bool = False

    qdrant_url: str = "http://localhost:6333"

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3300"
    langfuse_base_url: str = "http://localhost:3300"

    # MCP servers
    qdrant_mcp_url: str = "http://localhost:8001"
    neo4j_mcp_url: str = "http://localhost:8002"
    qdrant_collection_name: str = "legal_contracts_hybrid"
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    mcp_auth_key: str
    mcp_allowed_origins: str = ""
    mcp_allow_local_bypass: bool = False

    # mem0
    mem0_api_key: str = ""

    # LangGraph checkpointing
    checkpoint_backend: str = "mongodb"
    mongodb_url: str = ""
    mongodb_database: str = "langgraph"
    mongodb_checkpoint_collection: str = "checkpoints"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
