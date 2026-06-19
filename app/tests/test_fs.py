"""Tests for filesystem service module."""

from pathlib import Path

import pytest

from app.fs import FileSystemService


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
    def fs_service(self) -> FileSystemService:
        """Create a filesystem service."""
        return FileSystemService()

    class TestPathExistsOnDisk:
        """Tests for path_exists_on_disk methods."""

        def test_study_exists_on_disk(self, fs_service: FileSystemService, study_dir: Path):
            """Test existing study directory returns True."""
            (study_dir / "study1").mkdir()

            assert fs_service.study_exists_on_disk("study1") is True

        def test_panel_exists_on_disk(self, fs_service: FileSystemService, panel_dir: Path):
            """Test existing panel file returns True."""
            (panel_dir / "panel1.txt").touch()

            assert fs_service.panel_exists_on_disk("panel1.txt") is True

        def test_study_exists_on_disk_returns_false_when_missing(
            self, fs_service: FileSystemService
        ):
            """Test missing path returns False."""
            assert fs_service.study_exists_on_disk("missing-study") is False

        def test_study_exists_on_disk_returns_false_with_nonexistent_base_path(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
        ):
            """Test missing base path returns False for any child path."""
            nonexistent_dir = tmp_path / "missing-base"
            monkeypatch.setenv("STUDY_DIR", str(nonexistent_dir))
            fs_service = FileSystemService()

            assert fs_service.study_exists_on_disk("anything") is False

    class TestListStudies:
        """Tests for list_studies method."""

        def test_list_studies_empty_directory(self, fs_service: FileSystemService):
            """Test listing studies in an empty directory."""
            studies = fs_service.list_studies()
            assert studies == []

        def test_list_studies_with_directories(
            self, fs_service: FileSystemService, study_dir: Path
        ):
            """Test listing studies with directories present."""
            (study_dir / "study1").mkdir()
            (study_dir / "study2").mkdir()
            (study_dir / "study3").mkdir()

            studies = fs_service.list_studies()
            assert len(studies) == 3
            assert "study1" in studies
            assert "study2" in studies
            assert "study3" in studies

        def test_list_studies_ignores_files(self, fs_service: FileSystemService, study_dir: Path):
            """Test that list_studies ignores files."""
            (study_dir / "study1").mkdir()
            (study_dir / "file.txt").touch()

            studies = fs_service.list_studies()
            assert len(studies) == 1
            assert studies[0] == "study1"

        def test_list_studies_nonexistent_directory(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
        ):
            """Test listing studies when directory doesn't exist."""
            nonexistent_dir = tmp_path / "nonexistent"
            monkeypatch.setenv("STUDY_DIR", str(nonexistent_dir))
            fs_service = FileSystemService()
            studies = fs_service.list_studies()
            assert studies == []

    class TestListPanels:
        """Tests for list_panels method."""

        def test_list_panels_empty_directory(self, fs_service: FileSystemService):
            """Test listing panels in an empty directory."""
            panels = fs_service.list_panels()
            assert panels == []

        def test_list_panels_with_files(self, fs_service: FileSystemService, panel_dir: Path):
            """Test listing panels with files present."""
            (panel_dir / "panel1.txt").touch()
            (panel_dir / "panel2.txt").touch()
            (panel_dir / "panel3.txt").touch()

            panels = fs_service.list_panels()
            assert len(panels) == 3
            assert "panel1.txt" in panels
            assert "panel2.txt" in panels
            assert "panel3.txt" in panels

        def test_list_panels_ignores_directories(
            self, fs_service: FileSystemService, panel_dir: Path
        ):
            """Test that list_panels ignores directories."""
            (panel_dir / "panel1.txt").touch()
            (panel_dir / "subdir").mkdir()

            panels = fs_service.list_panels()
            assert len(panels) == 1
            assert panels[0] == "panel1.txt"

        def test_list_panels_nonexistent_directory(
            self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
        ):
            """Test listing panels when directory doesn't exist."""
            nonexistent_dir = tmp_path / "nonexistent"
            monkeypatch.setenv("PANEL_DIR", str(nonexistent_dir))
            fs_service = FileSystemService()
            panels = fs_service.list_panels()
            assert panels == []
