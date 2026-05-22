"""Tests for tasks module."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlmodel import Session

from app.models import LogLevel, Panel, Status, Study
from app.tasks import (
    ingest_panel,
    ingest_study,
    mark_completed,
    mark_failed,
    mark_in_progress,
)


class TestMarkInProgress:
    """Tests for mark_in_progress function."""

    def test_mark_study_in_progress(self, session: Session):
        """Test marking a study as in progress."""
        study = Study(name="test-study", status=Status.INITIAL)
        session.add(study)
        session.commit()
        session.refresh(study)

        mark_in_progress(study, session)

        assert study.status == Status.IN_PROGRESS
        assert len(study.logs) == 1
        assert study.logs[0]["level"] == LogLevel.INFO
        assert study.logs[0]["reporter"] == "worker"
        assert "Ingestion started" in study.logs[0]["message"]

    def test_mark_panel_in_progress(self, session: Session):
        """Test marking a panel as in progress."""
        panel = Panel(name="test-panel.txt", status=Status.INITIAL)
        session.add(panel)
        session.commit()
        session.refresh(panel)

        mark_in_progress(panel, session)

        assert panel.status == Status.IN_PROGRESS
        assert len(panel.logs) == 1
        assert panel.logs[0]["level"] == LogLevel.INFO


class TestMarkCompleted:
    """Tests for mark_completed function."""

    def test_mark_study_completed(self, session: Session):
        """Test marking a study as completed."""
        study = Study(name="test-study", status=Status.IN_PROGRESS)
        session.add(study)
        session.commit()
        session.refresh(study)

        mark_completed(study, session)

        assert study.status == Status.COMPLETED
        assert len(study.logs) == 1
        assert study.logs[0]["level"] == LogLevel.INFO
        assert study.logs[0]["reporter"] == "worker"
        assert "Ingestion completed" in study.logs[0]["message"]

    def test_mark_panel_completed(self, session: Session):
        """Test marking a panel as completed."""
        panel = Panel(name="test-panel.txt", status=Status.IN_PROGRESS)
        session.add(panel)
        session.commit()
        session.refresh(panel)

        mark_completed(panel, session)

        assert panel.status == Status.COMPLETED
        assert len(panel.logs) == 1
        assert panel.logs[0]["level"] == LogLevel.INFO


class TestMarkFailed:
    """Tests for mark_failed function."""

    def test_mark_study_failed(self, session: Session):
        """Test marking a study as failed."""
        study = Study(name="test-study", status=Status.IN_PROGRESS)
        session.add(study)
        session.commit()
        session.refresh(study)

        error_msg = "Docker container not found"
        mark_failed(study, error_msg, session)

        assert study.status == Status.FAILED
        assert len(study.logs) == 1
        assert study.logs[0]["level"] == LogLevel.ERROR
        assert study.logs[0]["reporter"] == "worker"
        assert error_msg in study.logs[0]["message"]

    def test_mark_panel_failed(self, session: Session):
        """Test marking a panel as failed."""
        panel = Panel(name="test-panel.txt", status=Status.IN_PROGRESS)
        session.add(panel)
        session.commit()
        session.refresh(panel)

        error_msg = "Validation failed"
        mark_failed(panel, error_msg, session)

        assert panel.status == Status.FAILED
        assert len(panel.logs) == 1
        assert panel.logs[0]["level"] == LogLevel.ERROR


class TestIngestStudy:
    """Tests for ingest_study function."""

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_study_success(self, mock_session_class: Mock, mock_docker: Mock):
        """Test successful study ingestion."""
        # Setup mocks
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        study = Study(id=1, name="test-study", status=Status.INITIAL)
        session.get.return_value = study

        # Mock Docker client and container
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        # Mock streaming low-level API
        mock_client.api.exec_create.return_value = {"Id": "exec-id-123"}
        mock_client.api.exec_start.return_value = iter([b"Successfully imported study\n"])
        mock_client.api.exec_inspect.return_value = {"ExitCode": 0}

        mock_container.attrs = {"Config": {"Image": "cbioportal:5.0.0"}}

        # Run the task
        with patch.dict("os.environ", {"CBIOPORTAL_CONTAINER_NAME": "test-container"}):
            ingest_study(1)

        # Verify Docker operations
        mock_docker.from_env.assert_called_once_with(timeout=3600)
        mock_client.containers.get.assert_called_once_with("test-container")
        mock_client.api.exec_create.assert_called_once()
        mock_client.api.exec_start.assert_called_once()
        mock_container.restart.assert_called_once()

        # Verify study status
        assert study.status == Status.COMPLETED
        assert study.command is not None
        assert study.cbioportal_version == "cbioportal:5.0.0"
        assert study.date_ingested is not None

    @patch("app.tasks.Session")
    def test_ingest_study_not_found(self, mock_session_class: Mock):
        """Test ingesting a non-existent study."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session
        session.get.return_value = None

        with pytest.raises(ValueError, match="Study with ID 999 not found"):
            ingest_study(999)

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_study_container_not_found(self, mock_session_class: Mock, mock_docker: Mock):
        """Test study ingestion when Docker container is not found."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        study = Study(id=1, name="test-study", status=Status.INITIAL)
        session.get.return_value = study

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.containers.get.side_effect = Exception("Container not found")

        with pytest.raises(Exception, match="Container not found"):
            ingest_study(1)

        # Verify study was marked as failed
        assert study.status == Status.FAILED

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_study_execution_failure(self, mock_session_class: Mock, mock_docker: Mock):
        """Test study ingestion with non-zero exit code."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        study = Study(id=1, name="test-study", status=Status.INITIAL)
        session.get.return_value = study

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        # Mock failed execution
        mock_client.api.exec_create.return_value = {"Id": "exec-id-fail"}
        mock_client.api.exec_start.return_value = iter([b"Error: Failed to import study\n"])
        mock_client.api.exec_inspect.return_value = {"ExitCode": 1}

        mock_container.attrs = {"Config": {"Image": "cbioportal:5.0.0"}}

        ingest_study(1)

        # Verify study was marked as failed
        assert study.status == Status.FAILED
        assert "exit code 1" in study.logs[-1]["message"]

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_study_invalid_name(self, mock_session_class: Mock, mock_docker: Mock):
        """Test study ingestion with invalid folder name."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        study = Study(id=1, name="../malicious", status=Status.INITIAL)
        session.get.return_value = study

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with pytest.raises(Exception):
            ingest_study(1)

        # Verify study was marked as failed
        assert study.status == Status.FAILED


class TestIngestPanel:
    """Tests for ingest_panel function."""

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_panel_success(self, mock_session_class: Mock, mock_docker: Mock):
        """Test successful panel ingestion."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        panel = Panel(id=1, name="test-panel.txt", status=Status.INITIAL)
        session.get.return_value = panel

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_client.api.exec_create.return_value = {"Id": "exec-id-panel"}
        mock_client.api.exec_start.return_value = iter([b"Successfully imported panel\n"])
        mock_client.api.exec_inspect.return_value = {"ExitCode": 0}

        mock_container.attrs = {"Config": {"Image": "cbioportal:5.0.0"}}

        with patch.dict("os.environ", {"CBIOPORTAL_CONTAINER_NAME": "test-container"}):
            ingest_panel(1)

        mock_docker.from_env.assert_called_once_with(timeout=3600)
        mock_client.containers.get.assert_called_once_with("test-container")
        mock_client.api.exec_create.assert_called_once()
        mock_client.api.exec_start.assert_called_once()
        mock_container.restart.assert_called_once()

        assert panel.status == Status.COMPLETED
        assert panel.command is not None
        assert panel.cbioportal_version == "cbioportal:5.0.0"
        assert panel.date_ingested is not None

    @patch("app.tasks.Session")
    def test_ingest_panel_not_found(self, mock_session_class: Mock):
        """Test ingesting a non-existent panel."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session
        session.get.return_value = None

        with pytest.raises(ValueError, match="Panel with ID 999 not found"):
            ingest_panel(999)

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_panel_execution_failure(self, mock_session_class: Mock, mock_docker: Mock):
        """Test panel ingestion with non-zero exit code."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        panel = Panel(id=1, name="test-panel.txt", status=Status.INITIAL)
        session.get.return_value = panel

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_client.api.exec_create.return_value = {"Id": "exec-id-fail-panel"}
        mock_client.api.exec_start.return_value = iter([b"Error: Failed to import panel\n"])
        mock_client.api.exec_inspect.return_value = {"ExitCode": 1}

        mock_container.attrs = {"Config": {"Image": "cbioportal:5.0.0"}}

        ingest_panel(1)

        assert panel.status == Status.FAILED
        assert "exit code 1" in panel.logs[-1]["message"]

    @patch("app.tasks.docker")
    @patch("app.tasks.Session")
    def test_ingest_panel_docker_exception(self, mock_session_class: Mock, mock_docker: Mock):
        """Test panel ingestion with Docker exception."""
        session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = session

        panel = Panel(id=1, name="test-panel.txt", status=Status.INITIAL)
        session.get.return_value = panel

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.containers.get.side_effect = Exception("Docker daemon not running")

        with pytest.raises(Exception, match="Docker daemon not running"):
            ingest_panel(1)

        assert panel.status == Status.FAILED
