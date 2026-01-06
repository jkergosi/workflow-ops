<#
kill-ports.ps1

Fast, non-hanging port killer for dev servers.
Handles respawning parents.
Compatible with Windows PowerShell 5.1.
#>

param(
    [int[]]$Ports = @(3000, 4000),
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$MAX_RETRIES = 5
$WAIT_MS = 300

function Get-ListeningPids {
    param([int]$PortNumber)

    Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Kill-PidTree {
    param([int]$ProcessId)

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $proc) { return }

    $parentPid = $proc.ParentProcessId

    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 200

    if ($parentPid -and $parentPid -ne 0) {
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid" -ErrorAction SilentlyContinue
        if ($parent -and $parent.Name -match '^(node|npm|pnpm|yarn|nodemon|pm2|docker|python|uvicorn|gunicorn)') {
            Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 200
        }
    }
}

function Kill-Port {
    param([int]$PortNumber)

    Write-Host "[Port $PortNumber] Releasing..." -ForegroundColor Cyan

    for ($i = 1; $i -le $MAX_RETRIES; $i++) {
        $pids = Get-ListeningPids -PortNumber $PortNumber
        if (-not $pids) {
            Write-Host "[Port $PortNumber] Free" -ForegroundColor Green
            return
        }

        foreach ($processId in $pids) {
            Kill-PidTree -ProcessId $processId
        }

        Start-Sleep -Milliseconds $WAIT_MS
    }

    $still = Get-ListeningPids -PortNumber $PortNumber
    if ($still) {
        Write-Host "[Port $PortNumber] FAILED – still held by PID(s): $($still -join ', ')" -ForegroundColor Red
    } else {
        Write-Host "[Port $PortNumber] Free" -ForegroundColor Green
    }
}

function Main {
    $portsToKill = if ($Port -gt 0) { @($Port) } else { $Ports }

    foreach ($p in ($portsToKill | Sort-Object -Unique)) {
        Kill-Port -PortNumber $p
    }
}

Main
