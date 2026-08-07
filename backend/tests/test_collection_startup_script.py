from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "start_collection_backend.ps1"
_REAL_VENV = Path(__file__).parents[1] / ".venv"
_BACKEND_ROOT = Path(__file__).parents[1]


def _run_script_fake_python(
    tmp_path: Path, env_text: str | None
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run with a fake (empty) python.exe — only tests pre-Python shell checks."""
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


def _run_script_real_python(
    tmp_path: Path, env_text: str, extra_env: dict | None = None
) -> subprocess.CompletedProcess[str]:
    """Run with the real venv Python — tests Pydantic-based secret validation.

    Uses the real python.exe from the project venv (not a copy) so that
    all installed packages (pydantic, pydantic-settings) are reachable.
    The script is run in an isolated backend directory; PYTHONPATH points
    to the real backend source root.
    """
    backend = tmp_path / "backend"
    backend.mkdir()
    shutil.copy2(SCRIPT, backend / SCRIPT.name)
    # Create a .venv/Scripts/python.exe symlink (or junction) pointing to the real binary
    venv_scripts = backend / ".venv" / "Scripts"
    venv_scripts.mkdir(parents=True)
    dst_python = venv_scripts / "python.exe"
    real_python = _REAL_VENV / "Scripts" / "python.exe"
    # Copy pyvenv.cfg one level up so Python finds its home
    pyvenv_cfg = _REAL_VENV / "pyvenv.cfg"
    if pyvenv_cfg.exists():
        shutil.copy2(pyvenv_cfg, backend / ".venv" / "pyvenv.cfg")
    # Hard-link or copy the python.exe so Set-Location in the script finds it
    shutil.copy2(real_python, dst_python)

    (backend / ".env").write_text(env_text, encoding="utf-8")

    # Build env: inherit current env, apply extra overrides, inject site-packages path
    import site
    env = {**os.environ}
    if extra_env:
        env.update(extra_env)
    # Prepend real backend root AND real venv site-packages so all imports resolve
    real_site = _REAL_VENV / "Lib" / "site-packages"
    extra_path = os.pathsep.join([str(_BACKEND_ROOT), str(real_site)])
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{extra_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else extra_path
    env.setdefault("COLLECTION_STIMULUS_DIR", str(tmp_path / "no_stimuli"))

    return subprocess.run(
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
        timeout=30,
        check=False,
        env=env,
        cwd=str(backend),
    )


def test_startup_refuses_missing_env_without_creating_one(tmp_path):
    result, env_path = _run_script_fake_python(tmp_path, None)

    assert result.returncode != 0
    assert not env_path.exists()
    assert ".env is required" in f"{result.stdout}\n{result.stderr}"


def test_startup_refuses_public_secret_key_placeholder(tmp_path):
    """Pydantic-based validation must reject well-known placeholder values."""
    result = _run_script_real_python(
        tmp_path,
        "SECRET_KEY=change-me-to-a-random-256bit-secret\n",
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, f"Expected refusal, got: {output}"
    assert "SECRET_KEY" in output


def test_startup_refuses_process_env_placeholder_override(tmp_path):
    """Process-level SECRET_KEY env var that is a placeholder must be refused,
    even when the .env file contains a valid-looking private key."""
    result = _run_script_real_python(
        tmp_path,
        "SECRET_KEY=my-real-private-key-that-is-long-enough\n",
        extra_env={"SECRET_KEY": "change-me"},
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, (
        f"Script must refuse when process-level SECRET_KEY is a placeholder. "
        f"Output: {output}"
    )
    assert "SECRET_KEY" in output

