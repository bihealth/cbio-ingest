from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlmodel import JSON, Field, SQLModel


class Status(str, Enum):
    INITIAL = "initial"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class StudyPanelBase(SQLModel):
    """Base class for ingested entities."""

    name: str
    status: Status = Field(default=Status.INITIAL)
    date_ingested: Optional[datetime] = Field(default=None)
    logs: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    job_id: Optional[str] = None
    command: Optional[str] = None
    cbioportal_version: Optional[str] = None


class Study(StudyPanelBase, table=True):
    """Study ingestion result."""

    id: Optional[int] = Field(default=None, primary_key=True)


class StudyResponse(StudyPanelBase):
    """Study response model with additional fields for API responses."""

    id: Optional[int]
    in_source_folder: bool

    @classmethod
    def augment(
        cls,
        study: Study,
        in_source_folder: bool = False,
        check_source: bool = False,
    ) -> "StudyResponse":
        from app.fs import FileSystemService, get_fs_service_studies

        fs: FileSystemService = get_fs_service_studies()

        if check_source:
            in_source_folder = fs.path_exists_on_disk(study.name)

        return cls(**study.model_dump(), in_source_folder=in_source_folder)


class Panel(StudyPanelBase, table=True):
    """Panel ingestion result."""

    id: Optional[int] = Field(default=None, primary_key=True)


class PanelResponse(StudyPanelBase):
    """Panel response model with additional fields for API responses."""

    id: Optional[int]
    in_source_folder: bool

    @classmethod
    def augment(
        cls,
        panel: Panel,
        in_source_folder: bool = False,
        check_source: bool = False,
    ) -> "PanelResponse":
        from app.fs import FileSystemService, get_fs_service_panels

        fs: FileSystemService = get_fs_service_panels()

        if check_source:
            in_source_folder = fs.path_exists_on_disk(panel.name)

        return cls(**panel.model_dump(), in_source_folder=in_source_folder)


class IngestQuery(SQLModel):
    """Query model for panel or study ingestion."""

    name: str
