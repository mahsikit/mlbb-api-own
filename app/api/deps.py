from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def require_jwt(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return credentials.credentials  # HTTPBearer already strips "Bearer "
