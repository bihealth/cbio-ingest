from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth import verify_token
from app.db import get_session
from app.fs import FileSystemService, get_fs_service_panels
from app.models import IngestQuery, Panel, Status
from app.scheduler import queue
from app.tasks import ingest_panel

router = APIRouter(responses={401: {"description": "Unauthorized"}})


@router.get("/")
async def list_panels(
    available: str | None = Query(default=None),
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_panels),
    token=Depends(verify_token),
) -> list[Panel]:
    """List all ingested panels. Pass `?available` to list panels on disk instead."""
    if available is not None:
        return fs.list_panels()
    return list(session.exec(select(Panel)).all())


@router.post("/", status_code=201, responses={400: {"description": "Bad Request"}})
async def create_panel(
    data: IngestQuery,
    session: Session = Depends(get_session),
    fs: FileSystemService = Depends(get_fs_service_panels),
    token=Depends(verify_token),
) -> Panel:
    """Ingest a panel into cBioPortal."""
    panel = fs.get_ingested_panel(data.name)

    if panel:
        if panel.status == Status.COMPLETED:
            raise HTTPException(status_code=400, detail="Panel ingested successfully")
        if panel.status == Status.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Panel ingestion in progress")
        if panel.status == Status.FAILED:
            panel.status = Status.INITIAL
            panel.job_id = None
            panel.date_ingested = None
            session.add(panel)
            session.commit()
            session.refresh(panel)
    else:
        panel = Panel(name=data.name)
        session.add(panel)
        session.commit()
        session.refresh(panel)

    job = queue.enqueue(ingest_panel, panel.id)

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
