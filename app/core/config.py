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

    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str | None = None

    RABBITMQ_URL: str
    RABBITMQ_ENABLED: bool = True

    TASKS_QUEUE_HIGH: str = "tasks.high"
    TASKS_QUEUE_MEDIUM: str = "tasks.medium"
    TASKS_QUEUE_LOW: str = "tasks.low"

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

settings = Settings()