import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import attributes
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import DbHelper, get_db_helper, get_session
from app.fs import FileSystemService, get_fs_service
from app.models import (
    DeletionResponse,
    Panel,
    Status,
    Study,
    TaskInput,
    Validation,
    ValidationResponse,
)
from app.scheduler import queue
from app.tasks import validate_study
from app.validator import Validator, get_validator

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_validations(
    session: Session = Depends(get_session),
    token=Depends(verify_token),
) -> list[ValidationResponse]:
    """List all validations."""
    return [ValidationResponse.augment(v) for v in session.exec(select(Validation)).all()]


@router.post("/", responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}})
async def create_validation(
    data: TaskInput,
    force: bool = Query(default=False),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    db: DbHelper = Depends(get_db_helper),
    validator: Validator = Depends(get_validator),
    token=Depends(verify_token),
) -> ValidationResponse:
    """Create a validation for a study."""

    try:
        validated_name = validator.validate_folder_name(data.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Study name invalid: {e}")

    validation = db.get_validation_by_name(validated_name)

    if validation:
        if validation.status == Status.COMPLETED and not force:
            raise HTTPException(status_code=400, detail="Study validated successfully")

        elif validation.status == Status.IN_PROGRESS and not force:
            raise HTTPException(status_code=400, detail="Study validation in progress")

        elif not fs.study_exists_on_disk(validation.name):
            raise HTTPException(status_code=400, detail="Study not found on disk")

        if validation.status in (Status.FAILED, Status.COMPLETED, Status.IN_PROGRESS):
            validation.status = Status.INITIAL
            validation.job_id = None
            validation.date = None
            validation.logs = []
            attributes.flag_modified(validation, "logs")
            session.add(validation)
            session.commit()
            session.refresh(validation)

    else:
        validation = Validation(name=validated_name)
        study = db.get_study_by_name(validated_name)

        if study:
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
        raise HTTPException(status_code=409, detail="Another task is already in progress")

    job_timeout = int(os.getenv("JOB_TIMEOUT", "43200"))  # 12 hours
    job = queue.enqueue(validate_study, validation.id, job_timeout=job_timeout)

    validation.job_id = job.id
    session.add(validation)
    session.commit()
    session.refresh(validation)

    return ValidationResponse.augment(validation)


@router.get("/{validation_id}", responses={404: {"description": "Not Found"}})
async def get_study_validation(
    validation_id: int,
    session: Session = Depends(get_session),
    token=Depends(verify_token),
) -> ValidationResponse:
    """Fetch the validation job for a study by study ID."""
    try:
        validation = session.get(Validation, validation_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Validation not found")

    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")

    return ValidationResponse.augment(validation)


@router.delete("/{validation_id}", responses={404: {"description": "Not Found"}})
async def delete_study_validation(
    validation_id: int,
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    token=Depends(verify_token),
) -> DeletionResponse:
    """Delete a study validation."""
    try:
        validation = session.get(Validation, validation_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Validation not found")

    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")

    fs.move_report_to_trash(validation.report)

    session.delete(validation)
    session.commit()

    return DeletionResponse(message=f"Validation with ID {validation_id} deleted successfully")
