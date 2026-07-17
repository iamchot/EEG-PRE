"""
EEG Signal Processing Service
Implements PRD Section 4 (Process) and Section 10 (Emotion Classification).

Processing pipeline:
  1. Signal Quality Gate   – all 4 sensors must be 'good'
  2. Artifact Rejection    – amplitude + variance thresholds
  3. Epoch Segmentation    – 2s epochs, 50% overlap, no cross-boundary FFT
  4. PSD per Epoch         – Welch method
  5. Feature Extraction    – Log Alpha/Beta per channel (AF7, AF8)
  6. FAA + Arousal         – frontal asymmetry and beta/alpha ratio
  7. Baseline Calibration  – 20s clean resting state
  8. Delta Calculation     – recording vs baseline
  9. Rule-based Emotion    – v1.0 threshold classification
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.signal import welch

# ─── Constants ────────────────────────────────────────────────────────────────

SAMPLING_RATE = 256  # Hz
CHANNELS = ["TP9", "AF7", "AF8", "TP10"]
CH_IDX = {ch: i for i, ch in enumerate(CHANNELS)}

EPOCH_SECONDS = 2.0
EPOCH_OVERLAP = 0.5
EPOCH_SAMPLES = int(EPOCH_SECONDS * SAMPLING_RATE)
EPOCH_STEP = int(EPOCH_SAMPLES * (1 - EPOCH_OVERLAP))

ALPHA_LOW, ALPHA_HIGH = 8.0, 13.0
BETA_LOW, BETA_HIGH = 13.0, 30.0

# Artifact rejection thresholds
ARTIFACT_AMPLITUDE_UV = 150.0    # |x| > 150 µV → artifact
ARTIFACT_FLATLINE_STD = 0.5      # std < 0.5 µV → flatline
STALE_TIMEOUT_SECONDS = 2.0      # no new data → stale

# Emotion rule thresholds (version v1.0)
EMOTION_THRESHOLDS_V1 = {
    "version": "v1.0",
    "delta_faa_threshold": 0.0,
    "delta_arousal_threshold": 0.0,
}
# Rule: delta_faa > 0 → positive valence; delta_arousal > 0 → high arousal
# Happy:   +valence, +arousal
# Excited: -valence, +arousal
# Sad:     +valence, -arousal
# Stressed:-valence, -arousal


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class SensorQuality:
    state: str = "unknown"    # unknown | poor | good | stale
    quality_score: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)
    sequence: int = 0


@dataclass
class EpochFeatures:
    log_alpha_af7: float
    log_alpha_af8: float
    log_beta_af7: float
    log_beta_af8: float
    faa: float          # logAlpha(AF8) - logAlpha(AF7)
    arousal: float      # log(beta_total / alpha_total)
    quality_score: float


@dataclass
class BaselineFeatures:
    log_alpha_af7: float
    log_alpha_af8: float
    log_beta_af7: float
    log_beta_af8: float
    faa: float
    arousal: float
    epoch_count: int


@dataclass
class RecordingFeatures:
    faa: float
    arousal: float
    delta_faa: float
    delta_arousal: float
    accepted_epochs: int
    rejected_epochs: int
    quality_score_avg: float


@dataclass
class EmotionClassification:
    emotion: str           # happy | sad | stressed | excited
    rule_version: str
    threshold_version: str
    valence: float
    arousal_value: float
    delta_faa: float
    delta_arousal: float


# ─── Core Functions ───────────────────────────────────────────────────────────

def _integrate(psd: np.ndarray, freqs: np.ndarray) -> float:
    """Integrate PSD over frequency band using trapezoid rule."""
    fn = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    return float(fn(psd, freqs))


def _band_power(freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    if not np.any(mask):
        return 0.0
    return _integrate(psd[mask], freqs[mask])


def compute_epoch_psd(epoch: np.ndarray, fs: float = SAMPLING_RATE) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute per-channel PSD for a single 2s epoch using Welch method.
    Returns (frequencies, psd) where psd.shape = (n_freqs, n_channels).
    """
    nperseg = min(len(epoch), int(fs))
    freqs, psd = welch(epoch, fs=fs, nperseg=nperseg, axis=0)
    return freqs, psd


def is_artifact(epoch: np.ndarray) -> bool:
    """Return True if epoch contains artifacts (blink, muscle, flatline)."""
    if np.any(np.abs(epoch) > ARTIFACT_AMPLITUDE_UV):
        return True
    if np.any(np.std(epoch, axis=0) < ARTIFACT_FLATLINE_STD):
        return True
    if np.any(~np.isfinite(epoch)):
        return True
    return False


def extract_epoch_features(epoch: np.ndarray) -> Optional[EpochFeatures]:
    """
    Extract FAA and Arousal features from a clean 2s epoch.
    epoch.shape must be (EPOCH_SAMPLES, 4) with channels [TP9, AF7, AF8, TP10].
    Returns None if epoch fails artifact rejection.
    """
    if is_artifact(epoch):
        return None

    # Remove DC offset
    epoch = epoch - np.mean(epoch, axis=0, keepdims=True)

    freqs, psd = compute_epoch_psd(epoch)

    af7_idx = CH_IDX["AF7"]
    af8_idx = CH_IDX["AF8"]

    alpha_af7 = _band_power(freqs, psd[:, af7_idx], ALPHA_LOW, ALPHA_HIGH)
    alpha_af8 = _band_power(freqs, psd[:, af8_idx], ALPHA_LOW, ALPHA_HIGH)
    beta_af7 = _band_power(freqs, psd[:, af7_idx], BETA_LOW, BETA_HIGH)
    beta_af8 = _band_power(freqs, psd[:, af8_idx], BETA_LOW, BETA_HIGH)

    # Safe log (add small epsilon to avoid log(0))
    eps = 1e-10
    log_a_af7 = math.log(alpha_af7 + eps)
    log_a_af8 = math.log(alpha_af8 + eps)
    log_b_af7 = math.log(beta_af7 + eps)
    log_b_af8 = math.log(beta_af8 + eps)

    faa = log_a_af8 - log_a_af7
    alpha_total = alpha_af7 + alpha_af8
    beta_total = beta_af7 + beta_af8
    arousal = math.log((beta_total + eps) / (alpha_total + eps))

    quality_score = _compute_quality(epoch)

    return EpochFeatures(
        log_alpha_af7=log_a_af7,
        log_alpha_af8=log_a_af8,
        log_beta_af7=log_b_af7,
        log_beta_af8=log_b_af8,
        faa=faa,
        arousal=arousal,
        quality_score=quality_score,
    )


def _compute_quality(epoch: np.ndarray) -> float:
    """Compute epoch-level quality score 0-100 based on amplitude."""
    std_vals = np.std(epoch, axis=0)
    peak_vals = np.max(np.abs(epoch), axis=0)
    scores = []
    for std, peak in zip(std_vals, peak_vals):
        if std < 1e-6 or peak > ARTIFACT_AMPLITUDE_UV:
            scores.append(0.0)
            continue
        score = 100.0 - min(abs(std - 35.0) * 1.8, 80.0)
        penalty = min(max(peak - 100.0, 0.0) / 5.0, 35.0)
        scores.append(max(0.0, min(100.0, score - penalty)))
    return float(np.mean(scores))


def segment_epochs(buffer: np.ndarray) -> list[np.ndarray]:
    """
    Segment contiguous EEG buffer into overlapping 2s epochs.
    buffer.shape = (N_samples, 4_channels).
    """
    epochs = []
    start = 0
    while start + EPOCH_SAMPLES <= len(buffer):
        epochs.append(buffer[start : start + EPOCH_SAMPLES])
        start += EPOCH_STEP
    return epochs


def compute_baseline(clean_buffer: np.ndarray) -> BaselineFeatures:
    """
    Compute baseline features from 20s clean resting-state buffer.
    Segments into epochs, extracts features, averages accepted epochs.
    """
    epochs = segment_epochs(clean_buffer)
    accepted: list[EpochFeatures] = []

    for epoch in epochs:
        feat = extract_epoch_features(epoch)
        if feat is not None:
            accepted.append(feat)

    if not accepted:
        raise ValueError("No clean epochs in baseline buffer")

    avg = lambda attr: float(np.mean([getattr(f, attr) for f in accepted]))

    return BaselineFeatures(
        log_alpha_af7=avg("log_alpha_af7"),
        log_alpha_af8=avg("log_alpha_af8"),
        log_beta_af7=avg("log_beta_af7"),
        log_beta_af8=avg("log_beta_af8"),
        faa=avg("faa"),
        arousal=avg("arousal"),
        epoch_count=len(accepted),
    )


def compute_recording_features(
    clean_segments: list[np.ndarray],
    baseline: BaselineFeatures,
) -> RecordingFeatures:
    """
    Compute recording features from list of clean (non-pause-spanning) segments.
    Each segment is segmented into epochs independently (no cross-boundary FFT).
    """
    accepted: list[EpochFeatures] = []
    rejected_count = 0

    for segment in clean_segments:
        epochs = segment_epochs(segment)
        for epoch in epochs:
            feat = extract_epoch_features(epoch)
            if feat is not None:
                accepted.append(feat)
            else:
                rejected_count += 1

    if not accepted:
        raise ValueError("No clean epochs in recording")

    avg = lambda attr: float(np.mean([getattr(f, attr) for f in accepted]))

    rec_faa = avg("faa")
    rec_arousal = avg("arousal")
    quality_avg = avg("quality_score")

    return RecordingFeatures(
        faa=rec_faa,
        arousal=rec_arousal,
        delta_faa=rec_faa - baseline.faa,
        delta_arousal=rec_arousal - baseline.arousal,
        accepted_epochs=len(accepted),
        rejected_epochs=rejected_count,
        quality_score_avg=quality_avg,
    )


def classify_emotion(recording: RecordingFeatures) -> EmotionClassification:
    """
    Rule-based emotion classification (v1.0).
    Uses delta_faa and delta_arousal relative to baseline.

    Valence (FAA): delta_faa > 0 → positive; ≤ 0 → negative
    Arousal:       delta_arousal > 0 → high; ≤ 0 → low

    Quadrant → Emotion:
      +valence, +arousal  → Happy
      -valence, +arousal  → Excited
      +valence, -arousal  → Sad
      -valence, -arousal  → Stressed
    """
    thresh = EMOTION_THRESHOLDS_V1
    positive_valence = recording.delta_faa > thresh["delta_faa_threshold"]
    high_arousal = recording.delta_arousal > thresh["delta_arousal_threshold"]

    if positive_valence and high_arousal:
        emotion = "happy"
    elif not positive_valence and high_arousal:
        emotion = "excited"
    elif positive_valence and not high_arousal:
        emotion = "sad"
    else:
        emotion = "stressed"

    return EmotionClassification(
        emotion=emotion,
        rule_version=thresh["version"],
        threshold_version=thresh["version"],
        valence=recording.delta_faa,
        arousal_value=recording.delta_arousal,
        delta_faa=recording.delta_faa,
        delta_arousal=recording.delta_arousal,
    )


def estimate_sensor_state(
    samples: np.ndarray,
    channel_idx: int,
    last_timestamp: float,
    now: float,
) -> SensorQuality:
    """
    Determine per-sensor state: unknown | poor | good | stale.
    """
    if now - last_timestamp > STALE_TIMEOUT_SECONDS:
        return SensorQuality(state="stale", quality_score=0.0, timestamp=now)

    ch_data = samples[:, channel_idx] if samples.ndim > 1 else samples
    ch_data = ch_data[np.isfinite(ch_data)]

    if len(ch_data) < 16:
        return SensorQuality(state="unknown", quality_score=0.0, timestamp=now)

    std = float(np.std(ch_data))
    peak = float(np.max(np.abs(ch_data)))

    if std < ARTIFACT_FLATLINE_STD or peak > ARTIFACT_AMPLITUDE_UV:
        quality = 10.0
        return SensorQuality(state="poor", quality_score=quality, timestamp=now)

    score = 100.0 - min(abs(std - 35.0) * 1.8, 80.0)
    penalty = min(max(peak - 100.0, 0.0) / 5.0, 35.0)
    quality = max(0.0, min(100.0, score - penalty))

    state = "good" if quality >= 60.0 else "poor"
    return SensorQuality(state=state, quality_score=quality, timestamp=now)
