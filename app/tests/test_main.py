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
    async def test_lifespan_checks_token(self):
        """Test that lifespan raises RuntimeError if TOKEN is not set."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from app.main import lifespan

        app = FastAPI()

        # When TOKEN is set (which is patched by default in conftest.py)
        async with lifespan(app):
            pass

        # When TOKEN is empty
        with patch("app.auth.TOKEN", ""):
            with pytest.raises(RuntimeError, match="TOKEN environment variable must be set"):
                async with lifespan(app):
                    pass
