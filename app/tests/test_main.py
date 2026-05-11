"""Tests for main application."""

import pytest
from fastapi.testclient import TestClient

from app import APP_VERSION


class TestMainApp:
    """Tests for main application endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "cBioPortal Ingest API"
        assert data["description"] == "REST API for ingesting data into cBioPortal"
        assert data["version"] == APP_VERSION
        assert data["docs"] == "/docs"

    def test_openapi_docs_accessible(self, client: TestClient):
        """Test that OpenAPI docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_accessible(self, client: TestClient):
        """Test that OpenAPI JSON is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "cBioPortal Ingest API"
        assert data["info"]["version"] == APP_VERSION


class TestLifespan:
    """Tests for application lifespan."""

    @pytest.mark.asyncio
    async def test_lifespan_creates_tables(self):
        """Test that lifespan context manager creates database tables."""
        from unittest.mock import MagicMock, patch

        from fastapi import FastAPI

        from app.main import lifespan

        app = FastAPI()

        # Mock the database engine to verify create_all is called
        with patch("app.main.engine") as mock_engine:
            with patch("app.main.SQLModel") as mock_sqlmodel:
                mock_metadata = MagicMock()
                mock_sqlmodel.metadata = mock_metadata

                # Use the lifespan context manager
                async with lifespan(app):
                    # Verify that create_all was called during startup
                    mock_metadata.create_all.assert_called_once_with(mock_engine)
