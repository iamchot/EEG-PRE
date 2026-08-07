from __future__ import annotations

import asyncio
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, persona, eeg_session, comic, admin, dataset_collection, muse, system
from app.services.eeg_stream_runner import user_eeg_stream_runner
from app.services.muse_bridge_manager import managed_muse_bridge_manager
from app.ws import eeg_manager  # noqa: F401  (ensure manager is imported)

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (Alembic handles production migrations)
    Base.metadata.create_all(bind=engine)

    # Ensure output directories exist
    os.makedirs(settings.raw_eeg_dir, exist_ok=True)
    os.makedirs(settings.comfyui_output_dir, exist_ok=True)

    # Seed default roles if missing
    _seed_roles()

    try:
        yield
    finally:
        cancellation: asyncio.CancelledError | None = None
        for cleanup in (user_eeg_stream_runner.shutdown, managed_muse_bridge_manager.shutdown):
            try:
                await cleanup()
            except asyncio.CancelledError as exc:
                if cancellation is None:
                    cancellation = exc
            except Exception:
                logger.exception("Muse shutdown cleanup failed")
        if cancellation is not None:
            raise cancellation


def _seed_roles():
    from app.database import SessionLocal
    from app.models.user import Role

    db = SessionLocal()
    try:
        for role_name in ("user", "admin"):
            if not db.query(Role).filter(Role.name == role_name).first():
                db.add(Role(name=role_name))
        db.commit()
    finally:
        db.close()


app = FastAPI(
    title="Dream Comicverse API",
    description="EEG-powered comic generation system — PRD v2.0",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],  # Angular dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static files (ComfyUI panel images) ──────────────────────────────────────
panels_dir = Path(settings.comfyui_output_dir)
panels_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/panels", StaticFiles(directory=str(panels_dir)), name="panels")

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(persona.router, prefix="/api/v1")
app.include_router(eeg_session.router, prefix="/api/v1")
app.include_router(comic.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(dataset_collection.router, prefix="/api/v1")
app.include_router(muse.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Dream Comicverse API"}
