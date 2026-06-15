from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt5 import QtCore
from pylsl import StreamInlet, resolve_byprop


MUSE_CHANNELS = ["TP9", "AF7", "AF8", "TP10"]
DEFAULT_SAMPLING_RATE = 256.0


def configure_windows_ble() -> None:
    """Allow Bleak/WinRT to run from a Qt GUI process on Windows."""
    if sys.platform != "win32":
        return

    try:
        from bleak.backends.winrt.util import allow_sta

        allow_sta()
    except Exception:
        # Older Bleak versions do not expose this helper. Discovery will report
        # the original backend error if Windows BLE cannot initialize.
        pass


@dataclass
class MuseDevice:
    name: str
    address: str


def _stream_muse(address: str, backend: str) -> None:
    configure_windows_ble()
    from muselsl import stream

    stream(address=address, backend=backend, ppg_enabled=False, acc_enabled=False, gyro_enabled=False)


class MuseConnector(QtCore.QObject):
    status_changed = QtCore.pyqtSignal(str)
    device_changed = QtCore.pyqtSignal(str)

    def __init__(self, backend: str = "auto", parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.backend = backend
        self.device: Optional[MuseDevice] = None
        self._stream_process: Optional[subprocess.Popen] = None

    @property
    def is_streaming(self) -> bool:
        return bool(self._stream_process and self._stream_process.poll() is None)

    def discover(self) -> Optional[MuseDevice]:
        self.status_changed.emit("Searching for Muse 2...")
        try:
            configure_windows_ble()
            from muselsl import list_muses

            muses = list_muses(backend=self.backend)
        except Exception as exc:
            self.status_changed.emit(f"Discovery failed: {exc}")
            return None

        if not muses:
            self.status_changed.emit("No Muse device found")
            return None

        muse = muses[0]
        name = str(muse.get("name", "Muse 2"))
        address = str(muse.get("address", ""))
        self.device = MuseDevice(name=name, address=address)
        self.device_changed.emit(f"{name} ({address})")
        self.status_changed.emit("Muse found")
        return self.device

    def start_stream(self) -> bool:
        if self.is_streaming:
            return True

        if self.device is None and self.discover() is None:
            return False

        assert self.device is not None
        self.status_changed.emit("Starting Muse LSL stream...")
        code = (
            "import sys; "
            "from muse_connector import configure_windows_ble; "
            "configure_windows_ble(); "
            "from muselsl import stream; "
            "stream(address=sys.argv[1], backend=sys.argv[2], "
            "ppg_enabled=False, acc_enabled=False, gyro_enabled=False, log_level=40)"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._stream_process = subprocess.Popen(
            [sys.executable, "-c", code, self.device.address, self.backend],
            cwd=None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return True

    def stop_stream(self) -> None:
        if self._stream_process and self._stream_process.poll() is None:
            self.status_changed.emit("Stopping Muse stream...")
            self._stream_process.terminate()
            try:
                self._stream_process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self._stream_process.kill()
                self._stream_process.wait(timeout=1.0)
        self._stream_process = None
        self.status_changed.emit("Stream stopped")

    def restart_stream(self) -> bool:
        self.stop_stream()
        time.sleep(1.0)
        return self.start_stream()


class MuseDiscoveryWorker(QtCore.QThread):
    found = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    status_changed = QtCore.pyqtSignal(str)

    def __init__(self, backend: str = "auto", parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.backend = backend

    def run(self) -> None:
        self.status_changed.emit("Searching for Muse 2...")
        try:
            configure_windows_ble()
            from muselsl import list_muses

            muses = list_muses(backend=self.backend)
            devices = [
                MuseDevice(
                    name=str(muse.get("name", "Muse 2")),
                    address=str(muse.get("address", "")),
                )
                for muse in muses
            ]
            if not devices:
                self.failed.emit("No Muse device found")
                return

            self.found.emit(devices)
        except Exception as exc:
            self.failed.emit(f"Discovery failed: {exc}")


class LSLReceiver(QtCore.QThread):
    samples_received = QtCore.pyqtSignal(object, object)
    status_changed = QtCore.pyqtSignal(str)
    sampling_rate_changed = QtCore.pyqtSignal(float)
    stream_lost = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._running = False
        self._inlet: Optional[StreamInlet] = None
        self.sampling_rate = DEFAULT_SAMPLING_RATE

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    def run(self) -> None:
        self._running = True
        while self._running:
            try:
                self.status_changed.emit("Resolving EEG LSL stream...")
                streams = resolve_byprop("type", "EEG", timeout=8)
                if not streams:
                    self.status_changed.emit("Waiting for EEG stream...")
                    time.sleep(1.0)
                    continue

                self._inlet = StreamInlet(streams[0], max_buflen=12)
                info = self._inlet.info()
                nominal_rate = info.nominal_srate()
                if nominal_rate > 0:
                    self.sampling_rate = float(nominal_rate)
                    self.sampling_rate_changed.emit(self.sampling_rate)
                self.status_changed.emit("EEG stream connected")

                last_sample_time = time.monotonic()
                while self._running:
                    chunk, timestamps = self._inlet.pull_chunk(timeout=0.2, max_samples=64)
                    if chunk:
                        last_sample_time = time.monotonic()
                        samples = np.asarray(chunk, dtype=float)[:, :4]
                        self.samples_received.emit(samples, np.asarray(timestamps, dtype=float))
                    elif time.monotonic() - last_sample_time > 5.0:
                        self.status_changed.emit("EEG stream lost")
                        self.stream_lost.emit()
                        break
            except Exception as exc:
                self.status_changed.emit(f"Receiver error: {exc}")
                self.stream_lost.emit()
                time.sleep(1.0)
