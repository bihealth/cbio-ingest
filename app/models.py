from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, TypeDecorator
from sqlmodel import JSON, Field, SQLModel


class TZDateTime(TypeDecorator):  # type: ignore[type-arg]
    """Stores datetimes as naive UTC; always returns timezone-aware datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


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
    date_ingested: Optional[datetime] = Field(default=None, sa_type=TZDateTime)
    date_created: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_type=TZDateTime)
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
