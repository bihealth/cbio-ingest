"""Smoke tests — verify the application starts and critical paths respond."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestAppStartup:
    def test_root_responds(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200

    def test_openapi_schema_available(self, client: TestClient):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["title"] == "cBioPortal Ingest API"

    def test_docs_available(self, client: TestClient):
        response = client.get("/docs")
        assert response.status_code == 200


class TestStudiesSmoke:
    def test_list_studies(self, client: TestClient, auth_headers: dict):
        response = client.get("/studies/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_studies_available(self, client: TestClient, auth_headers: dict):
        response = client.get("/studies/?available", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_studies_requires_auth(self, client: TestClient):
        response = client.get("/studies/")
        assert response.status_code == 401

    @patch("app.routers.studies.queue")
    def test_create_study(
        self, mock_queue: MagicMock, client: TestClient, auth_headers: dict
    ):
        mock_job = MagicMock()
        mock_job.id = "smoke-job-id"
        mock_queue.enqueue.return_value = mock_job

        response = client.post(
            "/studies/", json={"name": "smoke-study"}, headers=auth_headers
        )
        assert response.status_code == 201
        assert response.json()["name"] == "smoke-study"

    def test_delete_study_not_found(self, client: TestClient, auth_headers: dict):
        response = client.delete("/studies/99999", headers=auth_headers)
        assert response.status_code == 404


class TestPanelsSmoke:
    def test_list_panels(self, client: TestClient, auth_headers: dict):
        response = client.get("/panels/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_panels_available(self, client: TestClient, auth_headers: dict):
        response = client.get("/panels/?available", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_panels_requires_auth(self, client: TestClient):
        response = client.get("/panels/")
        assert response.status_code == 401

    @patch("app.routers.panels.queue")
    def test_create_panel(
        self, mock_queue: MagicMock, client: TestClient, auth_headers: dict
    ):
        mock_job = MagicMock()
        mock_job.id = "smoke-job-id"
        mock_queue.enqueue.return_value = mock_job

        response = client.post(
            "/panels/", json={"name": "smoke-panel.txt"}, headers=auth_headers
        )
        assert response.status_code == 201
        assert response.json()["name"] == "smoke-panel.txt"

    def test_delete_panel_not_found(self, client: TestClient, auth_headers: dict):
        response = client.delete("/panels/99999", headers=auth_headers)
        assert response.status_code == 404
