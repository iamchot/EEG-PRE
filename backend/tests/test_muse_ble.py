from __future__ import annotations

import asyncio
import importlib
import importlib.util
from dataclasses import dataclass

import pytest


def _muse_ble_module():
    assert importlib.util.find_spec("app.services.muse_ble") is not None, (
        "Muse BLE scanner module must be available"
    )
    return importlib.import_module("app.services.muse_ble")


@dataclass
class Advertisement:
    local_name: str | None


@dataclass
class Device:
    address: str
    name: str | None = None


def test_scan_keeps_a_later_named_muse_advertisement_for_the_same_address(monkeypatch):
    muse_ble = _muse_ble_module()

    class Scanner:
        def __init__(self, *, detection_callback):
            self.detection_callback = detection_callback

        async def start(self):
            self.detection_callback(Device("AA:BB", None), Advertisement(None))
            self.detection_callback(Device("AA:BB", None), Advertisement("  Muse-A9C7  "))

        async def stop(self):
            return None

    async def no_wait(_timeout):
        return None

    monkeypatch.setattr(muse_ble, "BleakScanner", Scanner)
    monkeypatch.setattr(muse_ble.asyncio, "sleep", no_wait)

    assert asyncio.run(muse_ble.MuseBleScanner.scan(timeout=0.1)) == [
        muse_ble.MuseBleDevice(address="AA:BB", name="Muse-A9C7")
    ]


def test_scan_excludes_non_muse_devices_and_deduplicates_addresses(monkeypatch):
    muse_ble = _muse_ble_module()

    class Scanner:
        def __init__(self, *, detection_callback):
            self.detection_callback = detection_callback

        async def start(self):
            self.detection_callback(Device("CC:DD", "Phone"), Advertisement(None))
            self.detection_callback(Device("BB:CC", "Muse-Z9"), Advertisement(None))
            self.detection_callback(Device("AA:BB", None), Advertisement("mUsE-A1"))
            self.detection_callback(Device("BB:CC", "Muse-Z9"), Advertisement(None))

        async def stop(self):
            return None

    async def no_wait(_timeout):
        return None

    monkeypatch.setattr(muse_ble, "BleakScanner", Scanner)
    monkeypatch.setattr(muse_ble.asyncio, "sleep", no_wait)

    assert asyncio.run(muse_ble.MuseBleScanner.scan(timeout=0.1)) == [
        muse_ble.MuseBleDevice(address="AA:BB", name="mUsE-A1"),
        muse_ble.MuseBleDevice(address="BB:CC", name="Muse-Z9"),
    ]


def test_scan_sanitizes_bluetooth_scanner_exceptions(monkeypatch):
    muse_ble = _muse_ble_module()

    class Scanner:
        def __init__(self, *, detection_callback):
            self.detection_callback = detection_callback

        async def start(self):
            raise RuntimeError("windows adapter COM detail")

        async def stop(self):
            return None

    monkeypatch.setattr(muse_ble, "BleakScanner", Scanner)

    with pytest.raises(muse_ble.MuseBleError, match="^Bluetooth scan failed$") as failure:
        asyncio.run(muse_ble.MuseBleScanner.scan(timeout=0.1))

    assert isinstance(failure.value.__cause__, RuntimeError)
    assert "windows adapter COM detail" not in str(failure.value)
