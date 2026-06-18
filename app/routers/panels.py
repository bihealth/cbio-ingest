import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import attributes
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import DbHelper, get_db_helper, get_session
from app.fs import FileSystemService, get_fs_service
from app.models import DeletionResponse, Panel, PanelResponse, Status, Study, TaskInput, Validation
from app.scheduler import queue
from app.tasks import ingest_panel
from app.validator import Validator, get_validator

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_panels(
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    token=Depends(verify_token),
) -> list[PanelResponse]:
    """List all ingested panels."""
    fs_names = set(fs.list_panels())
    db_panels = list(session.exec(select(Panel)).all())
    no_db = [
        PanelResponse.augment(Panel(name=p, status=Status.INITIAL))
        for p in fs_names - {p.name for p in db_panels}
    ]
    db_dbfs = [PanelResponse.augment(p, in_source_folder=p.name in fs_names) for p in db_panels]
    return db_dbfs + no_db


@router.post(
    "/",
    status_code=201,
    responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}},
)
async def create_panel(
    data: TaskInput,
    force: bool = Query(default=False),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    db: DbHelper = Depends(get_db_helper),
    validator: Validator = Depends(get_validator),
    token=Depends(verify_token),
) -> PanelResponse:
    """Ingest a panel into cBioPortal."""

    try:
        validated_name = validator.validate_folder_name(data.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Panel name invalid: {e}")

    panel = db.get_panel_by_name(validated_name)

    if panel:
        if panel.status == Status.COMPLETED and not force:
            raise HTTPException(status_code=400, detail="Panel ingested successfully")

        elif panel.status == Status.IN_PROGRESS and not force:
            raise HTTPException(status_code=400, detail="Panel ingestion in progress")

        elif not fs.panel_exists_on_disk(panel.name):
            raise HTTPException(status_code=400, detail="Panel not found on disk")

        if panel.status in (Status.FAILED, Status.COMPLETED, Status.IN_PROGRESS):
            panel.status = Status.INITIAL
            panel.job_id = None
            panel.date = None
            panel.logs = []
            attributes.flag_modified(panel, "logs")
            session.add(panel)
            session.commit()
            session.refresh(panel)

    else:
        panel = Panel(name=validated_name)
        session.add(panel)
        session.commit()
        session.refresh(panel)

    if (
        any(
            session.exec(select(model).where(model.status == Status.IN_PROGRESS)).first()
            for model in (Study, Panel, Validation)
        )
        and not force
    ):
        raise HTTPException(status_code=409, detail="Another ingestion is already in progress")

    job_timeout = int(os.getenv("JOB_TIMEOUT", "43200"))  # 12 hours
    job = queue.enqueue(ingest_panel, panel.id, job_timeout=job_timeout)

    panel.job_id = job.id
    session.add(panel)
    session.commit()
    session.refresh(panel)

    return PanelResponse.augment(panel, in_source_folder=fs.panel_exists_on_disk(panel.name))


@router.get("/{panel_id}", responses={404: {"description": "Not Found"}})
async def get_panel_by_name(
    panel_id: int,
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service),
    token=Depends(verify_token),
) -> PanelResponse:
    """Fetch a single panel by ID."""
    try:
        panel = session.get(Panel, panel_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Panel not found")

    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    return PanelResponse.augment(panel, in_source_folder=fs.panel_exists_on_disk(panel.name))


@router.delete("/{panel_id}", responses={404: {"description": "Not Found"}})
async def delete_panel(
    panel_id: int,
    session: Session = Depends(get_session),
    token=Depends(verify_token),
) -> DeletionResponse:
    """Delete a panel from cBioPortal."""
    try:
        panel = session.get(Panel, panel_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Panel not found")

    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    session.delete(panel)
    session.commit()

    return DeletionResponse(message=f"Panel with ID {panel_id} deleted successfully")
