import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

TOKEN: str | None = os.environ.get("TOKEN") or None

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    if not TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    if not secrets.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")

    return token
