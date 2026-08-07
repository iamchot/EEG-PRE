from __future__ import annotations

from fastapi import APIRouter

from app.middleware.auth_middleware import CurrentUser
from app.schemas.system_health import SystemHealth
from app.services.system_health import SystemHealthService

router = APIRouter(prefix="/system", tags=["System"])
system_health_service = SystemHealthService()


@router.get("/health", response_model=SystemHealth)
async def system_health(_current_user: CurrentUser) -> SystemHealth:
    return await system_health_service.get_health()
