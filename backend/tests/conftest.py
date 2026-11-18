"""Shared pytest fixtures for Phase 1+ backend tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

TEST_JWT_SECRET = "test-secret-key-with-at-least-32-characters-long!"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        jwt_secret=TEST_JWT_SECRET,
        cookie_secure=True,
        cors_origins=["http://localhost:5173"],
        admin_email="admin@careops.example",
        admin_password="Chief-Strong-Pass-99!",
    )


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session, test_settings: Settings) -> Iterator[TestClient]:
    limiter.reset()
    app = create_app(test_settings)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    limiter.reset()
