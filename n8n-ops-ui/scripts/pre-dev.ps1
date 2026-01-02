<#
pre-dev.ps1

Pre-flight check for frontend dev server.
Enforces port 3000 ownership per reqs/ports.md.
#>

$ErrorActionPreference = "Stop"

$FRONTEND_PORT = 3000
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$enforceScript = Join-Path $repoRoot "scripts" "enforce-ports.ps1"

if (-not (Test-Path $enforceScript)) {
    Write-Host "⚠️  Port enforcement script not found at $enforceScript" -ForegroundColor Yellow
    Write-Host "   Skipping port check. Port $FRONTEND_PORT may be in use." -ForegroundColor Yellow
    exit 0
}

Write-Host "Enforcing port ownership for frontend (port $FRONTEND_PORT)..." -ForegroundColor Cyan

& powershell.exe -ExecutionPolicy Bypass -File $enforceScript -Port $FRONTEND_PORT

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Port enforcement failed. Cannot start dev server." -ForegroundColor Red
    exit 1
}

Write-Host "✓ Port $FRONTEND_PORT is free and ready" -ForegroundColor Green

