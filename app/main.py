from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)
    app.include_router(v1_router)
    return app


app = create_app()