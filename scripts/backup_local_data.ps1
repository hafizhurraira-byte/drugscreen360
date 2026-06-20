$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$BackupRoot = Join-Path $ProjectRoot "backups"
$BackupPath = Join-Path $BackupRoot $Timestamp

New-Item -ItemType Directory -Force -Path $BackupPath | Out-Null

Write-Host ""
Write-Host "Creating DrugScreen360 local backup..." -ForegroundColor Cyan
Write-Host "Backup folder: $BackupPath"

$Patterns = @(
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "README.md",
    "VERSION"
)

foreach ($Pattern in $Patterns) {
    Get-ChildItem -Path $ProjectRoot -Filter $Pattern -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $BackupPath -Force
            Write-Host "Copied $($_.Name)"
        }
}

$OptionalFolders = @(
    "backend\uploads",
    "backend\reports",
    "backend\app\uploads"
)

foreach ($RelativeFolder in $OptionalFolders) {
    $Source = Join-Path $ProjectRoot $RelativeFolder
    if (Test-Path $Source) {
        $Destination = Join-Path $BackupPath $RelativeFolder
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
        Write-Host "Copied $RelativeFolder"
    }
}

Write-Host ""
Write-Host "Backup complete." -ForegroundColor Green
