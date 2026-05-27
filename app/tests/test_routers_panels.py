"""Tests for panels router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Panel, Status, Study


class TestPanelsRouter:
    """Tests for panels router endpoints."""

    class TestListPanels:
        """Tests for GET /panels/ endpoint."""

        def test_list_panels_empty(self, client: TestClient, auth_headers: dict[str, str]):
            """Test listing panels when database is empty."""
            response = client.get("/panels/", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_list_panels_with_data(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test listing panels with data in database."""
            # Add some panels
            panel1 = Panel(name="panel1.txt", status=Status.COMPLETED)
            panel2 = Panel(name="panel2.txt", status=Status.IN_PROGRESS)
            session.add(panel1)
            session.add(panel2)
            session.commit()

            response = client.get("/panels/", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert any(p["name"] == "panel1.txt" for p in data)
            assert any(p["name"] == "panel2.txt" for p in data)

        def test_list_panels_unauthorized(self, client: TestClient, mock_token: str):
            """Test listing panels without authentication."""
            response = client.get("/panels/")
            assert response.status_code == 401

        def test_list_panels_invalid_token(self, client: TestClient):
            """Test listing panels with invalid token."""
            response = client.get("/panels/", headers={"Authorization": "Bearer invalid"})
            assert response.status_code == 401

    class TestListPanelsAll:
        """Tests for GET /panels/?all endpoint."""

        def test_all_panels_empty(self, client: TestClient, auth_headers: dict[str, str]):
            """Test ?all when both DB and filesystem are empty."""
            response = client.get("/panels/?all", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_all_panels_db_only(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test ?all returns DB panels even when not on disk."""
            panel = Panel(name="db-only.txt", status=Status.COMPLETED)
            session.add(panel)
            session.commit()

            response = client.get("/panels/?all", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "db-only.txt"
            assert data[0]["status"] == "completed"

        def test_all_panels_merges_db_and_fs(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test ?all merges DB records and filesystem-only panels without duplicates."""
            panel = Panel(name="panel1.txt", status=Status.COMPLETED)
            session.add(panel)
            session.commit()

            response = client.get("/panels/?all", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            names = [p["name"] for p in data]
            # DB panel present
            assert "panel1.txt" in names
            # No duplicates
            assert len(names) == len(set(names))

        def test_all_panels_unauthorized(self, client: TestClient):
            """Test ?all without authentication."""
            response = client.get("/panels/?all")
            assert response.status_code == 401

    class TestListPanelsAvailable:
        """Tests for GET /panels/?available endpoint."""

        def test_scan_panels_empty_directory(
            self, client: TestClient, auth_headers: dict[str, str], tmp_path: Path
        ):
            """Test scanning panels in empty directory."""
            response = client.get("/panels/?available", headers=auth_headers)
            assert response.status_code == 200
            assert response.json() == []

        def test_scan_panels_with_files(
            self, client: TestClient, auth_headers: dict[str, str], tmp_path: Path
        ):
            """Test scanning panels with files present."""
            # Create panel files
            panel_dir = Path(tmp_path / "panels")
            panel_dir.mkdir(exist_ok=True)
            (panel_dir / "panel1.txt").touch()
            (panel_dir / "panel2.txt").touch()

            response = client.get("/panels/?available", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            panel_names = [p["name"] for p in data]
            assert "panel1.txt" in panel_names
            assert "panel2.txt" in panel_names

        def test_scan_panels_unauthorized(self, client: TestClient):
            """Test scanning panels without authentication."""
            response = client.get("/panels/?available")
            assert response.status_code == 401

    class TestCreatePanel:
        """Tests for POST /panels/ endpoint."""

        @patch("app.routers.panels.queue")
        def test_create_panel_success(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
        ):
            """Test creating a new panel."""
            # Mock the queue.enqueue method
            mock_job = MagicMock()
            mock_job.id = "job-123"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/",
                json={"name": "new-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "new-panel.txt"
            assert data["status"] == "initial"
            assert data["job_id"] == "job-123"
            assert mock_queue.enqueue.called

        @patch("app.routers.panels.queue")
        def test_create_panel_already_completed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a panel that's already completed."""
            # Add a completed panel
            panel = Panel(name="completed-panel.txt", status=Status.COMPLETED)
            session.add(panel)
            session.commit()

            response = client.post(
                "/panels/",
                json={"name": "completed-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Panel ingested successfully"

        @patch("app.routers.panels.queue")
        def test_create_panel_already_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test creating a panel that's already in progress without force."""
            # Add an in-progress panel
            panel = Panel(name="inprogress-panel.txt", status=Status.IN_PROGRESS)
            session.add(panel)
            session.commit()

            response = client.post(
                "/panels/",
                json={"name": "inprogress-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Panel ingestion in progress"

        @patch("app.routers.panels.queue")
        def test_create_panel_force_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test force re-ingesting a panel that's already in progress."""
            panel = Panel(name="inprogress-panel-force.txt", status=Status.IN_PROGRESS)
            session.add(panel)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force-inprogress"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/?force=true",
                json={"name": "inprogress-panel-force.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "inprogress-panel-force.txt"
            assert data["job_id"] == "job-force-inprogress"
            assert mock_queue.enqueue.called

        @patch("app.routers.panels.queue")
        def test_create_panel_retry_failed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test retrying a failed panel ingestion."""
            # Add a failed panel
            panel = Panel(name="failed-panel.txt", status=Status.FAILED, id=1)
            session.add(panel)
            session.commit()

            # Mock the queue
            mock_job = MagicMock()
            mock_job.id = "job-456"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/",
                json={"name": "failed-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "failed-panel.txt"
            assert data["job_id"] == "job-456"
            assert mock_queue.enqueue.called

        @patch("app.routers.panels.queue")
        def test_create_panel_retry_failed_purges_logs_by_default(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that retrying a failed panel purges logs by default."""
            panel = Panel(
                name="failed-panel-logs.txt",
                status=Status.FAILED,
                logs=[{"level": "ERROR", "message": "previous error"}],
            )
            session.add(panel)
            session.commit()
            session.refresh(panel)

            mock_job = MagicMock()
            mock_job.id = "job-789"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/",
                json={"name": "failed-panel-logs.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert response.json()["logs"] == []

        @patch("app.routers.panels.queue")
        def test_create_panel_retry_failed_keep_logs(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that retrying a failed panel preserves logs when keep_logs=true."""
            panel = Panel(
                name="failed-panel-keeplogs.txt",
                status=Status.FAILED,
                logs=[{"level": "ERROR", "message": "previous error"}],
            )
            session.add(panel)
            session.commit()
            session.refresh(panel)

            mock_job = MagicMock()
            mock_job.id = "job-789"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/?keep_logs=true",
                json={"name": "failed-panel-keeplogs.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert len(response.json()["logs"]) == 1

        @patch("app.routers.panels.queue")
        def test_create_panel_force_completed(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test force re-ingesting a completed panel."""
            panel = Panel(name="completed-panel-force.txt", status=Status.COMPLETED)
            session.add(panel)
            session.commit()

            mock_job = MagicMock()
            mock_job.id = "job-force"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/?force=true",
                json={"name": "completed-panel-force.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "completed-panel-force.txt"
            assert data["job_id"] == "job-force"
            assert mock_queue.enqueue.called

        @patch("app.routers.panels.queue")
        def test_create_panel_force_completed_purges_logs_by_default(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that force re-ingesting a completed panel purges logs by default."""
            panel = Panel(
                name="completed-panel-force-logs.txt",
                status=Status.COMPLETED,
                logs=[{"level": "INFO", "message": "previous success"}],
            )
            session.add(panel)
            session.commit()
            session.refresh(panel)

            mock_job = MagicMock()
            mock_job.id = "job-force-logs"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/?force=true",
                json={"name": "completed-panel-force-logs.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert response.json()["logs"] == []

        @patch("app.routers.panels.queue")
        def test_create_panel_force_completed_keep_logs(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that force re-ingesting a completed panel preserves logs when keep_logs=true."""
            panel = Panel(
                name="completed-panel-force-keeplogs.txt",
                status=Status.COMPLETED,
                logs=[{"level": "INFO", "message": "previous success"}],
            )
            session.add(panel)
            session.commit()
            session.refresh(panel)

            mock_job = MagicMock()
            mock_job.id = "job-force-keeplogs"
            mock_queue.enqueue.return_value = mock_job

            response = client.post(
                "/panels/?force=true&keep_logs=true",
                json={"name": "completed-panel-force-keeplogs.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert len(response.json()["logs"]) == 1

        @patch("app.routers.panels.queue")
        def test_create_panel_conflict_when_study_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a panel returns 409 when a study ingestion is in progress."""
            other_study = Study(name="other-study", status=Status.IN_PROGRESS)
            session.add(other_study)
            session.commit()

            response = client.post(
                "/panels/",
                json={"name": "new-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another ingestion is already in progress"

        @patch("app.routers.panels.queue")
        def test_create_panel_conflict_when_another_panel_in_progress(
            self,
            mock_queue: MagicMock,
            client: TestClient,
            auth_headers: dict[str, str],
            session: Session,
        ):
            """Test that creating a panel returns 409 when another panel ingestion is in
            progress."""
            other_panel = Panel(name="other-panel.txt", status=Status.IN_PROGRESS)
            session.add(other_panel)
            session.commit()

            response = client.post(
                "/panels/",
                json={"name": "new-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "Another ingestion is already in progress"

        @patch("app.routers.panels.queue")
        def test_create_panel_force_bypasses_conflict(
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
                "/panels/?force=true",
                json={"name": "new-panel.txt"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "new-panel.txt"
            assert data["job_id"] == "job-force-conflict"
            assert mock_queue.enqueue.called

        def test_create_panel_unauthorized(self, client: TestClient):
            """Test creating a panel without authentication."""
            response = client.post("/panels/", json={"name": "panel.txt"})
            assert response.status_code == 401

    class TestGetPanel:
        """Tests for GET /panels/{panel_id} endpoint."""

        def test_get_panel_success(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test fetching a single panel by ID."""
            panel = Panel(name="panel-get.txt", status=Status.COMPLETED)
            session.add(panel)
            session.commit()
            session.refresh(panel)

            response = client.get(f"/panels/{panel.id}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == panel.id
            assert data["name"] == "panel-get.txt"
            assert data["status"] == "completed"

        def test_get_panel_not_found(self, client: TestClient, auth_headers: dict[str, str]):
            """Test fetching a non-existent panel."""
            response = client.get("/panels/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Panel not found"

        def test_get_panel_unauthorized(self, client: TestClient):
            """Test fetching a panel without authentication."""
            response = client.get("/panels/1")
            assert response.status_code == 401

    class TestDeletePanel:
        """Tests for DELETE /panels/{panel_id} endpoint."""

        def test_delete_panel_success(
            self, client: TestClient, auth_headers: dict[str, str], session: Session
        ):
            """Test deleting a panel."""
            # Create a panel
            panel = Panel(name="panel-to-delete.txt")
            session.add(panel)
            session.commit()
            session.refresh(panel)

            response = client.delete(f"/panels/{panel.id}", headers=auth_headers)
            assert response.status_code == 200
            assert response.json()["message"] == "Panel deleted successfully"

            # Verify panel is deleted
            deleted_panel = session.get(Panel, panel.id)
            assert deleted_panel is None

        def test_delete_panel_not_found(self, client: TestClient, auth_headers: dict[str, str]):
            """Test deleting a non-existent panel."""
            response = client.delete("/panels/9999", headers=auth_headers)
            assert response.status_code == 404
            assert response.json()["detail"] == "Panel not found"

        def test_delete_panel_unauthorized(self, client: TestClient):
            """Test deleting a panel without authentication."""
            response = client.delete("/panels/1")
            assert response.status_code == 401
