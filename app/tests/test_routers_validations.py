"""Tests for validations router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Status, Validation


def _create_study_source(name: str) -> None:
    study_root = Path("/tmp")
    from os import getenv

    study_dir = getenv("STUDY_DIR")
    if study_dir:
        study_root = Path(study_dir)
    study_root.mkdir(parents=True, exist_ok=True)
    (study_root / name).mkdir(parents=True, exist_ok=True)


class TestValidationsRouter:
    """Tests for validations router endpoints."""

    class TestListValidations:
        """Tests for GET /validations/ endpoint."""

        def test_list_validations_empty(self, client: TestClient, auth_headers: dict[str, str]):
            """Test listing validations when database is empty."""
            response = client.get("/validations/", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_list_validations_with_data(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test listing validations with data in database."""
            validation1 = Validation(name="validation1", status=Status.COMPLETED)
            validation2 = Validation(name="validation2", status=Status.IN_PROGRESS)
            session.add(validation1)
            session.add(validation2)
            session.commit()

            response = client.get("/validations/", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert any(v["name"] == "validation1" for v in data)
            assert any(v["name"] == "validation2" for v in data)

        def test_list_validations_unauthorized(self, client: TestClient):
            """Test listing validations without authentication."""
            response = client.get("/validations/")
            assert response.status_code == 401

    class TestCreateValidation:
        """Tests for POST /validations/ endpoint."""

        @patch("app.routers.validations.queue")
        def test_create_validation_success(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a new validation."""
            mock_job = MagicMock()
            mock_job.id = "validation-job-id"
            mock_queue.enqueue.return_value = mock_job

            # Create the study directory on disk because the router checks for it
            _create_study_source("test-study")

            response = client.post(
                "/validations/",
                json={"name": "test-study"},
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-study"
            assert data["status"] == "initial"
            assert data["job_id"] == "validation-job-id"

    class TestGetValidation:
        """Tests for GET /validations/{validation_id} endpoint."""

        def test_get_validation_success(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test fetching a validation by ID."""
            validation = Validation(
                name="test-validation",
                status=Status.IN_PROGRESS,
                job_id="validation-job-123",
            )
            session.add(validation)
            session.commit()
            session.refresh(validation)

            response = client.get(f"/validations/{validation.id}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == validation.id
            assert data["name"] == "test-validation"
            assert data["status"] == "in_progress"
            assert data["job_id"] == "validation-job-123"

        def test_get_validation_not_found(self, client: TestClient, auth_headers: dict[str, str]):
            """Test fetching a non-existent validation."""
            response = client.get("/validations/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Validation not found"

        def test_get_validation_unauthorized(self, client: TestClient):
            """Test fetching validation without authentication."""
            response = client.get("/validations/1")
            assert response.status_code == 401

    class TestDeleteValidation:
        """Tests for DELETE /validations/{validation_id} endpoint."""

        def test_delete_validation_success(
            self,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test deleting a validation."""
            mock_fs = MagicMock()
            from app.fs import get_async_fs_service
            from app.main import app

            async def get_fs_service_override():
                return mock_fs

            app.dependency_overrides[get_async_fs_service] = get_fs_service_override
            try:
                validation = Validation(name="test-validation")
                session.add(validation)
                session.commit()
                session.refresh(validation)

                response = client.delete(f"/validations/{validation.id}", headers=auth_headers)
                assert response.status_code == 200
                assert (
                    response.json()["message"]
                    == f"Validation with ID {validation.id} deleted successfully"
                )
                mock_fs.move_report_to_trash.assert_called_once_with(validation.report)
            finally:
                app.dependency_overrides.pop(get_async_fs_service, None)

        def test_delete_validation_not_found(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
            """Test deleting a non-existent validation."""
            response = client.delete("/validations/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Validation not found"
