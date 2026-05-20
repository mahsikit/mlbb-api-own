from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import user

app = FastAPI(
    title="MLBB API",
    description="Personal MLBB proxy API. See /docs for interactive testing.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router, prefix="/api/user", tags=["User"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "docs": "/docs"}
