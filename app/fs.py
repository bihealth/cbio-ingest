import os
from datetime import datetime
from pathlib import Path


class FileSystemService:
    """Service for filesystem operations related to cBioPortal data."""

    def __init__(self):
        self.base_path_study = Path(os.getenv("STUDY_DIR", "/app/study"))
        self.base_path_panel = Path(os.getenv("PANEL_DIR", "/app/panel"))
        self.base_path_report = Path(os.getenv("REPORT_DIR", "/app/report"))

    def study_exists_on_disk(self, name: str) -> bool:
        """Check if a path exists on disk."""
        return (self.base_path_study / name).exists()

    def panel_exists_on_disk(self, name: str) -> bool:
        """Check if a panel exists on disk."""
        return (self.base_path_panel / name).exists()

    def report_exists_on_disk(self, name: str) -> bool:
        """Check if a report exists on disk."""
        return (self.base_path_report / name).exists()

    def _list_entries(self, base_path: Path, file: bool) -> list[str]:
        """List all entries in a given base path."""
        entries = []

        if not base_path.exists():
            return entries

        for entry in os.scandir(base_path):
            if file and entry.is_file():
                entries.append(entry.name)

            elif not file and entry.is_dir():
                entries.append(entry.name)

        return entries

    def list_studies(self) -> list[str]:
        """List all studies in the base path."""
        return self._list_entries(self.base_path_study, file=False)

    def list_panels(self) -> list[str]:
        """List all panels in the base path."""
        return self._list_entries(self.base_path_panel, file=True)

    def list_reports(self) -> list[str]:
        """List all reports in the base path."""
        return self._list_entries(self.base_path_report, file=True)

    def move_report_to_trash(self, name: str) -> None:
        """Move a report to the trash."""
        trash_path = self.base_path_report / "trash"
        trash_path.mkdir(exist_ok=True)

        source_path = self.base_path_report / name

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        target_path = trash_path / f"{source_path.stem}_{timestamp}{source_path.suffix}"

        if not source_path.exists():
            raise FileNotFoundError(f"Report {name} not found on disk")

        source_path.rename(target_path)


def get_fs_service() -> FileSystemService:
    """Dependency to get filesystem service instance."""
    return FileSystemService()


async def get_async_fs_service() -> FileSystemService:
    """Dependency to get filesystem service instance without using the sync threadpool."""
    return FileSystemService()
