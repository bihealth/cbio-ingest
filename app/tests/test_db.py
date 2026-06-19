"""Tests for database module."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.db import DbHelper, add_log, get_session
from app.models import LogLevel, Panel, Status, Study, Validation

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


class TestDbHelper:
    """Tests for DbHelper class."""

    @pytest.fixture
    def db_helper(self, session: Session) -> DbHelper:
        return DbHelper(session)

    class TestGetStudyByName:
        """Tests for get_study_by_name method."""

        def test_get_existing_study(self, db_helper: DbHelper, session: Session):
            """Test getting an existing study from database."""
            study = Study(name="test-study", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            result = db_helper.get_study_by_name("test-study")
            assert result is not None
            assert result.name == "test-study"
            assert result.status == Status.COMPLETED

        def test_get_nonexistent_study(self, db_helper: DbHelper):
            """Test getting a non-existent study returns None."""
            result = db_helper.get_study_by_name("nonexistent")
            assert result is None

    class TestGetPanelByName:
        """Tests for get_panel_by_name method."""

        def test_get_existing_panel(self, db_helper: DbHelper, session: Session):
            """Test getting an existing panel from database."""
            panel = Panel(name="test-panel.txt", status=Status.IN_PROGRESS)
            session.add(panel)
            session.commit()

            result = db_helper.get_panel_by_name("test-panel.txt")
            assert result is not None
            assert result.name == "test-panel.txt"
            assert result.status == Status.IN_PROGRESS

        def test_get_nonexistent_panel(self, db_helper: DbHelper):
            """Test getting a non-existent panel returns None."""
            result = db_helper.get_panel_by_name("nonexistent.txt")
            assert result is None

    class TestGetValidationByName:
        """Tests for get_validation_by_name method."""

        def test_get_existing_validation(self, db_helper: DbHelper, session: Session):
            """Test getting an existing validation from database."""
            validation = Validation(name="test-study", status=Status.COMPLETED)
            session.add(validation)
            session.commit()

            result = db_helper.get_validation_by_name("test-study")
            assert result is not None
            assert result.name == "test-study"
            assert result.status == Status.COMPLETED

        def test_get_nonexistent_validation(self, db_helper: DbHelper):
            """Test getting a non-existent validation returns None."""
            result = db_helper.get_validation_by_name("nonexistent")
            assert result is None

    class TestGetValidationByStudyId:
        """Tests for get_validation_by_study_id method."""

        def test_get_existing_validation(self, db_helper: DbHelper, session: Session):
            """Test getting validation by study ID."""
            validation = Validation(name="test-study", study_id=42, status=Status.COMPLETED)
            session.add(validation)
            session.commit()

            result = db_helper.get_validation_by_study_id(42)
            assert result is not None
            assert result.study_id == 42
            assert result.status == Status.COMPLETED

        def test_get_nonexistent_validation(self, db_helper: DbHelper):
            """Test getting a non-existent validation by study ID returns None."""
            result = db_helper.get_validation_by_study_id(999)
            assert result is None

    class TestGetStudyValidationById:
        """Tests for get_study_validation_by_id method."""

        def test_get_existing_study_and_validation(self, db_helper: DbHelper, session: Session):
            """Test getting study and its validation by ID."""
            study = Study(id=10, name="test-study", status=Status.COMPLETED)
            validation = Validation(name="test-study", study_id=10, status=Status.COMPLETED)
            session.add(study)
            session.add(validation)
            session.commit()

            db_study, db_validation = db_helper.get_study_validation_by_id(10)
            assert db_study is not None
            assert db_study.id == 10
            assert db_validation is not None
            assert db_validation.study_id == 10

        def test_get_study_without_validation(self, db_helper: DbHelper, session: Session):
            """Test getting study without validation returns (study, None)."""
            study = Study(id=20, name="test-study2", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            db_study, db_validation = db_helper.get_study_validation_by_id(20)
            assert db_study is not None
            assert db_study.id == 20
            assert db_validation is None

        def test_get_nonexistent_study(self, db_helper: DbHelper):
            """Test getting a non-existent study returns (None, None)."""
            db_study, db_validation = db_helper.get_study_validation_by_id(999)
            assert db_study is None
            assert db_validation is None
