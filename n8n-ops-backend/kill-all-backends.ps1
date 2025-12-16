# Kill all backend processes on port 4000
Write-Host "Stopping all processes on port 4000..." -ForegroundColor Cyan

$processes = Get-NetTCPConnection -LocalPort 4000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

if ($processes) {
    foreach ($procId in $processes) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Stopping process $procId ($($proc.ProcessName))..." -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "All processes on port 4000 stopped." -ForegroundColor Green
} else {
    Write-Host "No processes found on port 4000" -ForegroundColor Yellow
}

# Also kill any Python processes that might be running uvicorn
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*" -or $_.Path -like "*n8n-ops*"
}

if ($pythonProcs) {
    foreach ($proc in $pythonProcs) {
        Write-Host "Stopping Python process $($proc.Id)..." -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Python uvicorn processes stopped." -ForegroundColor Green
}

Write-Host ""
Write-Host "Waiting 2 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 2

Write-Host "Verifying port 4000 is free..." -ForegroundColor Cyan
$remaining = Get-NetTCPConnection -LocalPort 4000 -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "WARNING: Port 4000 is still in use!" -ForegroundColor Red
    $remaining | Format-Table
} else {
    Write-Host "Port 4000 is now free." -ForegroundColor Green
}

