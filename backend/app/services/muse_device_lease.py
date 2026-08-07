from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from filelock import FileLock, Timeout

from app.services.muse_stream import MuseStreamError


_device_registry_guard = threading.Lock()
_device_registry: dict[str, object] = {}


class DeviceLeaseUnavailableError(MuseStreamError):
    """Public, device-neutral conflict raised when acquisition is already owned."""


class DeviceLease:
    """A nonblocking process registry plus crash-safe OS file lease for one device."""

    def __init__(self, lock_dir: str | Path, device_id: str):
        digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
        self.path = Path(lock_dir) / f"{digest}.lock"
        self._digest = digest
        self._owner = object()
        self._lock = FileLock(self.path)
        self._acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _device_registry_guard:
            if self._digest in _device_registry:
                raise DeviceLeaseUnavailableError("Muse device is already in use")
            _device_registry[self._digest] = self._owner
        try:
            self._lock.acquire(timeout=0)
        except BaseException as exc:
            with _device_registry_guard:
                if _device_registry.get(self._digest) is self._owner:
                    _device_registry.pop(self._digest, None)
            if isinstance(exc, Timeout):
                raise DeviceLeaseUnavailableError("Muse device is already in use") from exc
            raise
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self._lock.release()
        finally:
            with _device_registry_guard:
                if _device_registry.get(self._digest) is self._owner:
                    _device_registry.pop(self._digest, None)
            self._acquired = False
