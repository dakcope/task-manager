from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "task-service"
    APP_ENV: str = "local"

    DATABASE_URL: str
    RABBITMQ_URL: Optional[str] = None

settings = Settings()