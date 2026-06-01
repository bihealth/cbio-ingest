import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import attributes
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import get_session
from app.fs import FileSystemService, get_fs_service_panels
from app.models import IngestQuery, Panel, PanelResponse, Status, Study
from app.scheduler import queue
from app.tasks import ingest_panel

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_panels(
    available: str | None = Query(default=None),
    all: str | None = Query(default=None),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_panels),
    token=Depends(verify_token),
) -> list[PanelResponse]:
    """List all ingested panels.

    Pass `?available` to list panels on disk instead.
    Pass `?all` to merge both.
    """
    if available is not None:
        return fs.list_panels()

    if all is not None:
        db_panels = list(session.exec(select(Panel)).all())
        fs_panels = fs.list_panels()
        fs_names = {s.name for s in fs_panels}
        db_only = [
            PanelResponse.augment(panel, in_source_folder=False)
            for panel in db_panels
            if panel.name not in fs_names
        ]
        return fs_panels + db_only

    return [PanelResponse.augment(panel) for panel in session.exec(select(Panel)).all()]


@router.post(
    "/",
    status_code=201,
    responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}},
)
async def create_panel(
    data: IngestQuery,
    keep_logs: bool = Query(default=False),
    force: bool = Query(default=False),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_panels),
    token=Depends(verify_token),
) -> PanelResponse:
    """Ingest a panel into cBioPortal."""
    panel = fs.get_ingested_panel(data.name)

    if panel:
        if panel.status == Status.COMPLETED and not force:
            raise HTTPException(status_code=400, detail="Panel ingested successfully")

        elif panel.status == Status.IN_PROGRESS and not force:
            raise HTTPException(status_code=400, detail="Panel ingestion in progress")

        elif not fs.path_exists_on_disk(panel.name):
            raise HTTPException(status_code=400, detail="Panel not found on disk")

        if panel.status in (Status.FAILED, Status.COMPLETED, Status.IN_PROGRESS):
            panel.status = Status.INITIAL
            panel.job_id = None
            panel.date_ingested = None
            if not keep_logs:
                panel.logs = []
                attributes.flag_modified(panel, "logs")
            session.add(panel)
            session.commit()
            session.refresh(panel)

    else:
        panel = Panel(name=data.name)
        session.add(panel)
        session.commit()
        session.refresh(panel)

    if (
        session.exec(select(Study).where(Study.status == Status.IN_PROGRESS)).first()
        or session.exec(select(Panel).where(Panel.status == Status.IN_PROGRESS)).first()
    ) and not force:
        raise HTTPException(status_code=409, detail="Another ingestion is already in progress")

    job_timeout = int(os.getenv("JOB_TIMEOUT", "43200"))  # 12 hours
    job = queue.enqueue(ingest_panel, panel.id, job_timeout=job_timeout)

    panel.job_id = job.id
    session.add(panel)
    session.commit()
    session.refresh(panel)

    return PanelResponse.augment(panel, in_source_folder=fs.path_exists_on_disk(panel.name))


@router.get("/{panel_id}", responses={404: {"description": "Not Found"}})
async def get_panel(
    panel_id: int,
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_panels),
    token=Depends(verify_token),
) -> PanelResponse:
    """Fetch a single panel by ID."""
    try:
        panel = session.get(Panel, panel_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Panel not found")

    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    return PanelResponse.augment(panel, in_source_folder=fs.path_exists_on_disk(panel.name))


@router.delete("/{panel_id}", responses={404: {"description": "Not Found"}})
async def delete_panel(
    panel_id: int,
    session: Session = Depends(get_session),
    token=Depends(verify_token),
):
    """Delete a panel from cBioPortal."""
    try:
        panel = session.get(Panel, panel_id)

    except OverflowError:
        raise HTTPException(status_code=404, detail="Panel not found")

    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    session.delete(panel)
    session.commit()

    return {"message": "Panel deleted successfully"}
