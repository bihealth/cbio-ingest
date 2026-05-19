import os

from sqlalchemy.orm import attributes
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import get_session
from app.fs import FileSystemService, get_fs_service_studies
from app.models import IngestQuery, Status, Study
from app.scheduler import queue
from app.tasks import ingest_study

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_studies(
    available: str | None = Query(default=None),
    all: str | None = Query(default=None),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_studies),
    token=Depends(verify_token),
) -> list[Study]:
    """List all ingested studies. Pass `?available` to list studies on disk instead. Pass `?all` to merge both."""
    if available is not None:
        return fs.list_studies()
    if all is not None:
        db_studies = list(session.exec(select(Study)).all())
        db_names = {s.name for s in db_studies}
        fs_only = [s for s in fs.list_studies() if s.name not in db_names]
        return db_studies + fs_only
    return list(session.exec(select(Study)).all())


@router.post("/", status_code=201, responses={400: {"description": "Bad Request"}})
async def create_study(
    data: IngestQuery,
    keep_logs: bool = Query(default=False),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_studies),
    token=Depends(verify_token),
) -> Study:
    """Ingest a study into cBioPortal."""
    study = fs.get_ingested_study(data.name)

    if study:
        if study.status == Status.COMPLETED:
            raise HTTPException(status_code=400, detail="Study ingested successfully")
        if study.status == Status.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Study ingestion in progress")
        if study.status == Status.FAILED:
            study.status = Status.INITIAL
            study.job_id = None
            study.date_ingested = None
            if not keep_logs:
                study.logs = []
                attributes.flag_modified(study, "logs")
            session.add(study)
            session.commit()
            session.refresh(study)
    else:
        study = Study(name=data.name)
        session.add(study)
        session.commit()
        session.refresh(study)

    job_timeout = int(os.getenv("JOB_TIMEOUT", "3600"))
    job = queue.enqueue(ingest_study, study.id, job_timeout=job_timeout)

    study.job_id = job.id
    session.add(study)
    session.commit()
    session.refresh(study)

    return study


@router.get("/{study_id}", responses={404: {"description": "Not Found"}})
async def get_study(
    study_id: int,
    session: Session = Depends(get_session),
    token=Depends(verify_token),
) -> Study:
    """Fetch a single study by ID."""
    try:
        study = session.get(Study, study_id)
    except OverflowError:
        raise HTTPException(status_code=404, detail="Study not found")

    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    return study


@router.delete("/{study_id}", responses={404: {"description": "Not Found"}})
async def delete_study(
    study_id: int,
    session: Session = Depends(get_session),
    token=Depends(verify_token),
):
    """Delete a study from cBioPortal."""
    try:
        study = session.get(Study, study_id)
    except OverflowError:
        raise HTTPException(status_code=404, detail="Study not found")

    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    session.delete(study)
    session.commit()

    return {"message": "Study deleted successfully"}
