from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "start_collection_backend.ps1"


def _run_script(
    tmp_path: Path, env_text: str | None
) -> tuple[subprocess.CompletedProcess[str], Path]:
    backend = tmp_path / "backend"
    backend.mkdir()
    shutil.copy2(SCRIPT, backend / SCRIPT.name)
    python = backend / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    (backend / ".env.example").write_text(
        "SECRET_KEY=change-me-to-a-random-256bit-secret\n",
        encoding="utf-8",
    )
    env_path = backend / ".env"
    if env_text is not None:
        env_path.write_text(env_text, encoding="utf-8")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(backend / SCRIPT.name),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result, env_path


def test_startup_refuses_missing_env_without_creating_one(tmp_path):
    result, env_path = _run_script(tmp_path, None)

    assert result.returncode != 0
    assert not env_path.exists()
    assert ".env is required" in f"{result.stdout}\n{result.stderr}"


def test_startup_refuses_public_secret_key_placeholder(tmp_path):
    result, _ = _run_script(
        tmp_path,
        "SECRET_KEY=change-me-to-a-random-256bit-secret\n",
    )

    assert result.returncode != 0
    assert "SECRET_KEY must be replaced" in f"{result.stdout}\n{result.stderr}"
