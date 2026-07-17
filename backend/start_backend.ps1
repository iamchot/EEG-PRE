#!/usr/bin/env powershell
# ==========================================
# Dream Comicverse — Backend Startup Script
# ==========================================
# Usage: .\start_backend.ps1

Write-Host "Starting Dream Comicverse Backend..." -ForegroundColor Cyan

# Check if virtual env exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate venv
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements_backend.txt --quiet

# Copy .env if not exists
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env created from .env.example — please update your API keys!" -ForegroundColor Yellow
}

# Seed database
Write-Host "Seeding database..." -ForegroundColor Yellow
python seed.py

# Start FastAPI server
Write-Host "Starting FastAPI on http://localhost:8000" -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
