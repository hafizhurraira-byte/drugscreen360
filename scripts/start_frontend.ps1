$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendPath = Join-Path $ProjectRoot "frontend"

Write-Host ""
Write-Host "Starting DrugScreen360 frontend..." -ForegroundColor Cyan
Write-Host "Frontend folder: $FrontendPath"

Set-Location $FrontendPath

if (-not (Test-Path "node_modules")) {
    Write-Host "node_modules not found. Installing frontend packages..." -ForegroundColor Yellow
    npm install
}

Write-Host "Frontend URL: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host ""

npm run dev -- --host 127.0.0.1 --port 5173
