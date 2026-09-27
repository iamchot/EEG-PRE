from __future__ import annotations

import hashlib
from pathlib import Path
import struct


def get_mp4_duration(file_path: Path) -> float:
    """Reads the exact duration in seconds from the MP4 mvhd atom in pure Python."""
    try:
        with open(file_path, "rb") as f:
            while True:
                header = f.read(8)
                if len(header) < 8:
                    break
                size, name = struct.unpack(">I4s", header)
                name = name.decode("latin1", errors="ignore")
                if name == "moov":
                    moov_bytes = f.read(size - 8) if size > 8 else f.read()
                    pos = moov_bytes.find(b"mvhd")
                    if pos != -1:
                        mvhd_data = moov_bytes[pos + 4 :]
                        version = mvhd_data[0]
                        if version == 0:
                            timescale, duration = struct.unpack(">II", mvhd_data[12:20])
                        else:
                            timescale, duration = struct.unpack(">IQ", mvhd_data[20:32])
                        if timescale > 0:
                            return round(duration / timescale, 2)
                    break
                elif size == 1:
                    size = struct.unpack(">Q", f.read(8))[0]
                    f.seek(size - 16, 1)
                elif size > 8:
                    f.seek(size - 8, 1)
                else:
                    break
    except Exception:
        pass
    return 0.0


def get_file_sha256(file_path: Path) -> str:
    """Computes the SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def infer_suggested_quadrant(rel_path_str: str) -> str | None:
    """Infers target quadrant based on folder or filename convention."""
    lower = rel_path_str.lower()
    if "relax" in lower or "calm" in lower:
        return "positive_low"
    if "excit" in lower or "happy" in lower or "joy" in lower:
        return "positive_high"
    if "sad" in lower or "depress" in lower:
        return "negative_low"
    if "stress" in lower or "fear" in lower or "anger" in lower:
        return "negative_high"
    return None


def resolve_stimulus_path(rel_path: str, stimulus_root: Path) -> Path:
    """Safely resolves relative path within the stimulus root directory, preventing directory traversal."""
    cleaned = rel_path.strip().replace("\\", "/").lstrip("/")
    target = (stimulus_root / cleaned).resolve()
    stimulus_root_resolved = stimulus_root.resolve()
    if not str(target).startswith(str(stimulus_root_resolved)):
        raise ValueError("Invalid path: traversal outside stimulus directory is not permitted")
    return target


def inspect_stimulus_file(rel_path: str, stimulus_root: Path) -> dict:
    """Inspects a stimulus file and returns checksum, duration, file size, and validation status."""
    target_path = resolve_stimulus_path(rel_path, stimulus_root)
    if not target_path.is_file():
        raise FileNotFoundError(f"Stimulus file not found: {rel_path}")

    checksum = get_file_sha256(target_path)
    duration = get_mp4_duration(target_path)
    file_size = target_path.stat().st_size
    rel_normalized = str(target_path.relative_to(stimulus_root.resolve())).replace("\\", "/")
    suggested_quadrant = infer_suggested_quadrant(rel_normalized)
    is_valid_duration = 45.0 <= duration <= 60.0

    return {
        "file_path": rel_normalized,
        "checksum": checksum,
        "duration_seconds": duration,
        "file_size_bytes": file_size,
        "suggested_quadrant": suggested_quadrant,
        "is_valid_duration": is_valid_duration,
    }


def list_available_stimuli_files(stimulus_root: Path) -> list[str]:
    """Lists all video files in the stimulus root directory relative to it."""
    stimulus_root_resolved = stimulus_root.resolve()
    if not stimulus_root_resolved.is_dir():
        return []

    files: list[str] = []
    for ext in ("*.mp4", "*.webm", "*.mkv"):
        for p in stimulus_root_resolved.glob(f"**/{ext}"):
            if p.is_file():
                rel = str(p.relative_to(stimulus_root_resolved)).replace("\\", "/")
                files.append(rel)

    return sorted(files)


def save_uploaded_stimulus(
    file_obj,
    original_filename: str,
    stimulus_root: Path,
    subfolder: str | None = None,
) -> dict:
    """Saves an uploaded video stream safely into stimulus_root and inspects it."""
    import re

    base_name = Path(original_filename).name
    # Strip any dangerous chars
    clean_name = re.sub(r"[^\w\.-]", "_", base_name)
    if not clean_name.lower().endswith((".mp4", ".webm", ".mkv", ".mov")):
        raise ValueError("รองรับเฉพาะไฟล์วิดีโอ (.mp4, .webm, .mkv) เท่านั้น")

    stimulus_root_resolved = stimulus_root.resolve()
    stimulus_root_resolved.mkdir(parents=True, exist_ok=True)

    # Determine subfolder
    if not subfolder:
        inferred = infer_suggested_quadrant(clean_name)
        folder_map = {
            "positive_low": "relax",
            "positive_high": "excited",
            "negative_high": "stress",
            "negative_low": "sad",
        }
        subfolder = folder_map.get(inferred or "", "uploads")
    else:
        # map quadrant keys if passed
        quad_map = {
            "positive_low": "relax",
            "positive_high": "excited",
            "negative_high": "stress",
            "negative_low": "sad",
        }
        subfolder = quad_map.get(subfolder, subfolder)
        subfolder = re.sub(r"[^\w-]", "", subfolder.strip().lower()) or "uploads"

    dest_dir = (stimulus_root_resolved / subfolder).resolve()
    if not str(dest_dir).startswith(str(stimulus_root_resolved)):
        raise ValueError("Invalid target directory path")
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / clean_name
    digest = hashlib.sha256()
    size = 0

    with open(dest_file, "wb") as out:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            size += len(chunk)

    checksum = digest.hexdigest().lower()
    duration = get_mp4_duration(dest_file)
    rel_normalized = str(dest_file.relative_to(stimulus_root_resolved)).replace("\\", "/")
    suggested_quadrant = infer_suggested_quadrant(rel_normalized)
    is_valid_duration = 45.0 <= duration <= 60.0

    return {
        "file_path": rel_normalized,
        "checksum": checksum,
        "duration_seconds": duration,
        "file_size_bytes": size,
        "suggested_quadrant": suggested_quadrant,
        "is_valid_duration": is_valid_duration,
    }

