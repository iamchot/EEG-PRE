from __future__ import annotations

from typing import Dict, Iterable

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets


class EEGPlotWidget(QtWidgets.QWidget):
    def __init__(self, channels: Iterable[str], seconds: int = 8, sampling_rate: float = 256.0) -> None:
        super().__init__()
        self.channels = list(channels)
        self.seconds = seconds
        self.sampling_rate = sampling_rate
        self.max_samples = int(self.seconds * self.sampling_rate)
        self.buffer = np.zeros((self.max_samples, len(self.channels)), dtype=float)
        self.write_index = 0
        self.total_samples = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#101418")
        self.plot.showGrid(x=True, y=True, alpha=0.22)
        self.plot.setLabel("left", "EEG", units="uV")
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.addLegend(offset=(10, 10))
        layout.addWidget(self.plot)

        colors = ["#5dd9c1", "#ffcf5a", "#ff6b8a", "#7aa2ff"]
        self.curves: Dict[str, pg.PlotDataItem] = {}
        self.offsets = np.arange(len(self.channels))[::-1] * 180.0
        for index, channel in enumerate(self.channels):
            curve = self.plot.plot(
                pen=pg.mkPen(colors[index % len(colors)], width=1.6),
                name=channel,
            )
            self.curves[channel] = curve
        self.plot.setYRange(-120, self.offsets[0] + 120)

    def set_sampling_rate(self, sampling_rate: float) -> None:
        if sampling_rate <= 0 or abs(sampling_rate - self.sampling_rate) < 0.1:
            return

        old_data = self.get_recent_samples()
        self.sampling_rate = sampling_rate
        self.max_samples = int(self.seconds * self.sampling_rate)
        self.buffer = np.zeros((self.max_samples, len(self.channels)), dtype=float)
        keep = min(len(old_data), self.max_samples)
        if keep:
            self.buffer[:keep] = old_data[-keep:]
            self.write_index = keep % self.max_samples
            self.total_samples = keep

    def append_samples(self, samples: np.ndarray) -> None:
        if samples.size == 0:
            return

        data = np.asarray(samples, dtype=float)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        data = data[:, : len(self.channels)]
        sample_count = len(data)

        if sample_count >= self.max_samples:
            self.buffer[:] = data[-self.max_samples :]
            self.write_index = 0
            self.total_samples += sample_count
            return

        end_index = self.write_index + sample_count
        if end_index <= self.max_samples:
            self.buffer[self.write_index : end_index] = data
        else:
            first_part = self.max_samples - self.write_index
            self.buffer[self.write_index :] = data[:first_part]
            self.buffer[: end_index % self.max_samples] = data[first_part:]

        self.write_index = end_index % self.max_samples
        self.total_samples += sample_count

    def get_recent_samples(self) -> np.ndarray:
        count = min(self.total_samples, self.max_samples)
        if count == 0:
            return np.empty((0, len(self.channels)))
        if self.total_samples < self.max_samples:
            return self.buffer[:count].copy()
        return np.vstack((self.buffer[self.write_index :], self.buffer[: self.write_index]))

    def refresh(self) -> None:
        data = self.get_recent_samples()
        if data.size == 0:
            return

        max_points = 1200
        if len(data) > max_points:
            step = max(1, int(np.ceil(len(data) / max_points)))
            data = data[::step]

        x = np.linspace(-len(data) / self.sampling_rate, 0, len(data))
        for index, channel in enumerate(self.channels):
            self.curves[channel].setData(x, data[:, index] + self.offsets[index])
