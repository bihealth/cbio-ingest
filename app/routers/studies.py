import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import attributes
from sqlmodel import Session, col, select

from app.auth import verify_token
from app.db import DbHelper, get_db_helper, get_session
from app.fs import FileSystemService, get_fs_service
from app.models import (
    DeletionResponse,
    Panel,
    Status,
    Study,
    StudyResponse,
    TaskInput,
    Validation,
)
from app.scheduler import queue
from app.tasks import ingest_study
from app.validator import Validator, get_validator

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_studies(
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    token=Depends(verify_token),
) -> list[StudyResponse]:
    """List all ingested studies."""
    # scan file system for studies and reports
    fs_names = set(fs.list_studies())
    fs_reports = set(fs.list_reports())
    # fetch studies and validations if exist
    db_studies = list(session.exec(select(Study, Validation).outerjoin(Validation)).all())
    db_studies_names = {s.name for s, _ in db_studies}
    db_reports = {v.report for _, v in db_studies if v}

    # fetch remaining validations not connected to a study
    db_orphaned_validations = list(
        session.exec(select(Validation).where(col(Validation.study_id).is_(None))).all()
    )
    db_orphaned_validations_by_name = {v.name: v.id for v in db_orphaned_validations}
    db_orphaned_reports = {v.report for v in db_orphaned_validations}

    # warn about orphaned reports without validation in db
    for report in fs_reports - db_reports - db_orphaned_reports:
        print(
            f"Warning: Report found on disk without corresponding validation in database: {report}"
        )

    # studies that exist on disk but are not yet in the db. can have a validation
    no_db = [
        StudyResponse.augment(
            Study(name=s),
            in_source_folder=True,
            validation_id=db_orphaned_validations_by_name.get(s),
        )
        for s in fs_names - db_studies_names
    ]

    # studies that exists in the db
    db_dbfs = [
        StudyResponse.augment(
            s, in_source_folder=s.name in fs_names, validation_id=v.id if v else None
        )
        for s, v in db_studies
    ]

    return db_dbfs + no_db


@router.post(
    "/",
    status_code=201,
    responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}},
)
async def create_study(
    data: TaskInput,
    force: bool = Query(default=False),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    db: DbHelper = Depends(get_db_helper),
    validator: Validator = Depends(get_validator),
    token=Depends(verify_token),
) -> StudyResponse:
    """Ingest a study into cBioPortal."""

    try:
        validated_name = validator.validate_folder_name(data.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Study name invalid: {e}")

    study = db.get_study_by_name(validated_name)

    if study:
        if study.status == Status.COMPLETED and not force:
            raise HTTPException(status_code=400, detail="Study ingested successfully")

        elif study.status == Status.IN_PROGRESS and not force:
            raise HTTPException(status_code=400, detail="Study ingestion in progress")

        elif not fs.study_exists_on_disk(study.name):
            raise HTTPException(status_code=400, detail="Study not found on disk")

        if study.status in (Status.FAILED, Status.COMPLETED, Status.IN_PROGRESS):
            study.status = Status.INITIAL
            study.job_id = None
            study.date = None
            study.logs = []
            attributes.flag_modified(study, "logs")
            session.add(study)
            session.commit()
            session.refresh(study)

    else:
        study = Study(name=validated_name)
        session.add(study)
        session.commit()
        session.refresh(study)

        validation = db.get_validation_by_name(validated_name)

        if validation:
            validation.study_id = study.id
            session.add(validation)
            session.commit()
            session.refresh(validation)

    if (
        any(
            session.exec(select(model).where(model.status == Status.IN_PROGRESS)).first()
            for model in (Study, Panel, Validation)
        )
        and not force
    ):
        raise HTTPException(status_code=409, detail="Another ingestion is already in progress")

    job_timeout = int(os.getenv("JOB_TIMEOUT", "43200"))  # 12 hours
    job = queue.enqueue(ingest_study, study.id, job_timeout=job_timeout)

    study.job_id = job.id
    session.add(study)
    session.commit()
    session.refresh(study)

    return StudyResponse.augment(study, in_source_folder=fs.study_exists_on_disk(study.name))


@router.get("/{study_id}", responses={404: {"description": "Not Found"}})
async def get_study_by_name(
    study_id: int,
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    token=Depends(verify_token),
) -> StudyResponse:
    """Fetch a single study by ID."""
    try:
        study = session.get(Study, study_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Study not found")

    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    return StudyResponse.augment(study, in_source_folder=fs.study_exists_on_disk(study.name))


@router.delete("/{study_id}", responses={404: {"description": "Not Found"}})
async def delete_study(
    study_id: int,
    session: Session = Depends(get_session),
    db: DbHelper = Depends(get_db_helper),
    token=Depends(verify_token),
) -> DeletionResponse:
    """Delete a study from cBioPortal."""
    try:
        study = session.get(Study, study_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Study not found")

    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    validation = db.get_validation_by_study_id(study_id)

    if validation:
        validation.study_id = None
        session.add(validation)
        session.commit()

    session.delete(study)
    session.commit()

    return DeletionResponse(message=f"Study with ID {study_id} deleted successfully")
