from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bleak import BleakScanner


class MuseBleError(RuntimeError):
    """A safe, operator-facing Bluetooth discovery failure."""


@dataclass(frozen=True, slots=True)
class MuseBleDevice:
    address: str
    name: str


class MuseBleScanner:
    @staticmethod
    async def scan(*, timeout: float) -> list[MuseBleDevice]:
        devices: dict[str, MuseBleDevice] = {}

        def detected(device, advertisement) -> None:
            address = str(getattr(device, "address", "")).strip()
            local_name = str(getattr(advertisement, "local_name", "") or "").strip()
            device_name = str(getattr(device, "name", "") or "").strip()
            name = local_name or device_name
            if address and name.casefold().startswith("muse-"):
                devices[address] = MuseBleDevice(address=address, name=name)

        try:
            scanner = BleakScanner(detection_callback=detected)
            await scanner.start()
            try:
                await asyncio.sleep(max(float(timeout), 0.0))
            finally:
                await scanner.stop()
        except Exception as exc:
            raise MuseBleError("Bluetooth scan failed") from exc

        return sorted(devices.values(), key=lambda item: item.address)
