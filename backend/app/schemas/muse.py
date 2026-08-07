from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MuseBridgeState(str, Enum):
    idle = "idle"
    scanning = "scanning"
    found = "found"
    not_found = "not_found"
    starting_bridge = "starting_bridge"
    connecting_bluetooth = "connecting_bluetooth"
    waiting_for_lsl = "waiting_for_lsl"
    connected = "connected"
    failed = "failed"
    disconnecting = "disconnecting"


class MuseOwner(BaseModel):
    model_config = {"frozen": True}

    kind: Literal["user", "collection"]
    session_id: int = Field(gt=0)


class MuseScanDevice(BaseModel):
    address: str
    name: str


class MuseScanStatus(BaseModel):
    scan_id: str
    state: MuseBridgeState
    devices: list[MuseScanDevice] = Field(default_factory=list)
    detail: Literal["scan_failed"] | None = None


class MuseConnectionStatus(BaseModel):
    owner: MuseOwner
    state: MuseBridgeState
    detail: Literal[
        "device_in_use",
        "bridge_exited",
        "bluetooth_timeout",
        "lsl_timeout",
        "bridge_failed",
    ] | None = None
