<#
backend_cycle.ps1

Usage:
  .\backend_cycle.ps1 -Action start
  .\backend_cycle.ps1 -Action stop
  .\backend_cycle.ps1 -Action restart

Behavior:
- Backend ALWAYS runs on port 4000
- start: does nothing if already running on 4000
- stop: kills the process(es) bound to 4000 with bounded timeout
- restart: stop (if running) + start
- start opens ONE new PowerShell window showing live logs
- uvicorn --reload handles file-change restarts automatically
#>

param (
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "stop", "restart")]
    [string]$Action,

    [int]$StopTimeoutSeconds = 10
)

$BACKEND_PORT = 4000

function Get-RepoBackendRoot {
    if ($PSScriptRoot) { return $PSScriptRoot }
    return (Get-Location).Path
}

function Assert-NetTcpAvailable {
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        throw "Get-NetTCPConnection is required to enforce single-instance-by-port on this system."
    }
}

function Get-BackendListeners {
    Assert-NetTcpAvailable
    return Get-NetTCPConnection -LocalPort $BACKEND_PORT -ErrorAction SilentlyContinue
}

function Is-BackendRunning {
    $listeners = Get-BackendListeners
    return ($listeners.Count -gt 0)
}

function Stop-Backend {
    Write-Host "Stopping backend on port $BACKEND_PORT..." -ForegroundColor Cyan

    $listeners = Get-BackendListeners
    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($p in $pids) {
        Write-Host "Stopping PID $p (bound to $BACKEND_PORT)..." -ForegroundColor Yellow
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }

    $deadline = (Get-Date).AddSeconds($StopTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Is-BackendRunning)) { break }
        Start-Sleep -Milliseconds 250
    }

    if (Is-BackendRunning) {
        $remaining = Get-BackendListeners | Select-Object -ExpandProperty OwningProcess -Unique
        throw "Backend failed to stop. Port $BACKEND_PORT still in use by PID(s): $($remaining -join ', ')"
    }

    Write-Host "Backend stopped. Port $BACKEND_PORT is free." -ForegroundColor Green
}

function Start-Backend {
    if (Is-BackendRunning) {
        Write-Host "Backend already running on port $BACKEND_PORT. Start skipped." -ForegroundColor Yellow
        return
    }

    Write-Host "Starting backend on port $BACKEND_PORT (new window)..." -ForegroundColor Cyan

    $workDir = Get-RepoBackendRoot

    Write-Host "API:     http://localhost:$BACKEND_PORT" -ForegroundColor Green
    Write-Host "Swagger: http://localhost:$BACKEND_PORT/api/v1/docs" -ForegroundColor Green

    # Build a single command line (avoid PowerShell parsing issues with --flags)
    $uvicornCmd = "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT --access-log --log-level info"

    # New PowerShell window:
    # - Set location
    # - Execute via cmd.exe so --flags are not parsed by PowerShell
    # - Keep window open (-NoExit) to keep logs visible
    $psCommand = "Set-Location -LiteralPath `"$workDir`"; cmd.exe /c `"$uvicornCmd`""

    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-Command", $psCommand) `
        -WorkingDirectory $workDir | Out-Null

    Write-Host "Backend started (reload enabled, logs in new window)." -ForegroundColor Green
}

switch ($Action) {
    "start" {
        Start-Backend
    }
    "stop" {
        if (Is-BackendRunning) {
            Stop-Backend
        } else {
            Write-Host "Backend not running. Nothing to stop." -ForegroundColor Yellow
        }
    }
    "restart" {
        Write-Host "Restarting backend..." -ForegroundColor Cyan
        if (Is-BackendRunning) {
            Stop-Backend
            Start-Sleep -Seconds 1
        }
        Start-Backend
    }
}
