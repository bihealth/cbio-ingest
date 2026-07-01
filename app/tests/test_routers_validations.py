"""Tests for validations router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Panel, Status, Study, Validation


class TestValidationsRouter:
    """Tests for validations router endpoints."""

    @staticmethod
    def _create_study_source(name: str) -> None:
        study_root = Path("/tmp")
        from os import getenv

        study_dir = getenv("STUDY_DIR")
        if study_dir:
            study_root = Path(study_dir)
        study_root.mkdir(parents=True, exist_ok=True)
        (study_root / name).mkdir(parents=True, exist_ok=True)

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

        def test_list_validations_invalid_token(self, client: TestClient):
            """Test listing validations with invalid token."""
            response = client.get("/validations/", headers={"Authorization": "Bearer invalid"})
            assert response.status_code == 401

    class TestCreateValidation:
        """Tests for POST /validations/ endpoint."""

        @patch("app.routers.validations.queue")
        def test_create_validation_success(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
        ):
            """Test creating a new validation."""
            mock_job = MagicMock()
            mock_job.id = "validation-job-id"
            mock_queue.enqueue.return_value = mock_job

            # Create the study directory on disk because the router checks for it
            TestValidationsRouter._create_study_source("test-study")

            response = client.post(
                "/validations/",
                json={"name": "test-study"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "test-study"
            assert data["status"] == "initial"
            assert data["job_id"] == "validation-job-id"
            assert mock_queue.enqueue.called

        @patch("app.routers.validations.queue")
        def test_create_validation_already_completed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a validation that's already completed."""
            # Add a completed validation
            validation = Validation(name="completed-validation", status=Status.COMPLETED)
            session.add(validation)
            session.commit()

            response = client.post(
                "/validations/",
                json={"name": "completed-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Study validated successfully"

        @patch("app.routers.validations.queue")
        def test_create_validation_already_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a validation that's already in progress without force."""
            # Add an in-progress validation
            validation = Validation(name="inprogress-validation", status=Status.IN_PROGRESS)
            session.add(validation)
            session.commit()

            response = client.post(
                "/validations/",
                json={"name": "inprogress-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Study validation in progress"

        @patch("app.routers.validations.queue")
        def test_create_validation_force_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test force re-ingesting a validation that's already in progress."""
            validation = Validation(name="inprogress-validation-force", status=Status.IN_PROGRESS)
            session.add(validation)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force-inprogress"
            mock_queue.enqueue.return_value = mock_job
            TestValidationsRouter._create_study_source("inprogress-validation-force")

            response = client.post(
                "/validations/?force=true",
                json={"name": "inprogress-validation-force"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "inprogress-validation-force"
            assert data["job_id"] == "job-force-inprogress"
            assert mock_queue.enqueue.called

        @patch("app.routers.validations.queue")
        def test_create_validation_retry_failed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test retrying a failed validation ingestion."""
            # Add a failed validation
            validation = Validation(name="failed-validation", status=Status.FAILED, id=1)
            session.add(validation)
            session.commit()

            # Mock the queue
            mock_job = MagicMock()
            mock_job.id = "job-456"
            mock_queue.enqueue.return_value = mock_job
            TestValidationsRouter._create_study_source("failed-validation")

            response = client.post(
                "/validations/",
                json={"name": "failed-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "failed-validation"
            assert data["job_id"] == "job-456"
            assert data["logs"] == []
            assert mock_queue.enqueue.called

        @patch("app.routers.validations.queue")
        def test_create_validation_force_completed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test force re-ingesting a completed validation."""
            validation = Validation(name="completed-validation-force", status=Status.COMPLETED)
            session.add(validation)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force"
            mock_queue.enqueue.return_value = mock_job
            TestValidationsRouter._create_study_source("completed-validation-force")

            response = client.post(
                "/validations/?force=true",
                json={"name": "completed-validation-force"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "completed-validation-force"
            assert data["job_id"] == "job-force"
            assert data["logs"] == []
            assert mock_queue.enqueue.called

        @patch("app.routers.validations.queue")
        def test_create_validation_conflict_when_another_validation_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a validation returns 409 when a study ingestion is in progress."""
            other_validation = Validation(name="other-study", status=Status.IN_PROGRESS)
            session.add(other_validation)
            session.commit()

            response = client.post(
                "/validations/",
                json={"name": "new-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another task is already in progress"

        @patch("app.routers.validations.queue")
        def test_create_validation_conflict_when_study_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a validation returns 409 when a study ingestion is in progress."""
            other_study = Study(name="other-study", status=Status.IN_PROGRESS)
            session.add(other_study)
            session.commit()

            response = client.post(
                "/validations/",
                json={"name": "new-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another task is already in progress"

        @patch("app.routers.validations.queue")
        def test_create_validation_conflict_when_panel_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a validation returns 409 when another panel ingestion is in
            progress."""
            other_panel = Panel(name="other-panel", status=Status.IN_PROGRESS)
            session.add(other_panel)
            session.commit()

            response = client.post(
                "/validations/",
                json={"name": "new-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another task is already in progress"

        @patch("app.routers.validations.queue")
        def test_create_validation_force_bypasses_conflict(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that force=true bypasses the 409 conflict check."""
            other_study = Study(name="other-study", status=Status.IN_PROGRESS)
            session.add(other_study)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force-conflict"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/validations/?force=true",
                json={"name": "new-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "new-validation"
            assert data["job_id"] == "job-force-conflict"
            assert mock_queue.enqueue.called

        def test_create_validation_unauthorized(self, client: TestClient):
            """Test creating a panel without authentication."""
            response = client.post("/validations/", json={"name": "validation"})
            assert response.status_code == 401

        def test_create_validation_invalid_name(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
            """Test creating a validation with invalid folder name triggers 400."""
            response = client.post(
                "/validations/",
                json={"name": "../bad-folder"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert "Study name invalid" in response.json()["detail"]

        def test_create_validation_not_on_disk(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test creating a validation when the validation record exists but folder is missing
            on disk."""
            validation = Validation(name="missing-validation", status=Status.INITIAL)
            session.add(validation)
            session.commit()

            response = client.post(
                "/validations/",
                json={"name": "missing-validation"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Study not found on disk"

        @patch("app.routers.validations.queue")
        def test_create_validation_attaches_study(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """If a study exists with the same name, creating the validation should attach it."""
            # create a study record
            study = Study(name="attach-study", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            # ensure queue mocked
            mock_job = MagicMock()
            mock_job.id = "job-attach-val"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/validations/",
                json={"name": "attach-study"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            # response should include study_id
            assert data.get("study_id") == study.id

            # refresh DB state and verify the validation.study_id points to the study
            # find the validation by name
            validation = session.exec(
                select(Validation).where(Validation.name == "attach-study")
            ).first()
            assert validation is not None
            assert validation.study_id == study.id

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

        def test_delete_validation_report_missing(
            self,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """If the report file is already gone, the delete should still succeed."""
            mock_fs = MagicMock()
            mock_fs.move_report_to_trash.side_effect = FileNotFoundError
            from app.fs import get_async_fs_service
            from app.main import app

            async def get_fs_service_override():
                return mock_fs

            app.dependency_overrides[get_async_fs_service] = get_fs_service_override
            try:
                validation = Validation(name="test-validation-missing-report")
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

        def test_delete_validation_unauthorized(self, client: TestClient):
            """Test deleting a valdiation without authentication."""
            response = client.delete("/validations/1")
            assert response.status_code == 401
