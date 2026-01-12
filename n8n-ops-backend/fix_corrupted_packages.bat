@echo off
REM Batch file to fix corrupted Python packages
REM This is a simple wrapper that runs the Python fix script

echo ================================================================================
echo Python Package Corruption Fix Utility (Batch)
echo ================================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python or add it to your PATH environment variable
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Check if the Python script exists
if not exist "%~dp0fix_corrupted_packages.py" (
    echo ERROR: fix_corrupted_packages.py not found in current directory
    echo Expected location: %~dp0fix_corrupted_packages.py
    pause
    exit /b 1
)

echo Starting corruption fix script...
echo.

REM Run the Python script
python "%~dp0fix_corrupted_packages.py"

echo.
echo ================================================================================
echo Script execution complete
echo ================================================================================
pause
