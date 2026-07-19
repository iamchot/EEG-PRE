from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.raw_eeg_writer import AtomicEEGWriter, EEGSample


HEADER = (
    "timestamp,tp9,af7,af8,tp10,tp9_quality,af7_quality,af8_quality,"
    "tp10_quality,marker\n"
)


def sample(timestamp: float) -> EEGSample:
    return EEGSample(timestamp, 1.0, 2.0, 3.0, 4.0, 0.1, 0.2, 0.3, 0.4, "")


def test_writer_uses_exact_stable_csv_contract_and_returns_file_metadata(tmp_path: Path):
    writer = AtomicEEGWriter(tmp_path, clock=lambda: 12.5)
    writer.start(["P001", "session-7", "trial-3"])

    assert list(tmp_path.rglob("*.partial"))
    assert not list(tmp_path.rglob("*.csv"))

    writer.append(sample(10.25))
    writer.mark("stimulus_start")
    result = writer.finalize()

    final_path = tmp_path / Path(result.relative_path)
    expected = (
        HEADER
        + "10.25,1.0,2.0,3.0,4.0,0.1,0.2,0.3,0.4,\n"
        + "12.5,,,,,,,,,stimulus_start\n"
    ).encode("utf-8")
    assert final_path.read_bytes() == expected
    assert result.relative_path == str(Path("P001") / "session-7" / "trial-3.csv")
    assert result.sha256 == hashlib.sha256(expected).hexdigest()
    assert result.byte_size == len(expected)
    assert result.row_count == 2
    assert result.first_timestamp == 10.25
    assert result.last_timestamp == 12.5
    assert not list(tmp_path.rglob("*.partial"))


def test_append_and_backend_marker_timestamps_must_be_strictly_monotonic(tmp_path: Path):
    marker_times = iter([2.0, 3.0])
    writer = AtomicEEGWriter(tmp_path, clock=lambda: next(marker_times))
    writer.start(["P001", "session-1", "trial-1"])
    writer.append(sample(1.0))
    writer.mark("rest_end")

    with pytest.raises(ValueError, match="strictly monotonic"):
        writer.append(sample(1.5))

    writer.mark("stimulus_start")
    assert writer.finalize().last_timestamp == 3.0


def test_marker_rejects_unusable_text(tmp_path: Path):
    writer = AtomicEEGWriter(tmp_path, clock=lambda: 1.0)
    writer.start(["P001", "session-1", "trial-1"])

    for marker in ("", " ", "bad\nmarker", "bad\rmarker"):
        with pytest.raises(ValueError, match="marker"):
            writer.mark(marker)


def test_abort_removes_partial_and_prevents_more_writes(tmp_path: Path):
    writer = AtomicEEGWriter(tmp_path)
    writer.start(["P001", "session-1", "trial-1"])
    writer.append(sample(1.0))
    writer.abort()

    assert not list(tmp_path.rglob("*.partial"))
    assert not list(tmp_path.rglob("*.csv"))
    with pytest.raises(RuntimeError, match="aborted"):
        writer.append(sample(2.0))


def test_finalize_is_single_use_and_never_overwrites_existing_capture(tmp_path: Path):
    writer = AtomicEEGWriter(tmp_path)
    writer.start(["P001", "session-1", "trial-1"])
    writer.append(sample(1.0))
    writer.finalize()

    with pytest.raises(RuntimeError, match="finalized"):
        writer.finalize()

    duplicate = AtomicEEGWriter(tmp_path)
    with pytest.raises(FileExistsError):
        duplicate.start(["P001", "session-1", "trial-1"])


@pytest.mark.parametrize(
    "parts",
    [
        ["P001", "..", "trial-1"],
        ["P001", ".", "trial-1"],
        ["P001", "folder/trial", "trial-1"],
        ["P001", r"folder\\trial", "trial-1"],
        ["P001", "C:\\escape", "trial-1"],
        ["P001", "/absolute", "trial-1"],
        ["P001", "session-1", "../escape"],
        ["John", "session-1", "trial-1"],
        ["John Smith", "session-1", "trial-1"],
        ["john@example.com", "session-1", "trial-1"],
        ["P001", "session-1", "trial-1.csv"],
        ["P001", "session-1", ""],
    ],
)
def test_start_rejects_unsafe_or_identity_bearing_path_parts(tmp_path: Path, parts: list[str]):
    writer = AtomicEEGWriter(tmp_path)

    with pytest.raises(ValueError, match="path"):
        writer.start(parts)

    assert not list(tmp_path.rglob("*.partial"))


def test_symlink_escape_is_rejected_when_supported(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    participant_link = tmp_path / "P001"
    try:
        participant_link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not available")

    writer = AtomicEEGWriter(tmp_path)
    with pytest.raises(ValueError, match="outside collection_raw_dir"):
        writer.start(["P001", "session-1", "trial-1"])
