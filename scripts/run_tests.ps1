$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot "backend"
$FrontendPath = Join-Path $ProjectRoot "frontend"
$VenvActivate = Join-Path $BackendPath ".venv312\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Running DrugScreen360 checks..." -ForegroundColor Cyan

if (-not (Test-Path $VenvActivate)) {
    throw "Missing backend virtual environment: $VenvActivate. Create it with: cd `"$BackendPath`"; py -3.12 -m venv .venv312; .\.venv312\Scripts\Activate.ps1; pip install -r requirements.txt"
}

Set-Location $BackendPath
. $VenvActivate
Write-Host "Running backend tests..." -ForegroundColor Cyan
python -m pytest

Set-Location $FrontendPath
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js LTS, then run this script again."
}

if (-not (Test-Path "node_modules")) {
    Write-Host "node_modules not found. Installing frontend packages..." -ForegroundColor Yellow
    npm install
}

Write-Host "Running frontend tests..." -ForegroundColor Cyan
npm test

Write-Host "Building frontend..." -ForegroundColor Cyan
npm run build

Write-Host ""
Write-Host "All DrugScreen360 local checks completed successfully." -ForegroundColor Green
