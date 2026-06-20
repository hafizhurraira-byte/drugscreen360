$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot "backend"
$FrontendPath = Join-Path $ProjectRoot "frontend"
$VenvActivate = Join-Path $BackendPath ".venv312\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Running DrugScreen360 checks..." -ForegroundColor Cyan

if (-not (Test-Path $VenvActivate)) {
    throw "Missing backend virtual environment: $VenvActivate"
}

Set-Location $BackendPath
. $VenvActivate
Write-Host "Running backend tests..." -ForegroundColor Cyan
python -m pytest

Set-Location $FrontendPath
if (-not (Test-Path "node_modules")) {
    Write-Host "node_modules not found. Installing frontend packages..." -ForegroundColor Yellow
    npm install
}

Write-Host "Running frontend tests..." -ForegroundColor Cyan
npm test

Write-Host "Building frontend..." -ForegroundColor Cyan
npm run build

Write-Host ""
Write-Host "All checks completed." -ForegroundColor Green
