from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

try:
    import cv2
except ImportError:
    cv2 = None

from eeg_plot import EEGPlotWidget
from muse_connector import (
    DEFAULT_SAMPLING_RATE,
    LSLReceiver,
    MUSE_CHANNELS,
    MuseConnector,
    MuseDevice,
    MuseDiscoveryWorker,
    configure_windows_ble,
)
from recorder import EEGRecorder
from signal_processing import BANDS, calculate_spectrum, estimate_signal_quality


class MuseDashboard(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Muse 2 Real-time EEG Dashboard")
        self.resize(1360, 860)

        self.connector = MuseConnector()
        self.receiver: LSLReceiver | None = None
        self.discovery_worker: MuseDiscoveryWorker | None = None
        self.stream_worker: StreamStartWorker | None = None
        self.discovered_devices: list[MuseDevice] = []
        self.recorder = EEGRecorder(MUSE_CHANNELS)
        self.sampling_rate = DEFAULT_SAMPLING_RATE
        self.recording_started_at: float | None = None
        self.latest_values = np.zeros(len(MUSE_CHANNELS))
        self.camera_capture = None
        self.camera_retry_count = 0
        self.camera_max_retries = 12

        self._build_ui()
        self._wire_signals()

        self.plot_timer = QtCore.QTimer(self)
        self.plot_timer.setInterval(66)
        self.plot_timer.timeout.connect(self._refresh_plots)
        self.plot_timer.start()

        self.analysis_timer = QtCore.QTimer(self)
        self.analysis_timer.setInterval(1000)
        self.analysis_timer.timeout.connect(self._update_analysis)
        self.analysis_timer.start()

        self.camera_timer = QtCore.QTimer(self)
        self.camera_timer.setInterval(50)
        self.camera_timer.timeout.connect(self._update_camera_frame)
        QtCore.QTimer.singleShot(500, self._start_camera)

    def _build_ui(self) -> None:
        pg.setConfigOptions(antialias=False)
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        main_layout = QtWidgets.QVBoxLayout(root)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        top = QtWidgets.QFrame()
        top.setObjectName("topBar")
        top_layout = QtWidgets.QHBoxLayout(top)
        self.status_label = QtWidgets.QLabel("Status: Idle")
        self.device_label = QtWidgets.QLabel("Device: -")
        self.rate_label = QtWidgets.QLabel(f"Sampling Rate: {self.sampling_rate:.0f} Hz")
        self.duration_label = QtWidgets.QLabel("Recording Time: 00:00:00")
        for widget in (self.status_label, self.device_label, self.rate_label, self.duration_label):
            top_layout.addWidget(widget)
        top_layout.addStretch(1)
        main_layout.addWidget(top)

        controls = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton("Scan Devices")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumWidth(260)
        self.device_combo.addItem("No Muse scanned", None)
        self.connect_btn = QtWidgets.QPushButton("Connect Selected")
        self.disconnect_btn = QtWidgets.QPushButton("Disconnect")
        self.start_btn = QtWidgets.QPushButton("Start Stream")
        self.stop_btn = QtWidgets.QPushButton("Stop Stream")
        self.start_record_btn = QtWidgets.QPushButton("Start Recording")
        self.stop_record_btn = QtWidgets.QPushButton("Stop Recording")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(False)
        controls.addWidget(self.scan_btn)
        controls.addWidget(self.device_combo)
        for button in (
            self.connect_btn,
            self.disconnect_btn,
            self.start_btn,
            self.stop_btn,
            self.start_record_btn,
            self.stop_record_btn,
        ):
            button.setMinimumHeight(36)
            controls.addWidget(button)
        controls.addStretch(1)
        main_layout.addLayout(controls)

        content = QtWidgets.QHBoxLayout()
        self.eeg_plot = EEGPlotWidget(MUSE_CHANNELS, seconds=8, sampling_rate=self.sampling_rate)
        content.addWidget(self.eeg_plot, stretch=5)

        side = QtWidgets.QFrame()
        side.setObjectName("sidePanel")
        side_layout = QtWidgets.QVBoxLayout(side)
        side_layout.addWidget(QtWidgets.QLabel("Webcam"))
        self.camera_label = QtWidgets.QLabel("Starting webcam...")
        self.camera_label.setObjectName("cameraPreview")
        self.camera_label.setAlignment(QtCore.Qt.AlignCenter)
        self.camera_label.setMinimumSize(240, 150)
        self.camera_label.setMaximumHeight(170)
        self.camera_label.setScaledContents(False)
        side_layout.addWidget(self.camera_label)
        side_layout.addSpacing(12)

        side_layout.addWidget(QtWidgets.QLabel("Current EEG"))
        self.channel_labels: Dict[str, QtWidgets.QLabel] = {}
        self.quality_bars: Dict[str, QtWidgets.QProgressBar] = {}
        for channel in MUSE_CHANNELS:
            label = QtWidgets.QLabel(f"{channel}: 0.00 uV")
            bar = QtWidgets.QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat(f"{channel} quality: %p%")
            self.channel_labels[channel] = label
            self.quality_bars[channel] = bar
            side_layout.addWidget(label)
            side_layout.addWidget(bar)

        side_layout.addSpacing(12)
        side_layout.addWidget(QtWidgets.QLabel("Band Power"))
        self.band_labels: Dict[str, QtWidgets.QLabel] = {}
        for name in BANDS:
            label = QtWidgets.QLabel(f"{name}: 0.000")
            self.band_labels[name] = label
            side_layout.addWidget(label)
        side_layout.addStretch(1)
        content.addWidget(side, stretch=2)
        main_layout.addLayout(content, stretch=6)

        self.fft_plot = pg.PlotWidget()
        self.fft_plot.setBackground("#101418")
        self.fft_plot.showGrid(x=True, y=True, alpha=0.22)
        self.fft_plot.setLabel("left", "Power")
        self.fft_plot.setLabel("bottom", "Frequency", units="Hz")
        self.fft_plot.setXRange(0, 50)
        self.fft_curve = self.fft_plot.plot(pen=pg.mkPen("#5dd9c1", width=1.8))
        main_layout.addWidget(self.fft_plot, stretch=2)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0c1014; color: #eef3f7; font-size: 13px; }
            QFrame#topBar, QFrame#sidePanel { background: #151b22; border: 1px solid #28313b; border-radius: 6px; }
            QLabel { color: #eef3f7; }
            QLabel#cameraPreview { background: #090c10; border: 1px solid #3d4d61; border-radius: 6px; color: #8f9aaa; }
            QPushButton { background: #263241; color: #f6f8fb; border: 1px solid #3d4d61; border-radius: 5px; padding: 7px 12px; }
            QPushButton:hover { background: #314055; }
            QPushButton:disabled { color: #7b8794; background: #1b222b; }
            QProgressBar { background: #202832; border: 1px solid #3d4d61; border-radius: 4px; text-align: center; height: 18px; }
            QProgressBar::chunk { background: #5dd9c1; border-radius: 3px; }
            """
        )

    def _wire_signals(self) -> None:
        self.scan_btn.clicked.connect(self.scan_devices)
        self.connect_btn.clicked.connect(self.connect_selected_device)
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.start_btn.clicked.connect(self.start_stream)
        self.stop_btn.clicked.connect(self.stop_stream)
        self.start_record_btn.clicked.connect(self.start_recording)
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.connector.status_changed.connect(self._set_status)
        self.connector.device_changed.connect(lambda text: self.device_label.setText(f"Device: {text}"))

    def scan_devices(self) -> None:
        if self.discovery_worker and self.discovery_worker.isRunning():
            return

        self.scan_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.device_combo.clear()
        self.device_combo.addItem("Scanning...", None)
        self.discovered_devices = []
        self.connector.device = None
        self.device_label.setText("Device: -")
        self.start_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.discovery_worker = MuseDiscoveryWorker(self.connector.backend, self)
        self.discovery_worker.status_changed.connect(self._set_status)
        self.discovery_worker.found.connect(self._on_devices_found)
        self.discovery_worker.failed.connect(self._on_discovery_failed)
        self.discovery_worker.finished.connect(lambda: self.scan_btn.setEnabled(True))
        self.discovery_worker.start()

    def _on_devices_found(self, devices: list[MuseDevice]) -> None:
        self.discovered_devices = devices
        self.device_combo.clear()
        for index, device in enumerate(devices):
            self.device_combo.addItem(f"{device.name} ({device.address})", index)
        self.connect_btn.setEnabled(True)
        self._set_status(f"Found {len(devices)} Muse device(s). Select one, then connect.")

    def connect_selected_device(self) -> None:
        selected_index = self.device_combo.currentData()
        if selected_index is None or selected_index >= len(self.discovered_devices):
            QtWidgets.QMessageBox.information(self, "Select Muse", "Scan and select a Muse device first.")
            return

        device = self.discovered_devices[int(selected_index)]
        self.connector.device = device
        self.device_label.setText(f"Device: {device.name} ({device.address})")
        self.start_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(True)
        self._set_status(f"Selected {device.name}. Ready to start stream.")

    def _on_discovery_failed(self, message: str) -> None:
        self._set_status(message)
        self.device_combo.clear()
        self.device_combo.addItem("No Muse found", None)
        self.scan_btn.setEnabled(True)
        self.connect_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        QtWidgets.QMessageBox.warning(
            self,
            "Muse not found",
            "Could not find Muse 2. Check Bluetooth, make sure no other app is connected, then try again.",
        )

    def start_stream(self) -> None:
        if self.connector.device is None:
            QtWidgets.QMessageBox.information(
                self,
                "Connect first",
                "Press Scan Devices, choose a Muse, then press Connect Selected first.",
            )
            return

        if self.stream_worker and self.stream_worker.isRunning():
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._set_status("Starting stream...")
        self.stream_worker = StreamStartWorker(self.connector, self)
        self.stream_worker.succeeded.connect(self._on_stream_started)
        self.stream_worker.failed.connect(self._on_stream_failed)
        self.stream_worker.start()

    def _on_stream_started(self) -> None:
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._start_receiver()

    def _on_stream_failed(self, message: str) -> None:
        self._set_status(message)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QtWidgets.QMessageBox.warning(self, "Stream failed", message)

    def stop_stream(self) -> None:
        if self.receiver:
            self.receiver.stop()
            self.receiver = None
        self.connector.stop_stream()
        self.start_btn.setEnabled(self.connector.device is not None)
        self.stop_btn.setEnabled(False)

    def disconnect_device(self) -> None:
        if self.recorder.is_recording:
            self.stop_recording()
        self.stop_stream()
        self.connector.device = None
        self.discovered_devices = []
        self.device_combo.clear()
        self.device_combo.addItem("No Muse connected", None)
        self.device_label.setText("Device: -")
        self.latest_values = np.zeros(len(MUSE_CHANNELS))
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._set_status("Disconnected")

    def _start_receiver(self) -> None:
        if self.receiver:
            self.receiver.stop()
        self.receiver = LSLReceiver(self)
        self.receiver.samples_received.connect(self._on_samples)
        self.receiver.status_changed.connect(self._set_status)
        self.receiver.sampling_rate_changed.connect(self._set_sampling_rate)
        self.receiver.stream_lost.connect(self._handle_stream_lost)
        self.receiver.start()

    def _handle_stream_lost(self) -> None:
        self._set_status("Reconnecting Muse stream...")
        self.connector.stop_stream()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        QtCore.QTimer.singleShot(1200, self.start_stream)

    def _on_samples(self, samples: object, timestamps: object) -> None:
        sample_array = np.asarray(samples, dtype=float)
        timestamp_array = np.asarray(timestamps, dtype=float)
        self.eeg_plot.append_samples(sample_array)
        if sample_array.size:
            self.latest_values = sample_array[-1]
        if self.recorder.is_recording:
            self.recorder.write_samples(timestamp_array, sample_array)

    def _set_sampling_rate(self, sampling_rate: float) -> None:
        self.sampling_rate = sampling_rate
        self.rate_label.setText(f"Sampling Rate: {sampling_rate:.0f} Hz")
        self.eeg_plot.set_sampling_rate(sampling_rate)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(f"Status: {text}")

    def _start_camera(self) -> None:
        if cv2 is None:
            self.camera_label.setText("Install opencv-python")
            return

        self._release_camera()
        self.camera_label.setText("Opening webcam...")

        backends = []
        if sys.platform == "darwin" and hasattr(cv2, "CAP_AVFOUNDATION"):
            backends.append(cv2.CAP_AVFOUNDATION)
        backends.append(cv2.CAP_ANY)

        for backend in backends:
            capture = cv2.VideoCapture(0, backend)
            if capture.isOpened():
                self.camera_capture = capture
                break
            capture.release()

        if self.camera_capture is None:
            self._retry_camera("Webcam unavailable")
            return

        self.camera_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self.camera_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 200)
        self.camera_capture.set(cv2.CAP_PROP_FPS, 20)
        self.camera_timer.start()

    def _update_camera_frame(self) -> None:
        if cv2 is None or self.camera_capture is None:
            return

        ok, frame = self.camera_capture.read()
        if not ok:
            self.camera_timer.stop()
            self._release_camera()
            self._retry_camera("Waiting for webcam permission...")
            return

        self.camera_retry_count = 0
        frame = cv2.flip(frame, 1)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        image = QtGui.QImage(frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).copy()
        pixmap = QtGui.QPixmap.fromImage(image)
        self.camera_label.setPixmap(
            pixmap.scaled(
                self.camera_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def _retry_camera(self, message: str) -> None:
        self.camera_retry_count += 1
        if self.camera_retry_count > self.camera_max_retries:
            self.camera_label.setText("Enable Camera permission")
            return

        self.camera_label.setText(message)
        QtCore.QTimer.singleShot(1000, self._start_camera)

    def _release_camera(self) -> None:
        if self.camera_capture is not None:
            self.camera_capture.release()
            self.camera_capture = None

    def start_recording(self) -> None:
        path = self.recorder.start()
        self.recording_started_at = time.monotonic()
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self._set_status(f"Recording to {path}")

    def stop_recording(self) -> None:
        path = self.recorder.stop()
        self.recording_started_at = None
        self.duration_label.setText("Recording Time: 00:00:00")
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        if path:
            self._set_status(f"Saved {Path(path)}")

    def _refresh_plots(self) -> None:
        self.eeg_plot.refresh()
        for channel, value in zip(MUSE_CHANNELS, self.latest_values):
            self.channel_labels[channel].setText(f"{channel}: {value:8.2f} uV")
        if self.recording_started_at is not None:
            elapsed = int(time.monotonic() - self.recording_started_at)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.duration_label.setText(f"Recording Time: {h:02d}:{m:02d}:{s:02d}")

    def _update_analysis(self) -> None:
        data = self.eeg_plot.get_recent_samples()
        if data.size == 0:
            return

        recent = data[-min(len(data), int(self.sampling_rate * 2)) :]
        for index, channel in enumerate(MUSE_CHANNELS):
            self.quality_bars[channel].setValue(estimate_signal_quality(recent[:, index]))

        spectral = calculate_spectrum(data[-min(len(data), int(self.sampling_rate * 4)) :], self.sampling_rate)
        if spectral.frequencies.size:
            mask = spectral.frequencies <= 50
            self.fft_curve.setData(spectral.frequencies[mask], spectral.spectrum[mask])
        for name, value in spectral.band_power.items():
            self.band_labels[name].setText(f"{name}: {value:.3f}")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.camera_timer.stop()
        self._release_camera()
        self.stop_recording()
        self.stop_stream()
        event.accept()


def main() -> None:
    mp_support()
    configure_windows_ble()
    app = QtWidgets.QApplication(sys.argv)
    window = MuseDashboard()
    window.show()
    sys.exit(app.exec_())


def mp_support() -> None:
    import multiprocessing as mp

    mp.freeze_support()


class StreamStartWorker(QtCore.QThread):
    succeeded = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self, connector: MuseConnector, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.connector = connector

    def run(self) -> None:
        try:
            if self.connector.start_stream():
                self.succeeded.emit()
            else:
                self.failed.emit("Could not start Muse LSL stream.")
        except Exception as exc:
            self.failed.emit(f"Could not start Muse LSL stream: {exc}")


if __name__ == "__main__":
    main()
