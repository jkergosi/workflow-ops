# PowerShell Script to Fix Corrupted Python Packages
# This script removes corrupted package directories and reinstalls packages

param(
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,

    [Parameter(Mandatory=$false)]
    [switch]$AutoConfirm
)

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 79 -ForegroundColor Cyan
Write-Host "Python Package Corruption Fix Utility (PowerShell)" -ForegroundColor Yellow
Write-Host "=" * 80 -ForegroundColor Cyan

# Get site-packages path
$pythonPath = "F:\Python312\Lib\site-packages"

if (-not (Test-Path $pythonPath)) {
    Write-Host "`nError: Site-packages directory not found at: $pythonPath" -ForegroundColor Red
    Write-Host "Please update the `$pythonPath variable in this script with your Python installation path." -ForegroundColor Yellow
    exit 1
}

Write-Host "`nScanning: $pythonPath" -ForegroundColor Cyan
Write-Host "-" * 80

# Find corrupted packages (directories starting with ~)
$corruptedPackages = Get-ChildItem -Path $pythonPath -Directory | Where-Object { $_.Name -like "~*" }

if ($corruptedPackages.Count -eq 0) {
    Write-Host "`n✓ No corrupted packages found! Your environment is clean." -ForegroundColor Green
    exit 0
}

# Display found corrupted packages
Write-Host "`nFound corrupted packages:" -ForegroundColor Yellow
foreach ($pkg in $corruptedPackages) {
    Write-Host "  - $($pkg.Name)" -ForegroundColor Red
}

Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "Found $($corruptedPackages.Count) corrupted package(s)" -ForegroundColor Yellow
Write-Host "=" * 80 -ForegroundColor Cyan

# If dry run, just show what would be deleted
if ($DryRun) {
    Write-Host "`n--- DRY RUN MODE ---" -ForegroundColor Yellow
    Write-Host "The following directories would be removed:" -ForegroundColor Yellow
    foreach ($pkg in $corruptedPackages) {
        Write-Host "  [DRY RUN] Would remove: $($pkg.FullName)" -ForegroundColor Gray
    }
    exit 0
}

# Ask for confirmation unless auto-confirm is set
if (-not $AutoConfirm) {
    Write-Host "`nDo you want to remove these corrupted packages? (Y/N): " -NoNewline -ForegroundColor Yellow
    $confirmation = Read-Host

    if ($confirmation -ne "Y" -and $confirmation -ne "y") {
        Write-Host "Operation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# Remove corrupted packages
Write-Host "`nRemoving corrupted packages..." -ForegroundColor Cyan
Write-Host "-" * 80

$removedCount = 0
$errorCount = 0

foreach ($pkg in $corruptedPackages) {
    try {
        Write-Host "Removing: $($pkg.Name)..." -NoNewline
        Remove-Item -Path $pkg.FullName -Recurse -Force -ErrorAction Stop
        Write-Host " ✓" -ForegroundColor Green
        $removedCount++
    }
    catch {
        Write-Host " ✗" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "Cleanup Summary:" -ForegroundColor Yellow
Write-Host "  Successfully removed: $removedCount" -ForegroundColor Green
Write-Host "  Errors: $errorCount" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Gray" })
Write-Host "=" * 80 -ForegroundColor Cyan

# Ask if user wants to reinstall packages
if (-not $AutoConfirm) {
    Write-Host "`nDo you want to reinstall packages from requirements.txt? (Y/N): " -NoNewline -ForegroundColor Yellow
    $reinstall = Read-Host
}
else {
    $reinstall = "Y"
}

if ($reinstall -eq "Y" -or $reinstall -eq "y") {
    $requirementsPath = Join-Path $PSScriptRoot "requirements.txt"

    if (Test-Path $requirementsPath) {
        Write-Host "`nReinstalling packages from requirements.txt..." -ForegroundColor Cyan
        Write-Host "-" * 80

        # Upgrade pip first
        Write-Host "Upgrading pip..." -ForegroundColor Cyan
        & python -m pip install --upgrade pip

        # Install requirements
        Write-Host "`nInstalling requirements..." -ForegroundColor Cyan
        & python -m pip install -r $requirementsPath

        Write-Host "`n✓ Package reinstallation complete!" -ForegroundColor Green
    }
    else {
        Write-Host "`nWarning: requirements.txt not found at: $requirementsPath" -ForegroundColor Yellow
        Write-Host "Skipping package reinstallation." -ForegroundColor Yellow
    }
}

Write-Host "`n✓ All operations complete!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
