"""Pytest configuration and fixtures for cbio-ingest tests."""

import os
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database session override."""

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_token() -> str:
    """Mock authentication token."""
    return "test-token"


@pytest.fixture(autouse=True)
def patch_auth_token(mock_token: str):
    """Automatically patch auth.TOKEN for all tests."""
    with patch("app.auth.TOKEN", mock_token):
        yield


@pytest.fixture(autouse=True)
def set_test_env(tmp_path):
    """Set environment variables for testing."""
    os.environ["STUDY_DIR"] = str(tmp_path / "studies")
    os.environ["PANEL_DIR"] = str(tmp_path / "panels")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = "6379"
    yield
    # Clean up
    for key in [
        "STUDY_DIR",
        "PANEL_DIR",
        "DATABASE_URL",
        "REDIS_HOST",
        "REDIS_PORT",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def auth_headers(mock_token: str) -> dict[str, str]:
    """Generate authentication headers for API requests."""
    return {"Authorization": f"Bearer {mock_token}"}
