"""FastAPI application factory.  Run:  uvicorn api.main:app --reload --port 8000"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.errors import install_error_handlers
from api.routers import accounts, alerts, data, graph, search, system


def create_app() -> FastAPI:
    app = FastAPI(
        title="Graph-Based Financial Crime Intelligence API",
        version=__version__,
        description=("HTTP adapter over the `core` analytical library. Alerts are leads for human review, "
                     "not findings of fraud; risk scores are uncalibrated ordinal indices."),
    )
    origins = os.environ.get("FRAUD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins if o.strip()],
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["*"])
    install_error_handlers(app)
    for m in (system, data, accounts, graph, alerts, search):
        app.include_router(m.router)
    return app


app = create_app()
