from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LlamaParse
    llama_cloud_api_key: str
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str
    
    # PostgreSQL
    database_url: str
    
    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "documents"
    minio_use_ssl: bool = False
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    
    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
