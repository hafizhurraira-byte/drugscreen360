$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot "backend"
$VenvActivate = Join-Path $BackendPath ".venv312\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Starting DrugScreen360 backend..." -ForegroundColor Cyan
Write-Host "Backend folder: $BackendPath"

if (-not (Test-Path $VenvActivate)) {
    Write-Host "Python 3.12 virtual environment was not found at backend\.venv312." -ForegroundColor Yellow
    Write-Host "Create it with:"
    Write-Host '  cd "D:\DRUG CONJUGATE\drugscreen360\backend"'
    Write-Host '  py -3.12 -m venv .venv312'
    Write-Host '  .\.venv312\Scripts\Activate.ps1'
    Write-Host '  pip install -r requirements.txt'
    exit 1
}

Set-Location $BackendPath
. $VenvActivate

Write-Host "Backend API:  http://127.0.0.1:8010" -ForegroundColor Green
Write-Host "API docs:     http://127.0.0.1:8010/docs" -ForegroundColor Green
Write-Host "Health check: http://127.0.0.1:8010/api/health" -ForegroundColor Green
Write-Host ""

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
