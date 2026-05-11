import os
from datetime import UTC, datetime

from sqlalchemy.orm import attributes
from sqlmodel import Session, create_engine

from app.models import Panel, Study

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


def add_log(entity: Study | Panel, level: str, reporter: str, message: str):
    entity.logs.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "reporter": reporter,
            "message": message,
        }
    )
    attributes.flag_modified(entity, "logs")
