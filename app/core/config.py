from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str | None = None

    RABBITMQ_URL: str
    RABBITMQ_ENABLED: bool = True

    WORKER_PREFETCH: int
    MAX_RETRIES: int
    RETRY_DELAYS_SECONDS: str

    TASKS_QUEUE_HIGH: str = "tasks.high"
    TASKS_QUEUE_MEDIUM: str = "tasks.medium"
    TASKS_QUEUE_LOW: str = "tasks.low"

    OUTBOX_POLL_INTERVAL: float
    OUTBOX_BATCH_SIZE: int
    OUTBOX_MAX_ATTEMPTS: int

    WORKER_QUEUES: str | None = None

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def retry_delays(self) -> list[int]:
        parts = [p.strip() for p in (self.RETRY_DELAYS_SECONDS or "").split(",") if p.strip()]
        delays: list[int] = []
        for p in parts:
            try:
                v = int(p)
                if v > 0:
                    delays.append(v)
            except ValueError:
                continue
        return delays or [1, 5, 30, 120]


settings = Settings()