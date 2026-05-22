# cbio-ingest FastAPI application
from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata as _metadata

from dotenv import load_dotenv

load_dotenv()

try:
    _meta = _metadata("cbio-ingest")
    APP_VERSION = _meta["Version"]
    APP_DESCRIPTION = _meta["Summary"]
except PackageNotFoundError:
    APP_VERSION = "0.0.0-dev"
    APP_DESCRIPTION = "REST API for ingesting data into cBioPortal"

APP_TITLE = "cBioPortal Ingest API"
