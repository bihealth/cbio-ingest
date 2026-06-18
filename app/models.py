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


class Task(SQLModel):
    """Base class for task entities."""

    name: str
    status: Status = Field(default=Status.INITIAL)
    date: Optional[datetime] = Field(default=None)
    logs: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    job_id: Optional[str] = None
    command: Optional[str] = None
    cbioportal_version: Optional[str] = None


class Study(Task, table=True):
    """Study ingestion result."""

    id: Optional[int] = Field(default=None, primary_key=True)


class StudyResponse(Task):
    """Study response model with additional fields for API responses."""

    id: Optional[int]
    in_source_folder: bool
    validation_id: Optional[int] = None

    @classmethod
    def augment(
        cls,
        study: Study,
        in_source_folder: bool = False,
        validation_id: Optional[int] = None,
    ) -> "StudyResponse":
        return cls(
            **study.model_dump(), in_source_folder=in_source_folder, validation_id=validation_id
        )


class Panel(Task, table=True):
    """Panel ingestion result."""

    id: Optional[int] = Field(default=None, primary_key=True)


class PanelResponse(Task):
    """Panel response model with additional fields for API responses."""

    id: Optional[int]
    in_source_folder: bool

    @classmethod
    def augment(
        cls,
        panel: Panel,
        in_source_folder: bool = False,
    ) -> "PanelResponse":
        return cls(**panel.model_dump(), in_source_folder=in_source_folder)


class Validation(Task, table=True):
    """Study validation result."""

    id: Optional[int] = Field(default=None, primary_key=True)
    study_id: Optional[int] = Field(default=None, foreign_key="study.id")

    @property
    def report(self) -> str:
        return f"{self.name}.html"


class ValidationResponse(Task):
    """Validation response model with additional fields for API responses."""

    id: Optional[int]
    study_id: Optional[int]

    @classmethod
    def augment(
        cls,
        validation: Validation,
    ) -> "ValidationResponse":
        return cls(**validation.model_dump())


class TaskInput(SQLModel):
    """Query model for panel or study ingestion."""

    name: str


class DeletionResponse(SQLModel):
    """Response model for deletion endpoints."""

    message: str
