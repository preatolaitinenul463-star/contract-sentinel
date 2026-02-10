"""Application configuration management."""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Application
    app_name: str = "ContractSentinel"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True
    
    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "sqlite+aiosqlite:///./contract_sentinel.db"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # JWT
    jwt_secret: str = "your-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    
    # Encryption at rest (use ENCRYPTION_KEY in production; fallback: JWT secret)
    encryption_key: Optional[str] = None
    encryption_salt: str = "contract_sentinel_salt"  # Override via ENCRYPTION_SALT env var
    encryption_enabled: bool = True
    key_rotation_days: int = 90  # Key rotation interval for KMS
    
    # Data retention (days); audit and contracts purged after this
    data_retention_days: int = 365
    
    # File Storage
    storage_path: str = "./storage"
    max_file_size_mb: int = 50
    
    # LLM Providers
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    
    minimax_api_key: Optional[str] = None
    minimax_group_id: Optional[str] = None
    minimax_base_url: str = "https://api.minimax.chat/v1"
    
    openai_compatible_api_key: Optional[str] = None
    openai_compatible_base_url: str = "http://localhost:11434/v1"
    
    siliconflow_api_key: Optional[str] = None
    
    # Default Provider
    default_chat_provider: str = "deepseek"
    default_chat_model: str = "deepseek-reasoner"
    default_embedding_provider: str = "openai"
    default_embedding_model: str = "text-embedding-3-small"
    
    # Web-RAG
    rag_crawl_rate_limit: float = 1.0
    rag_cache_ttl_hours: int = 24
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "logs/app.log"  # Set to None to disable file logging
    log_rotation: str = "1 day"
    log_retention: str = "30 days"

    # SMTP (for email sending)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: str = "noreply@contract-sentinel.ai"

    # CORS - comma-separated origins, defaults to localhost for development
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins string into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_dir(self) -> Path:
        """Get storage directory path."""
        path = Path(self.storage_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"

    def validate_production(self) -> None:
        """Validate production configuration. Raises ValueError if insecure defaults are detected."""
        if not self.debug and not self.is_production:
            return  # Only enforce in production

        errors = []
        if self.jwt_secret == "your-super-secret-jwt-key-change-in-production":
            errors.append("JWT_SECRET must be changed from default value in production")

        if not self.encryption_key and self.encryption_enabled:
            errors.append("ENCRYPTION_KEY must be set in production (not derived from JWT secret)")

        if self.debug:
            errors.append("DEBUG must be False in production")

        if errors:
            raise ValueError(
                "Production configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
