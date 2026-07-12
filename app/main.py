"""FastAPI app factory and router registration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, telephony
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    # Telephony providers + console tools hit these URLs from many origins.
    # Wildcard origins cannot be combined with credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(telephony.router, tags=["telephony"])
    return app


app = create_app()
