import os
from datetime import UTC, datetime

from fastapi import Depends
from sqlalchemy.orm import attributes
from sqlmodel import Session, create_engine, select

from app.models import Panel, Study, Validation

# Use /app-data in containers, fallback to current dir for local dev
DB_DIR = os.getenv("DB_DIR", "/db")
DATABASE_URL = f"sqlite:///{DB_DIR}/cbio-ingest.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # important for FastAPI + SQLite
)


def get_session():
    with Session(engine) as session:
        yield session


async def get_async_session():
    with Session(engine) as session:
        yield session


def add_log(entity: Study | Panel | Validation, level: str, reporter: str, message: str) -> None:
    entity.logs.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "reporter": reporter,
            "message": message,
        }
    )
    attributes.flag_modified(entity, "logs")


class DbHelper:
    """Helper class for database operations related to studies and panels."""

    def __init__(self, session: Session):
        self.session = session

    def get_study_by_name(self, name: str) -> Study | None:
        """Get ingested study by name."""
        stmt = select(Study).where(Study.name == name)
        return self.session.exec(stmt).first()

    def get_panel_by_name(self, name: str) -> Panel | None:
        """Get ingested panel by name."""
        stmt = select(Panel).where(Panel.name == name)
        return self.session.exec(stmt).first()

    def get_validation_by_name(self, name: str) -> Validation | None:
        """Get validation by name."""
        stmt = select(Validation).where(Validation.name == name)
        return self.session.exec(stmt).first()

    def get_validation_by_study_id(self, study_id: int) -> Validation | None:
        """Get validation by study ID."""
        stmt = select(Validation).where(Validation.study_id == study_id)
        return self.session.exec(stmt).first()

    def get_study_validation_by_id(self, study_id: int) -> tuple[Study | None, Validation | None]:
        """Get ingested study and its validation by ID."""
        stmt = select(Study, Validation).where(Study.id == study_id).outerjoin(Validation)
        result = self.session.exec(stmt).first()
        return result if result else (None, None)


def get_db_helper(session: Session = Depends(get_session)) -> DbHelper:
    """Dependency to get database helper instance."""
    return DbHelper(session=session)


async def get_async_db_helper(session: Session = Depends(get_async_session)) -> DbHelper:
    """Dependency to get database helper instance without using the sync threadpool."""
    return DbHelper(session=session)
