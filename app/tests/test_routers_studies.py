"""Tests for studies router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Panel, Status, Study, Validation


class TestStudiesRouter:
    """Tests for studies router endpoints."""

    @staticmethod
    def _create_study_source(name: str) -> None:
        study_root = Path("/tmp")
        from os import getenv

        study_dir = getenv("STUDY_DIR")
        if study_dir:
            study_root = Path(study_dir)
        study_root.mkdir(parents=True, exist_ok=True)
        (study_root / name).mkdir(parents=True, exist_ok=True)

    class TestListStudies:
        """Tests for GET /studies/ endpoint."""

        def test_list_studies_empty(self, client: TestClient, auth_headers: dict[str, str]):
            """Test listing studies when database is empty."""
            response = client.get("/studies/", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_list_studies_with_data(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test listing studies with data in database."""
            # Add some studies
            study1 = Study(name="study1", status=Status.COMPLETED)
            study2 = Study(name="study2", status=Status.IN_PROGRESS)
            session.add(study1)
            session.add(study2)
            session.commit()

            response = client.get("/studies/", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert any(s["name"] == "study1" for s in data)
            assert any(s["name"] == "study2" for s in data)

        def test_list_studies_unauthorized(self, client: TestClient):
            """Test listing studies without authentication."""
            response = client.get("/studies/")
            assert response.status_code == 401

        def test_list_studies_invalid_token(self, client: TestClient):
            """Test listing studies with invalid token."""
            response = client.get("/studies/", headers={"Authorization": "Bearer invalid"})
            assert response.status_code == 401

    class TestListStudiesUnion:
        """Tests for merged DB + source listing on GET /studies/."""

        def test_list_studies_db_only_sets_in_source_false(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test DB-only studies are returned with in_source_folder=False."""
            study = Study(name="db-only-study", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            response = client.get("/studies/", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "db-only-study"
            assert data[0]["in_source_folder"] is False

        def test_list_studies_source_only_sets_in_source_true(
            self, client: TestClient, auth_headers: dict[str, str], tmp_path: Path
        ):
            """Test source-only studies are returned with in_source_folder=True."""
            study_dir = Path(tmp_path / "studies")
            study_dir.mkdir(exist_ok=True)
            (study_dir / "source-only-study").mkdir()

            response = client.get("/studies/", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "source-only-study"
            assert data[0]["in_source_folder"] is True
            assert data[0]["status"] == "initial"

        def test_list_studies_merges_sources_without_duplicates(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test merged list has shared, DB-only, and source-only entries with proper flags."""
            session.add(Study(name="shared-study", status=Status.COMPLETED))
            session.add(Study(name="db-only-study", status=Status.FAILED))
            session.commit()
            TestStudiesRouter._create_study_source("shared-study")
            TestStudiesRouter._create_study_source("source-only-study")

            response = client.get("/studies/", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            by_name = {item["name"]: item for item in data}

            assert set(by_name.keys()) == {"shared-study", "db-only-study", "source-only-study"}
            assert by_name["shared-study"]["in_source_folder"] is True
            assert by_name["shared-study"]["status"] == "completed"
            assert by_name["db-only-study"]["in_source_folder"] is False
            assert by_name["source-only-study"]["in_source_folder"] is True

    class TestCreateStudy:
        """Tests for POST /studies/ endpoint."""

        @patch("app.routers.studies.queue")
        def test_create_study_success(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
        ):
            """Test creating a new study."""
            # Mock the queue.enqueue method
            mock_job = MagicMock()
            mock_job.id = "job-123"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/studies/",
                json={"name": "new-study"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "new-study"
            assert data["status"] == "initial"
            assert data["job_id"] == "job-123"
            assert mock_queue.enqueue.called

        @patch("app.routers.studies.queue")
        def test_create_study_already_completed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a study that's already completed."""
            # Add a completed study
            study = Study(name="completed-study", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            response = client.post(
                "/studies/",
                json={"name": "completed-study"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Study ingested successfully"

        @patch("app.routers.studies.queue")
        def test_create_study_already_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a study that's already in progress without force."""
            # Add an in-progress study
            study = Study(name="inprogress-study", status=Status.IN_PROGRESS)
            session.add(study)
            session.commit()

            response = client.post(
                "/studies/",
                json={"name": "inprogress-study"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Study ingestion in progress"

        @patch("app.routers.studies.queue")
        def test_create_study_force_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test force re-ingesting a study that's already in progress."""
            study = Study(name="inprogress-study-force", status=Status.IN_PROGRESS)
            session.add(study)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force-inprogress"
            mock_queue.enqueue.return_value = mock_job
            TestStudiesRouter._create_study_source("inprogress-study-force")

            response = client.post(
                "/studies/?force=true",
                json={"name": "inprogress-study-force"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "inprogress-study-force"
            assert data["job_id"] == "job-force-inprogress"
            assert mock_queue.enqueue.called

        @patch("app.routers.studies.queue")
        def test_create_study_retry_failed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test retrying a failed study ingestion."""
            # Add a failed study
            study = Study(name="failed-study", status=Status.FAILED, id=1)
            session.add(study)
            session.commit()

            # Mock the queue
            mock_job = MagicMock()
            mock_job.id = "job-456"
            mock_queue.enqueue.return_value = mock_job
            TestStudiesRouter._create_study_source("failed-study")

            response = client.post(
                "/studies/",
                json={"name": "failed-study"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "failed-study"
            assert data["job_id"] == "job-456"
            assert data["logs"] == []
            assert mock_queue.enqueue.called

        @patch("app.routers.studies.queue")
        def test_create_study_force_completed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test force re-ingesting a completed study."""
            study = Study(name="completed-study-force", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force"
            mock_queue.enqueue.return_value = mock_job
            TestStudiesRouter._create_study_source("completed-study-force")

            response = client.post(
                "/studies/?force=true",
                json={"name": "completed-study-force"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "completed-study-force"
            assert data["job_id"] == "job-force"
            assert data["logs"] == []
            assert mock_queue.enqueue.called

        @patch("app.routers.studies.queue")
        def test_create_study_conflict_when_another_study_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a study returns 409 when another study ingestion is in
            progress."""
            other_study = Study(name="other-study", status=Status.IN_PROGRESS)
            session.add(other_study)
            session.commit()

            response = client.post(
                "/studies/",
                json={"name": "new-study"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another ingestion is already in progress"

        @patch("app.routers.studies.queue")
        def test_create_study_conflict_when_panel_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a study returns 409 when a panel ingestion is in progress."""
            panel = Panel(name="other-panel.txt", status=Status.IN_PROGRESS)
            session.add(panel)
            session.commit()

            response = client.post(
                "/studies/",
                json={"name": "new-study"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another ingestion is already in progress"

        @patch("app.routers.studies.queue")
        def test_create_study_force_bypasses_conflict(
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
                "/studies/?force=true",
                json={"name": "new-study"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "new-study"
            assert data["job_id"] == "job-force-conflict"
            assert mock_queue.enqueue.called

        def test_create_study_unauthorized(self, client: TestClient):
            """Test creating a study without authentication."""
            response = client.post("/studies/", json={"name": "study"})
            assert response.status_code == 401

    class TestGetStudy:
        """Tests for GET /studies/{study_id} endpoint."""

        def test_get_study_success(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test fetching a single study by ID."""
            study = Study(name="study-get", status=Status.COMPLETED)
            session.add(study)
            session.commit()
            session.refresh(study)

            response = client.get(f"/studies/{study.id}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == study.id
            assert data["name"] == "study-get"
            assert data["status"] == "completed"

        def test_get_study_not_found(self, client: TestClient, auth_headers: dict[str, str]):
            """Test fetching a non-existent study."""
            response = client.get("/studies/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Study not found"

        def test_get_study_unauthorized(self, client: TestClient):
            """Test fetching a study without authentication."""
            response = client.get("/studies/1")
            assert response.status_code == 401

    class TestGetStudyValidation:
        """Tests for GET /studies/{study_id}/validation endpoint."""

        def test_get_study_validation_by_study_name_success(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test fetching a validation by study ID."""
            study = Study(name="study-validation", status=Status.COMPLETED)
            session.add(study)
            session.commit()
            session.refresh(study)

            validation = Validation(
                name="study-validation.html",
                study_id=study.id,
                status=Status.IN_PROGRESS,
                job_id="validation-job-123",
            )
            session.add(validation)
            session.commit()
            session.refresh(validation)

            response = client.get(f"/studies/{study.id}/validation", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == validation.id
            assert data["name"] == "study-validation.html"
            assert data["study_id"] == study.id
            assert data["status"] == "in_progress"
            assert data["job_id"] == "validation-job-123"

        def test_get_study_validation_by_study_name_not_found_when_missing_validation(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test fetching validation for a study without a validation record."""
            study = Study(name="study-no-validation", status=Status.COMPLETED)
            session.add(study)
            session.commit()
            session.refresh(study)

            response = client.get(f"/studies/{study.id}/validation", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Validation not found"

        def test_get_study_validation_by_study_name_not_found_when_study_missing(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
            """Test fetching validation for a missing study."""
            response = client.get("/studies/9999/validation", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Study not found"

        def test_get_study_validation_by_study_name_unauthorized(self, client: TestClient):
            """Test fetching a study validation without authentication."""
            response = client.get("/studies/1/validation")
            assert response.status_code == 401

    class TestDeleteStudy:
        """Tests for DELETE /studies/{study_id} endpoint."""

        def test_delete_study_success(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test deleting a study."""
            # Create a study
            study = Study(name="study-to-delete")
            session.add(study)
            session.commit()
            session.refresh(study)

            response = client.delete(f"/studies/{study.id}", headers=auth_headers)
            assert response.status_code == 200
            assert response.json()["message"] == "Study deleted successfully"

            # Verify study is deleted
            deleted_study = session.get(Study, study.id)
            assert deleted_study is None

        def test_delete_study_not_found(self, client: TestClient, auth_headers: dict[str, str]):
            """Test deleting a non-existent study."""
            response = client.delete("/studies/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Study not found"

        def test_delete_study_unauthorized(self, client: TestClient):
            """Test deleting a study without authentication."""
            response = client.delete("/studies/1")
            assert response.status_code == 401
