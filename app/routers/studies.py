import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import attributes
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import get_session
from app.fs import FileSystemService, get_fs_service_studies
from app.models import IngestQuery, Panel, Status, Study, StudyResponse
from app.scheduler import queue
from app.tasks import ingest_study

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_studies(
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_studies),
    token=Depends(verify_token),
) -> list[StudyResponse]:
    """List all ingested studies."""
    db_studies = list(session.exec(select(Study)).all())
    fs_studies = fs.list_studies()
    fs_names = {s.name for s in fs_studies}
    db_only = [
        StudyResponse.augment(study, in_source_folder=False)
        for study in db_studies
        if study.name not in fs_names
    ]
    return fs_studies + db_only


@router.post(
    "/",
    status_code=201,
    responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}},
)
async def create_study(
    data: IngestQuery,
    keep_logs: bool = Query(default=False),
    force: bool = Query(default=False),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_studies),
    token=Depends(verify_token),
) -> StudyResponse:
    """Ingest a study into cBioPortal."""
    study = fs.get_ingested_study(data.name)

    if study:
        if study.status == Status.COMPLETED and not force:
            raise HTTPException(status_code=400, detail="Study ingested successfully")

        elif study.status == Status.IN_PROGRESS and not force:
            raise HTTPException(status_code=400, detail="Study ingestion in progress")

        elif not fs.path_exists_on_disk(study.name):
            raise HTTPException(status_code=400, detail="Study not found on disk")

        if study.status in (Status.FAILED, Status.COMPLETED, Status.IN_PROGRESS):
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

    if (
        session.exec(select(Study).where(Study.status == Status.IN_PROGRESS)).first()
        or session.exec(select(Panel).where(Panel.status == Status.IN_PROGRESS)).first()
    ) and not force:
        raise HTTPException(status_code=409, detail="Another ingestion is already in progress")

    job_timeout = int(os.getenv("JOB_TIMEOUT", "43200"))  # 12 hours
    job = queue.enqueue(ingest_study, study.id, job_timeout=job_timeout)

    study.job_id = job.id
    session.add(study)
    session.commit()
    session.refresh(study)

    return StudyResponse.augment(study, in_source_folder=fs.path_exists_on_disk(study.name))


@router.get("/{study_id}", responses={404: {"description": "Not Found"}})
async def get_study(
    study_id: int,
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_studies),
    token=Depends(verify_token),
) -> StudyResponse:
    """Fetch a single study by ID."""
    try:
        study = session.get(Study, study_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Study not found")

    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    return StudyResponse.augment(study, in_source_folder=fs.path_exists_on_disk(study.name))


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
