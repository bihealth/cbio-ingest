from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from app import auth as _auth
from app.routers.panels import router as panels_router
from app.routers.studies import router as studies_router
from app.routers.validations import router as validations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _auth.TOKEN:
        raise RuntimeError("TOKEN environment variable must be set")
    yield


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)


app.include_router(studies_router, prefix="/studies", tags=["studies"])
app.include_router(panels_router, prefix="/panels", tags=["panels"])
app.include_router(validations_router, prefix="/validations", tags=["validations"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "title": APP_TITLE,
        "description": APP_DESCRIPTION,
        "version": APP_VERSION,
        "docs": "/docs",
    }
