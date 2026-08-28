"""FastAPI entrypoint for the NADI backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.api import admin as admin_routes
from app.api import auth as auth_routes
from app.api import user_applications
from app.api.routes import router
from app.core.app_database import AppBase, app_database_path, create_app_sqlite_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    engine = create_app_sqlite_engine(app_database_path())
    AppBase.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="TVS NADI",
    description="Adaptive Credit Path Engine backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_routes.router)
app.include_router(user_applications.router)
app.include_router(admin_routes.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a simple service health response."""
    return {"status": "ok"}
