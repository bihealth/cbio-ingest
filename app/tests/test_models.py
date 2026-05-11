"""Tests for models module."""

from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import attributes
from sqlmodel import Session

from app.models import IngestQuery, LogLevel, Panel, Status, Study


class TestStatus:
    """Tests for Status enum."""

    def test_status_values(self):
        """Test that Status enum has expected values."""
        assert Status.INITIAL == "initial"
        assert Status.IN_PROGRESS == "in_progress"
        assert Status.COMPLETED == "completed"
        assert Status.FAILED == "failed"


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self):
        """Test that LogLevel enum has expected values."""
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"


class TestStudy:
    """Tests for Study model."""

    def test_create_study_with_defaults(self, session: Session):
        """Test creating a study with default values."""
        study = Study(name="test-study")
        session.add(study)
        session.commit()
        session.refresh(study)

        assert study.id is not None
        assert study.name == "test-study"
        assert study.status == Status.INITIAL
        assert study.date_ingested is None
        assert study.logs == []
        assert study.job_id is None
        assert study.command is None
        assert study.cbioportal_version is None

    def test_create_study_with_custom_values(self, session: Session):
        """Test creating a study with custom values."""
        now = datetime.now()
        logs = [{"level": "INFO", "message": "Test log"}]
        study = Study(
            name="custom-study",
            status=Status.COMPLETED,
            date_ingested=now,
            logs=logs,
            job_id="job-123",
            command="test-command",
            cbioportal_version="1.0.0",
        )
        session.add(study)
        session.commit()
        session.refresh(study)

        assert study.id is not None
        assert study.name == "custom-study"
        assert study.status == Status.COMPLETED
        assert study.date_ingested == now
        assert study.logs == logs
        assert study.job_id == "job-123"
        assert study.command == "test-command"
        assert study.cbioportal_version == "1.0.0"

    def test_study_update(self, session: Session):
        """Test updating a study."""
        study = Study(name="test-study")
        session.add(study)
        session.commit()
        session.refresh(study)

        study.status = Status.IN_PROGRESS
        study.job_id = "job-456"
        session.add(study)
        session.commit()
        session.refresh(study)

        assert study.status == Status.IN_PROGRESS
        assert study.job_id == "job-456"


class TestPanel:
    """Tests for Panel model."""

    def test_create_panel_with_defaults(self, session: Session):
        """Test creating a panel with default values."""
        panel = Panel(name="test-panel")
        session.add(panel)
        session.commit()
        session.refresh(panel)

        assert panel.id is not None
        assert panel.name == "test-panel"
        assert panel.status == Status.INITIAL
        assert panel.date_ingested is None
        assert panel.logs == []
        assert panel.job_id is None
        assert panel.command is None
        assert panel.cbioportal_version is None

    def test_create_panel_with_custom_values(self, session: Session):
        """Test creating a panel with custom values."""
        now = datetime.now()
        logs = [{"level": "INFO", "message": "Test log"}]
        panel = Panel(
            name="custom-panel",
            status=Status.FAILED,
            date_ingested=now,
            logs=logs,
            job_id="job-789",
            command="test-command-2",
            cbioportal_version="2.0.0",
        )
        session.add(panel)
        session.commit()
        session.refresh(panel)

        assert panel.id is not None
        assert panel.name == "custom-panel"
        assert panel.status == Status.FAILED
        assert panel.date_ingested == now
        assert panel.logs == logs
        assert panel.job_id == "job-789"
        assert panel.command == "test-command-2"
        assert panel.cbioportal_version == "2.0.0"

    def test_panel_update(self, session: Session):
        """Test updating a panel."""
        panel = Panel(name="test-panel")
        session.add(panel)
        session.commit()
        session.refresh(panel)

        panel.status = Status.COMPLETED
        panel.logs.append({"level": "INFO", "message": "Panel ingested"})
        attributes.flag_modified(panel, "logs")
        session.add(panel)
        session.commit()
        session.refresh(panel)

        assert panel.status == Status.COMPLETED
        assert len(panel.logs) == 1
        assert panel.logs[0]["message"] == "Panel ingested"


class TestIngestQuery:
    """Tests for IngestQuery model."""

    def test_create_ingest_query(self):
        """Test creating an ingest query."""
        query = IngestQuery(name="test-item")
        assert query.name == "test-item"

    def test_ingest_query_validation(self):
        """Test that IngestQuery requires a name."""
        with pytest.raises(ValidationError):
            IngestQuery()  # pyright: ignore[reportCallIssue]
