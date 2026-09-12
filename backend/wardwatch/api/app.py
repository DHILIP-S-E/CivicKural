"""FastAPI app factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import routes_admin, routes_complaints, routes_public, routes_webhook


def create_app() -> FastAPI:
    app = FastAPI(title="WardWatch API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_webhook.router)
    app.include_router(routes_complaints.router)
    app.include_router(routes_admin.router)
    app.include_router(routes_public.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
