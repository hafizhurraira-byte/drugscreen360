$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendScript = Join-Path $PSScriptRoot "start_backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start_frontend.ps1"

Write-Host ""
Write-Host "Opening DrugScreen360 backend and frontend in separate PowerShell windows..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$BackendScript`"" -WorkingDirectory $ProjectRoot
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$FrontendScript`"" -WorkingDirectory $ProjectRoot

Write-Host "Backend:  http://127.0.0.1:8010" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "Opening frontend in your browser..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5173"
