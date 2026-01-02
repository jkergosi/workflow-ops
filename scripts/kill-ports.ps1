<#
kill-ports.ps1

Quick script to kill processes on ports 3000 and/or 4000.
Use this when you need to manually stop dev servers.

Usage:
  .\scripts\kill-ports.ps1              # Kills both 3000 and 4000
  .\scripts\kill-ports.ps1 -Port 3000  # Kills only port 3000
  .\scripts\kill-ports.ps1 -Port 4000   # Kills only port 4000
  .\scripts\kill-ports.ps1 -Ports @(3000, 4000)  # Kills specific ports
#>

param(
    [Parameter(Mandatory = $false)]
    [int[]]$Ports = @(3000, 4000),

    [Parameter(Mandatory = $false)]
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"

function Assert-NetTcpAvailable {
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        throw "Get-NetTCPConnection is required. This script requires Windows PowerShell with networking cmdlets."
    }
}

function Kill-Port {
    param([int]$PortNumber)
    
    Assert-NetTcpAvailable
    
    $listeners = Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction SilentlyContinue
    
    if ($listeners.Count -eq 0) {
        Write-Host "[Port $PortNumber] No process found - port is already free" -ForegroundColor Green
        return
    }
    
    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
    
    Write-Host "[Port $PortNumber] Found process(es): $($pids -join ', ')" -ForegroundColor Yellow
    
    foreach ($pid in $pids) {
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  Killing PID $pid ($($proc.ProcessName))..." -ForegroundColor Yellow
                taskkill /PID $pid /F /T 2>&1 | Out-Null
            }
        } catch {
            Write-Host "  Failed to kill PID $pid: $_" -ForegroundColor Red
        }
    }
    
    Start-Sleep -Milliseconds 500
    
    $remaining = Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction SilentlyContinue
    if ($remaining.Count -eq 0) {
        Write-Host "[Port $PortNumber] ✓ Port is now free" -ForegroundColor Green
    } else {
        $stillRunning = $remaining | Select-Object -ExpandProperty OwningProcess -Unique
        Write-Host "[Port $PortNumber] ⚠️  Port still in use by PID(s): $($stillRunning -join ', ')" -ForegroundColor Red
    }
}

function Main {
    $portsToKill = @()
    
    if ($Port -gt 0) {
        $portsToKill = @($Port)
    } elseif ($Ports.Count -gt 0) {
        $portsToKill = $Ports
    } else {
        $portsToKill = @(3000, 4000)
    }
    
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host "Killing processes on ports: $($portsToKill -join ', ')" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host ""
    
    foreach ($port in $portsToKill) {
        Kill-Port -PortNumber $port
        Write-Host ""
    }
    
    Write-Host "Done." -ForegroundColor Green
}

Main

