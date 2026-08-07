from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import CurrentUser
from app.schemas.muse import MuseScanStatus
from app.services.muse_bridge_manager import managed_muse_bridge_manager


router = APIRouter(prefix="/muse", tags=["Muse"])


@router.post("/scans", response_model=MuseScanStatus, status_code=status.HTTP_202_ACCEPTED)
async def start_muse_scan(current_user: CurrentUser, db: Session = Depends(get_db)):
    del db
    return await managed_muse_bridge_manager.start_scan(current_user.id)


@router.get("/scans/{scan_id}", response_model=MuseScanStatus)
async def get_muse_scan(scan_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    del db
    try:
        return await managed_muse_bridge_manager.get_scan(current_user.id, scan_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Muse scan not found") from exc
