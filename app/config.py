import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Disaster Splatting Backend"
    API_V1_STR: str = "/api/v1"
    
    # Security & CORS
    ALLOWED_ORIGINS: list[str] = ["*"]
    
    # Storage
    UPLOAD_DIR: str = "uploads"
    STATIC_DIR: str = "static"
    
    # Database
    # Default to a local SQLite for immediate execution, but support PostgreSQL/PostGIS
    DATABASE_URL: str = "sqlite:///./disaster_splats.db"
    
    # Redis (for Celery background tasks)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # External APIs (Stage 2)
    LUMA_API_KEY: Optional[str] = None
    LUMA_API_URL: str = "https://api.luma.ai/public/v1"
    
    # AWS Storage (Optional for production stage 1/2)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"
    )


# Ensure directories exist
os.makedirs(Settings().UPLOAD_DIR, exist_ok=True)
os.makedirs(Settings().STATIC_DIR, exist_ok=True)

settings = Settings()
