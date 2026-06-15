from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
from scipy.signal import welch


BANDS = {
    "Delta": (0.5, 4.0),
    "Theta": (4.0, 8.0),
    "Alpha": (8.0, 12.0),
    "Beta": (12.0, 30.0),
    "Gamma": (30.0, 45.0),
}

_integrate = getattr(np, "trapezoid", None) or getattr(np, "trapz")


@dataclass
class SpectralResult:
    frequencies: np.ndarray
    spectrum: np.ndarray
    band_power: Dict[str, float]


def calculate_spectrum(samples: np.ndarray, sampling_rate: float) -> SpectralResult:
    """Return average FFT spectrum and EEG band powers for a multi-channel buffer."""
    if samples.size == 0 or sampling_rate <= 0:
        return SpectralResult(np.array([]), np.array([]), {name: 0.0 for name in BANDS})

    data = np.asarray(samples, dtype=float)
    if data.ndim == 1:
        data = data.reshape(-1, 1)

    valid = np.all(np.isfinite(data), axis=1)
    data = data[valid]
    if len(data) < max(32, int(sampling_rate)):
        return SpectralResult(np.array([]), np.array([]), {name: 0.0 for name in BANDS})

    # Remove DC offset per channel before spectral analysis.
    data = data - np.mean(data, axis=0, keepdims=True)
    nperseg = min(len(data), int(sampling_rate * 2))
    frequencies, psd = welch(data, fs=sampling_rate, nperseg=nperseg, axis=0)
    mean_psd = np.mean(psd, axis=1)

    band_power = {}
    for name, (low, high) in BANDS.items():
        mask = (frequencies >= low) & (frequencies < high)
        if np.any(mask):
            band_power[name] = float(_integrate(mean_psd[mask], frequencies[mask]))
        else:
            band_power[name] = 0.0

    return SpectralResult(frequencies=frequencies, spectrum=mean_psd, band_power=band_power)


def estimate_signal_quality(channel_samples: np.ndarray) -> int:
    """Heuristic quality score from 0-100 for raw Muse EEG samples."""
    values = np.asarray(channel_samples, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 16:
        return 0

    std = float(np.std(values))
    peak = float(np.max(np.abs(values)))
    if std < 1e-6 or peak > 2_000:
        return 5

    # Typical Muse raw EEG is usually tens to low hundreds of microvolts.
    std_score = 100.0 - min(abs(std - 35.0) * 1.8, 80.0)
    peak_penalty = min(max(peak - 250.0, 0.0) / 10.0, 35.0)
    return int(max(0.0, min(100.0, std_score - peak_penalty)))
