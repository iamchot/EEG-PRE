from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ServiceHealthState(str, Enum):
    unknown = "unknown"
    checking = "checking"
    available = "available"
    degraded = "degraded"
    unavailable = "unavailable"


class ServiceHealth(BaseModel):
    state: ServiceHealthState
    detail: str
    checked_at: datetime
    latency_ms: int | None = None


class SystemHealth(BaseModel):
    api: ServiceHealth
    comfyui: ServiceHealth
    gemini: ServiceHealth
    muse: ServiceHealth
