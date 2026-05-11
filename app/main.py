from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from app import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from app import auth as _auth
from app.db import engine
from app.routers.panels import router as panels_router
from app.routers.studies import router as studies_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _auth.TOKEN:
        raise RuntimeError("TOKEN environment variable must be set")
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)


app.include_router(studies_router, prefix="/studies", tags=["studies"])
app.include_router(panels_router, prefix="/panels", tags=["panels"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "title": APP_TITLE,
        "description": APP_DESCRIPTION,
        "version": APP_VERSION,
        "docs": "/docs",
    }
