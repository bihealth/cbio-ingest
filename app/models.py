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


class Panel(StudyPanelBase, table=True):
    """Panel ingestion result."""

    id: Optional[int] = Field(default=None, primary_key=True)


class IngestQuery(SQLModel):
    """Query model for panel or study ingestion."""

    name: str
