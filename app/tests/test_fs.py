"""Tests for filesystem service module."""

from pathlib import Path

import pytest
from sqlmodel import Session

from app.fs import FileSystemService
from app.models import Panel, Status, Study


class TestFileSystemService:
    """Tests for FileSystemService class."""

    @pytest.fixture
    def study_dir(self, tmp_path: Path) -> Path:
        """Create a temporary study directory."""
        study_dir = tmp_path / "studies"
        study_dir.mkdir()
        return study_dir

    @pytest.fixture
    def panel_dir(self, tmp_path: Path) -> Path:
        """Create a temporary panel directory."""
        panel_dir = tmp_path / "panels"
        panel_dir.mkdir()
        return panel_dir

    @pytest.fixture
    def fs_service_studies(
        self, session: Session, study_dir: Path
    ) -> FileSystemService:
        """Create a filesystem service for studies."""
        return FileSystemService(session=session, base_path=str(study_dir))

    @pytest.fixture
    def fs_service_panels(self, session: Session, panel_dir: Path) -> FileSystemService:
        """Create a filesystem service for panels."""
        return FileSystemService(session=session, base_path=str(panel_dir))

    class TestGetIngestedStudy:
        """Tests for get_ingested_study method."""

        def test_get_existing_study(
            self, fs_service_studies: FileSystemService, session: Session
        ):
            """Test getting an existing study from database."""
            study = Study(name="test-study", status=Status.COMPLETED)
            session.add(study)
            session.commit()

            result = fs_service_studies.get_ingested_study("test-study")
            assert result is not None
            assert result.name == "test-study"
            assert result.status == Status.COMPLETED

        def test_get_nonexistent_study(self, fs_service_studies: FileSystemService):
            """Test getting a non-existent study returns None."""
            result = fs_service_studies.get_ingested_study("nonexistent")
            assert result is None

    class TestGetIngestedPanel:
        """Tests for get_ingested_panel method."""

        def test_get_existing_panel(
            self, fs_service_panels: FileSystemService, session: Session
        ):
            """Test getting an existing panel from database."""
            panel = Panel(name="test-panel.txt", status=Status.IN_PROGRESS)
            session.add(panel)
            session.commit()

            result = fs_service_panels.get_ingested_panel("test-panel.txt")
            assert result is not None
            assert result.name == "test-panel.txt"
            assert result.status == Status.IN_PROGRESS

        def test_get_nonexistent_panel(self, fs_service_panels: FileSystemService):
            """Test getting a non-existent panel returns None."""
            result = fs_service_panels.get_ingested_panel("nonexistent.txt")
            assert result is None

    class TestListStudies:
        """Tests for list_studies method."""

        def test_list_studies_empty_directory(
            self, fs_service_studies: FileSystemService
        ):
            """Test listing studies in an empty directory."""
            studies = fs_service_studies.list_studies()
            assert studies == []

        def test_list_studies_with_directories(
            self, fs_service_studies: FileSystemService, study_dir: Path
        ):
            """Test listing studies with directories present."""
            # Create some study directories
            (study_dir / "study1").mkdir()
            (study_dir / "study2").mkdir()
            (study_dir / "study3").mkdir()

            studies = fs_service_studies.list_studies()
            assert len(studies) == 3
            study_names = [s.name for s in studies]
            assert "study1" in study_names
            assert "study2" in study_names
            assert "study3" in study_names

            # All should have INITIAL status
            for study in studies:
                assert study.status == Status.INITIAL
                assert study.id is None  # Not persisted

        def test_list_studies_with_ingested_study(
            self,
            fs_service_studies: FileSystemService,
            study_dir: Path,
            session: Session,
        ):
            """Test listing studies with some already ingested."""
            # Create directories
            (study_dir / "study1").mkdir()
            (study_dir / "study2").mkdir()

            # Add one to database
            ingested_study = Study(name="study1", status=Status.COMPLETED)
            session.add(ingested_study)
            session.commit()

            studies = fs_service_studies.list_studies()
            assert len(studies) == 2

            # Check that ingested study has COMPLETED status
            study1 = next(s for s in studies if s.name == "study1")
            assert study1.status == Status.COMPLETED

            # Check that non-ingested study has INITIAL status
            study2 = next(s for s in studies if s.name == "study2")
            assert study2.status == Status.INITIAL

        def test_list_studies_ignores_files(
            self, fs_service_studies: FileSystemService, study_dir: Path
        ):
            """Test that list_studies ignores files."""
            (study_dir / "study1").mkdir()
            (study_dir / "file.txt").touch()

            studies = fs_service_studies.list_studies()
            assert len(studies) == 1
            assert studies[0].name == "study1"

        def test_list_studies_nonexistent_directory(
            self, session: Session, tmp_path: Path
        ):
            """Test listing studies when directory doesn't exist."""
            nonexistent_dir = tmp_path / "nonexistent"
            fs_service = FileSystemService(
                session=session, base_path=str(nonexistent_dir)
            )
            studies = fs_service.list_studies()
            assert studies == []

    class TestListPanels:
        """Tests for list_panels method."""

        def test_list_panels_empty_directory(
            self, fs_service_panels: FileSystemService
        ):
            """Test listing panels in an empty directory."""
            panels = fs_service_panels.list_panels()
            assert panels == []

        def test_list_panels_with_files(
            self, fs_service_panels: FileSystemService, panel_dir: Path
        ):
            """Test listing panels with files present."""
            # Create some panel files
            (panel_dir / "panel1.txt").touch()
            (panel_dir / "panel2.txt").touch()
            (panel_dir / "panel3.txt").touch()

            panels = fs_service_panels.list_panels()
            assert len(panels) == 3
            panel_names = [p.name for p in panels]
            assert "panel1.txt" in panel_names
            assert "panel2.txt" in panel_names
            assert "panel3.txt" in panel_names

            # All should have INITIAL status
            for panel in panels:
                assert panel.status == Status.INITIAL
                assert panel.id is None  # Not persisted

        def test_list_panels_with_ingested_panel(
            self,
            fs_service_panels: FileSystemService,
            panel_dir: Path,
            session: Session,
        ):
            """Test listing panels with some already ingested."""
            # Create files
            (panel_dir / "panel1.txt").touch()
            (panel_dir / "panel2.txt").touch()

            # Add one to database
            ingested_panel = Panel(name="panel1.txt", status=Status.FAILED)
            session.add(ingested_panel)
            session.commit()

            panels = fs_service_panels.list_panels()
            assert len(panels) == 2

            # Check that ingested panel has FAILED status
            panel1 = next(p for p in panels if p.name == "panel1.txt")
            assert panel1.status == Status.FAILED

            # Check that non-ingested panel has INITIAL status
            panel2 = next(p for p in panels if p.name == "panel2.txt")
            assert panel2.status == Status.INITIAL

        def test_list_panels_ignores_directories(
            self, fs_service_panels: FileSystemService, panel_dir: Path
        ):
            """Test that list_panels ignores directories."""
            (panel_dir / "panel1.txt").touch()
            (panel_dir / "subdir").mkdir()

            panels = fs_service_panels.list_panels()
            assert len(panels) == 1
            assert panels[0].name == "panel1.txt"

        def test_list_panels_nonexistent_directory(
            self, session: Session, tmp_path: Path
        ):
            """Test listing panels when directory doesn't exist."""
            nonexistent_dir = tmp_path / "nonexistent"
            fs_service = FileSystemService(
                session=session, base_path=str(nonexistent_dir)
            )
            panels = fs_service.list_panels()
            assert panels == []
