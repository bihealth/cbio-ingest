"""Tests for database module."""

from sqlmodel import Session, SQLModel, create_engine

from app.db import add_log, get_session
from app.models import LogLevel, Study

engine = create_engine("sqlite:///:memory:")


def get_test_session():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestGetSession:
    """Tests for get_session function."""

    def test_get_session_yields_session(self):
        """Test that get_session yields a valid session."""
        session_generator = get_session()
        session = next(session_generator)

        assert isinstance(session, Session)
        assert session is not None

        # Cleanup
        try:
            next(session_generator)
        except StopIteration:
            pass


class TestAddLog:
    """Tests for add_log function."""

    def test_add_log_appends_to_logs(self):
        """Test that add_log adds entries to entity logs."""
        study = Study(name="test-study")

        add_log(study, LogLevel.INFO, "test-reporter", "Test message")

        assert len(study.logs) == 1
        assert study.logs[0]["level"] == LogLevel.INFO
        assert study.logs[0]["reporter"] == "test-reporter"
        assert study.logs[0]["message"] == "Test message"
        assert "timestamp" in study.logs[0]

    def test_add_log_multiple_entries(self):
        """Test that multiple logs can be added."""
        study = Study(name="test-study")

        add_log(study, LogLevel.INFO, "worker", "First message")
        add_log(study, LogLevel.ERROR, "docker", "Second message")

        assert len(study.logs) == 2
        assert study.logs[0]["message"] == "First message"
        assert study.logs[1]["message"] == "Second message"
