import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base

@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db_session_factory(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True)
    return SessionLocal

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()