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
$SecretLine = Get-Content -LiteralPath $EnvPath |
    Where-Object { $_ -match "^\s*SECRET_KEY\s*=" } |
    Select-Object -Last 1
if ($null -eq $SecretLine) {
    throw "SECRET_KEY must be set in .env before collection startup."
}
$SecretValue = ($SecretLine -split "=", 2)[1].Trim()
if (
    $SecretValue.Length -ge 2 -and
    (($SecretValue.StartsWith('"') -and $SecretValue.EndsWith('"')) -or
     ($SecretValue.StartsWith("'") -and $SecretValue.EndsWith("'")))
) {
    $SecretValue = $SecretValue.Substring(1, $SecretValue.Length - 2)
}
$PublicPlaceholders = @("change-me", "change-me-to-a-random-256bit-secret")
if ([string]::IsNullOrWhiteSpace($SecretValue) -or $PublicPlaceholders -contains $SecretValue) {
    throw "SECRET_KEY must be replaced with a private random value before collection startup."
}

& $Python -c "from pathlib import Path; from app.config import get_settings; s=get_settings(); [Path(p).mkdir(parents=True, exist_ok=True) for p in (s.collection_raw_dir, s.collection_lock_dir)]; assert Path(s.collection_stimulus_dir).is_dir(), 'collection_stimulus_dir must exist'"
if ($LASTEXITCODE -ne 0) {
    throw "Collection directory validation failed."
}

Write-Host "Starting collection API with one worker and reload disabled on port $Port." -ForegroundColor Green
& $Python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --workers 1
