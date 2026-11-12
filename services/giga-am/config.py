from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Application settings
    app_name: str = "GigaAM API"
    app_version: str = "1.1.0"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 7860
    
    # Model settings
    model_name: str = "v3_e2e_rnnt"
    
    # File upload settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_audio_formats: List[str] = [
        ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".webm"
    ]
    
    # Security settings
    hf_token: str = ""
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Timeout settings
    transcription_timeout: int = Field(default=900, ge=1)  # 15 минут по умолчанию

    # Inngest connection
    inngest_api_url: str = "http://localhost:3001"
    inngest_event_key: str = ""

    callback_timeout: int = Field(default=20, ge=1)
    callback_allowed_hosts: List[str] = []
    callback_allowed_networks: List[str] = []
    callback_response_max_bytes: int = Field(default=64 * 1024, ge=1)
    callback_max_attempts: int = Field(default=3, ge=1)
    callback_retry_seconds: int = Field(default=60, ge=1)
    callback_outbox_path: str = "data/webhook-callbacks.sqlite3"

    # Concurrency settings
    model_workers: int = Field(default=2, ge=1)
    model_loading_timeout: int = Field(default=1800, ge=1)  # 30 минут для первичной загрузки модели

    # Preloading settings
    preload_pyannote_model: bool = Field(
        default=False,
        description="Preload pyannote model at startup (may cause rate limiting)"
    )
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }

# Global settings instance
settings = Settings()
