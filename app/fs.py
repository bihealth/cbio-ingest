import os
from pathlib import Path

from fastapi import Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import Panel, PanelResponse, Status, Study, StudyResponse


class FileSystemService:
    """Service for filesystem operations related to cBioPortal data."""

    def __init__(self, session: Session, base_path: str):
        self.base_path = Path(base_path)
        self.session = session

    def get_ingested_study(self, name: str) -> Study | None:
        """Get ingested study by name."""
        stmt = select(Study).where(Study.name == name)
        return self.session.exec(stmt).first()

    def get_ingested_panel(self, name: str) -> Panel | None:
        """Get ingested panel by name."""
        stmt = select(Panel).where(Panel.name == name)
        return self.session.exec(stmt).first()

    def path_exists_on_disk(self, name: str) -> bool:
        """Check if a path exists on disk."""
        return (self.base_path / name).exists()

    def list_studies(self) -> list[StudyResponse]:
        """List all studies in the base path."""
        studies = []

        if not self.base_path.exists():
            return studies

        for entry in os.scandir(self.base_path):
            if entry.is_dir():
                study = self.get_ingested_study(entry.name)  # Check if already ingested
                if not study:
                    study = Study(
                        name=entry.name,
                        status=Status.INITIAL,
                    )
                studies.append(StudyResponse.augment(study, in_source_folder=True))
        return studies

    def list_panels(self) -> list[PanelResponse]:
        """List all panels in the base path."""
        panels = []

        if not self.base_path.exists():
            return panels

        for entry in os.scandir(self.base_path):
            if entry.is_file():
                panel = self.get_ingested_panel(entry.name)  # Check if already ingested
                if not panel:
                    panel = Panel(
                        name=entry.name,
                        status=Status.INITIAL,
                    )
                panels.append(PanelResponse.augment(panel, in_source_folder=True))
        return panels


def get_fs_service_studies(
    session: Session = Depends(get_session),
) -> FileSystemService:
    """Dependency to get filesystem service instance."""
    return FileSystemService(session=session, base_path=os.getenv("STUDY_DIR", "/app/study"))


def get_fs_service_panels(session: Session = Depends(get_session)) -> FileSystemService:
    """Dependency to get filesystem service instance."""
    return FileSystemService(session=session, base_path=os.getenv("PANEL_DIR", "/app/panel"))
