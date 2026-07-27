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
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Warning ".env was created from .env.example; review it before collection."
}

& $Python -c "from pathlib import Path; from app.config import get_settings; s=get_settings(); [Path(p).mkdir(parents=True, exist_ok=True) for p in (s.collection_raw_dir, s.collection_lock_dir)]; assert Path(s.collection_stimulus_dir).is_dir(), 'collection_stimulus_dir must exist'"
if ($LASTEXITCODE -ne 0) {
    throw "Collection directory validation failed."
}

Write-Host "Starting collection API with one worker and reload disabled on port $Port." -ForegroundColor Green
& $Python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --workers 1
