import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import attributes
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import get_session
from app.fs import FileSystemService, get_fs_service_panels
from app.models import IngestQuery, Panel, Status, Study
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
) -> list[Panel]:
    """List all ingested panels.

    Pass `?available` to list panels on disk instead.
    Pass `?all` to merge both.
    """
    if available is not None:
        return fs.list_panels()
    if all is not None:
        db_panels = list(session.exec(select(Panel)).all())
        db_names = {p.name for p in db_panels}
        fs_only = [p for p in fs.list_panels() if p.name not in db_names]
        return db_panels + fs_only
    return list(session.exec(select(Panel)).all())


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
) -> Panel:
    """Ingest a panel into cBioPortal."""
    panel = fs.get_ingested_panel(data.name)

    if panel:
        if panel.status == Status.COMPLETED:
            if not force:
                raise HTTPException(status_code=400, detail="Panel ingested successfully")
        if panel.status == Status.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Panel ingestion in progress")
        if panel.status in (Status.FAILED, Status.COMPLETED):
            panel.status = Status.INITIAL
            panel.job_id = None
            panel.date_ingested = None
            panel.date_created = datetime.now(UTC)
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
    ):
        raise HTTPException(status_code=409, detail="Another ingestion is already in progress")

    job_timeout = int(os.getenv("JOB_TIMEOUT", "3600"))
    job = queue.enqueue(ingest_panel, panel.id, job_timeout=job_timeout)

    panel.job_id = job.id
    session.add(panel)
    session.commit()
    session.refresh(panel)

    return panel


@router.get("/{panel_id}", responses={404: {"description": "Not Found"}})
async def get_panel(
    panel_id: int,
    session: Session = Depends(get_session),
    token=Depends(verify_token),
) -> Panel:
    """Fetch a single panel by ID."""
    try:
        panel = session.get(Panel, panel_id)
    except OverflowError:
        raise HTTPException(status_code=404, detail="Panel not found")

    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    return panel


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
