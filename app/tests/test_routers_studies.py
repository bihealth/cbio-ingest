"""Tests for studies router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Status, Study


class TestStudiesRouter:
    """Tests for studies router endpoints."""

    class TestListStudies:
        """Tests for GET /studies/ endpoint."""

        def test_list_studies_empty(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
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
            response = client.get(
                "/studies/", headers={"Authorization": "Bearer invalid"}
            )
            assert response.status_code == 401

    class TestListStudiesAll:
        """Tests for GET /studies/?all endpoint."""

        def test_all_studies_empty(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
            """Test ?all when both DB and filesystem are empty."""
            response = client.get("/studies/?all", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_all_studies_db_only(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test ?all returns DB studies even when not on disk."""
            study = Study(name="db-only-study", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            response = client.get("/studies/?all", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "db-only-study"
            assert data[0]["status"] == "completed"

        def test_all_studies_merges_db_and_fs(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test ?all merges DB records and filesystem-only studies without duplicates."""
            study = Study(name="study1", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            response = client.get("/studies/?all", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            names = [s["name"] for s in data]
            # DB study present
            assert "study1" in names
            # No duplicates
            assert len(names) == len(set(names))

        def test_all_studies_unauthorized(self, client: TestClient):
            """Test ?all without authentication."""
            response = client.get("/studies/?all")
            assert response.status_code == 401

    class TestListStudiesAvailable:
        """Tests for GET /studies/?available endpoint."""

        def test_scan_studies_empty_directory(
            self, client: TestClient, auth_headers: dict[str, str], tmp_path: Path
        ):
            """Test scanning studies in empty directory."""
            response = client.get("/studies/?available", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_scan_studies_with_directories(
            self, client: TestClient, auth_headers: dict[str, str], tmp_path: Path
        ):
            """Test scanning studies with directories present."""
            # Create study directories
            study_dir = Path(tmp_path / "studies")
            study_dir.mkdir(exist_ok=True)
            (study_dir / "study1").mkdir()
            (study_dir / "study2").mkdir()

            response = client.get("/studies/?available", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            study_names = [s["name"] for s in data]
            assert "study1" in study_names
            assert "study2" in study_names

        def test_scan_studies_unauthorized(self, client: TestClient):
            """Test scanning studies without authentication."""
            response = client.get("/studies/?available")
            assert response.status_code == 401

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
            """Test creating a study that's already in progress."""
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

            response = client.post(
                "/studies/",
                json={"name": "failed-study"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "failed-study"
            assert data["job_id"] == "job-456"
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

        def test_get_study_not_found(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
            """Test fetching a non-existent study."""
            response = client.get("/studies/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Study not found"

        def test_get_study_unauthorized(self, client: TestClient):
            """Test fetching a study without authentication."""
            response = client.get("/studies/1")
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

        def test_delete_study_not_found(
            self, client: TestClient, auth_headers: dict[str, str]
        ):
            """Test deleting a non-existent study."""
            response = client.delete("/studies/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Study not found"

        def test_delete_study_unauthorized(self, client: TestClient):
            """Test deleting a study without authentication."""
            response = client.delete("/studies/1")
            assert response.status_code == 401
