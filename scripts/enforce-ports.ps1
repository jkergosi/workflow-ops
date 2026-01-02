<#
enforce-ports.ps1

Enforces deterministic port ownership on Windows.
Implements the requirements from reqs/ports.md.

Usage:
  .\scripts\enforce-ports.ps1 -Ports @(3000, 4000)
  .\scripts\enforce-ports.ps1 -Port 3000
  .\scripts\enforce-ports.ps1 -Port 4000

Behavior:
- Checks if ports are in use
- Identifies PID and process name
- Force-kills entire process tree
- Re-checks until port is free
- Aborts with error if port remains occupied
#>

param(
    [Parameter(Mandatory = $false)]
    [int[]]$Ports = @(),

    [Parameter(Mandatory = $false)]
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"

function Assert-NetTcpAvailable {
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        throw "Get-NetTCPConnection is required. This script requires Windows PowerShell with networking cmdlets."
    }
}

function Get-PortListeners {
    param([int]$PortNumber)
    
    Assert-NetTcpAvailable
    
    $listeners = Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction SilentlyContinue
    return $listeners
}

function Get-ProcessInfo {
    param([int]$ProcessId)
    
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($proc) {
            return @{
                Name = $proc.ProcessName
                Path = $proc.Path
                Id = $proc.Id
            }
        }
    } catch {
        return $null
    }
    return $null
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    
    $procInfo = Get-ProcessInfo -ProcessId $ProcessId
    if (-not $procInfo) {
        Write-Host "  PID $ProcessId no longer exists" -ForegroundColor Yellow
        return $true
    }
    
    Write-Host "  Killing PID $ProcessId ($($procInfo.Name))..." -ForegroundColor Yellow
    
    try {
        taskkill /PID $ProcessId /F /T 2>&1 | Out-Null
        Start-Sleep -Milliseconds 500
        return $true
    } catch {
        Write-Host "  Failed to kill PID $ProcessId: $_" -ForegroundColor Red
        return $false
    }
}

function Enforce-Port {
    param([int]$PortNumber)
    
    Write-Host "`n[Port $PortNumber] Checking port ownership..." -ForegroundColor Cyan
    
    $listeners = Get-PortListeners -PortNumber $PortNumber
    
    if ($listeners.Count -eq 0) {
        Write-Host "[Port $PortNumber] Port is free ✓" -ForegroundColor Green
        return $true
    }
    
    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
    
    Write-Host "[Port $PortNumber] Port is in use by PID(s): $($pids -join ', ')" -ForegroundColor Yellow
    
    foreach ($pid in $pids) {
        $procInfo = Get-ProcessInfo -ProcessId $pid
        if ($procInfo) {
            Write-Host "  Process: $($procInfo.Name) (PID: $pid)" -ForegroundColor Yellow
            if ($procInfo.Path) {
                Write-Host "  Path: $($procInfo.Path)" -ForegroundColor Gray
            }
        } else {
            Write-Host "  Process: Unknown (PID: $pid)" -ForegroundColor Yellow
        }
    }
    
    Write-Host "[Port $PortNumber] Force-killing process tree(s)..." -ForegroundColor Yellow
    
    $allKilled = $true
    foreach ($pid in $pids) {
        if (-not (Stop-ProcessTree -ProcessId $pid)) {
            $allKilled = $false
        }
    }
    
    if (-not $allKilled) {
        Write-Host "[Port $PortNumber] Failed to kill some processes" -ForegroundColor Red
    }
    
    $maxRetries = 10
    $retryDelay = 250
    $retries = 0
    
    while ($retries -lt $maxRetries) {
        Start-Sleep -Milliseconds $retryDelay
        $remaining = Get-PortListeners -PortNumber $PortNumber
        
        if ($remaining.Count -eq 0) {
            Write-Host "[Port $PortNumber] Port is now free ✓" -ForegroundColor Green
            return $true
        }
        
        $retries++
    }
    
    $stillOccupied = Get-PortListeners -PortNumber $PortNumber
    $remainingPids = $stillOccupied | Select-Object -ExpandProperty OwningProcess -Unique
    
    Write-Host "" -ForegroundColor Red
    Write-Host "❌ [Port $PortNumber] Port remains occupied after forced termination" -ForegroundColor Red
    Write-Host "   Blocking PID(s): $($remainingPids -join ', ')" -ForegroundColor Red
    
    foreach ($pid in $remainingPids) {
        $procInfo = Get-ProcessInfo -ProcessId $pid
        if ($procInfo) {
            Write-Host "   - PID $pid: $($procInfo.Name)" -ForegroundColor Red
        } else {
            Write-Host "   - PID $pid: Unknown process" -ForegroundColor Red
        }
    }
    
    Write-Host "" -ForegroundColor Red
    Write-Host "Aborting execution. Port $PortNumber must be free before continuing." -ForegroundColor Red
    
    return $false
}

function Main {
    $portsToCheck = @()
    
    if ($Port -gt 0) {
        $portsToCheck = @($Port)
    } elseif ($Ports.Count -gt 0) {
        $portsToCheck = $Ports
    } else {
        Write-Host "Error: Must specify either -Port or -Ports parameter" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host "Port Ownership Enforcement" -ForegroundColor Cyan
    Write-Host "Ports: $($portsToCheck -join ', ')" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor Cyan
    
    foreach ($port in $portsToCheck) {
        if (-not (Enforce-Port -PortNumber $port)) {
            exit 1
        }
    }
    
    Write-Host "`n✓ All ports are free and ready" -ForegroundColor Green
}

Main

