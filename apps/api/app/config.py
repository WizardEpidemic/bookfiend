# Loads environment-based configuration for the BookFiend API and worker services.

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    upload_dir: str = "uploads"
    scan_rate_limit: int = 5
    scan_rate_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()