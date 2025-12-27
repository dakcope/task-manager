import os
from pathlib import Path
from typing import Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(".env.test", override=True)


def _apply_test_env() -> None:
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("RABBITMQ_ENABLED", "0")
    os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/")


_apply_test_env()

from app.main import app
from app.db.session import get_db


def make_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if "connect_timeout=" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{sep}connect_timeout=3"
        return db_url

    db = os.getenv("POSTGRES_DB", "task_manager_test")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "123")
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "55432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}?connect_timeout=3"


def _run_alembic_upgrade(db_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL"] = db_url

    ini_path = Path("alembic.ini")
    if not ini_path.exists():
        ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"

    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine():
    url = make_db_url()
    eng = create_engine(url, pool_pre_ping=True)

    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as e:
        pytest.skip(f"Postgres is not available. DSN={url}. Error={repr(e)}")

    _run_alembic_upgrade(url)
    return eng


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        try:
            db.execute(text("TRUNCATE TABLE tasks RESTART IDENTITY CASCADE"))
            db.commit()
        except Exception:
            db.rollback()
        db.close()


@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()