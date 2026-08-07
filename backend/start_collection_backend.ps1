#!/usr/bin/env powershell
# Start the collection API in its required single-process, no-reload mode.

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Backend virtual environment is missing. Create .venv and install requirements_backend.txt first."
}
$EnvPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) {
    throw ".env is required. Create it with a private SECRET_KEY before collection startup."
}

# Validate SECRET_KEY via Pydantic Settings so that process-level env overrides,
# inline dotenv comments, and quoted values are all handled consistently.
$SecretCheckResult = & $Python -c @"
import sys
try:
    from app.config import Settings
    s = Settings()
    placeholders = {'change-me', 'change-me-to-a-random-256bit-secret'}
    key = (s.secret_key or '').strip()
    if not key or key in placeholders:
        print('SECRET_KEY must be replaced with a private random value before collection startup.')
        sys.exit(1)
except Exception as exc:
    print(f'Failed to load settings: {exc}')
    sys.exit(2)
"@
if ($LASTEXITCODE -ne 0) {
    throw $SecretCheckResult
}

& $Python -c "from pathlib import Path; from app.config import get_settings; s=get_settings(); [Path(p).mkdir(parents=True, exist_ok=True) for p in (s.collection_raw_dir, s.collection_lock_dir)]; assert Path(s.collection_stimulus_dir).is_dir(), 'collection_stimulus_dir must exist'"
if ($LASTEXITCODE -ne 0) {
    throw "Collection directory validation failed."
}

Write-Host "Starting collection API with one worker and reload disabled on port $Port." -ForegroundColor Green
& $Python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --workers 1
