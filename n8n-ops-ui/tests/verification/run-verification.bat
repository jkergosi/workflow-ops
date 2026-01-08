@echo off
REM Verification Test Runner for Entitlement Enforcement (Windows)
REM This script helps run the verification tests with proper setup

setlocal enabledelayedexpansion

echo ==================================================
echo Entitlement Enforcement Verification Test Runner
echo ==================================================
echo.

REM Check if .env.test exists
if not exist ".env.test" (
    echo Warning: .env.test file not found
    echo Creating template .env.test file...
    (
        echo # API Configuration
        echo API_BASE_URL=http://localhost:8000
        echo BASE_URL=http://localhost:3000
        echo.
        echo # Test Credentials ^(UPDATE THESE!^)
        echo TEST_TENANT_EMAIL=test-enforcement@example.com
        echo TEST_AUTH_TOKEN=your_test_auth_token_here
        echo.
        echo # Optional: Override for specific tests
        echo # TEST_TENANT_ID=tenant_id_here
    ) > .env.test
    echo Please update .env.test with your test credentials
    exit /b 1
)

REM Load environment variables from .env.test
for /f "usebackq tokens=*" %%a in (".env.test") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "!line!"=="" (
            set "!line!"
        )
    )
)

REM Check if backend is running
echo Checking backend health...
curl -s -o nul -w "%%{http_code}" "%API_BASE_URL%/health" > temp_health.txt 2>&1
set /p BACKEND_HEALTH=<temp_health.txt
del temp_health.txt 2>nul

if not "%BACKEND_HEALTH%"=="200" (
    echo Error: Backend is not responding at %API_BASE_URL%
    echo Please start the backend server first:
    echo   cd ..\n8n-ops-backend ^&^& python -m app.main
    exit /b 1
)

echo [92m✓ Backend is running[0m

REM Check if frontend is running (optional)
curl -s -o nul -w "%%{http_code}" "%BASE_URL%" > temp_frontend.txt 2>&1
set /p FRONTEND_HEALTH=<temp_frontend.txt
del temp_frontend.txt 2>nul

if not "%FRONTEND_HEALTH%"=="200" (
    echo [93mWarning: Frontend is not running at %BASE_URL%[0m
    echo Some UI tests may fail. Start frontend with: npm run dev
)

echo.
echo [92mRunning verification tests...[0m
echo.

REM Parse command line arguments
set "TEST_FILTER="
set "RUN_MODE=--reporter=list"

:parse_args
if "%~1"=="" goto run_tests

if /i "%~1"=="--ui" (
    set "RUN_MODE=--ui"
    shift
    goto parse_args
)
if /i "%~1"=="--headed" (
    set "RUN_MODE=--headed --reporter=list"
    shift
    goto parse_args
)
if /i "%~1"=="--html" (
    set "RUN_MODE=--reporter=html"
    shift
    goto parse_args
)
if /i "%~1"=="--debug" (
    set "RUN_MODE=--debug"
    shift
    goto parse_args
)
if /i "%~1"=="--environment" (
    set "TEST_FILTER=-g \"Environment Limit\""
    shift
    goto parse_args
)
if /i "%~1"=="--team" (
    set "TEST_FILTER=-g \"Team Member\""
    shift
    goto parse_args
)
if /i "%~1"=="--downgrade" (
    set "TEST_FILTER=-g \"Downgrade\""
    shift
    goto parse_args
)
if /i "%~1"=="--webhook" (
    set "TEST_FILTER=-g \"Webhook\""
    shift
    goto parse_args
)
if /i "%~1"=="--retention" (
    set "TEST_FILTER=-g \"Retention\""
    shift
    goto parse_args
)
if /i "%~1"=="--all" (
    set "TEST_FILTER="
    shift
    goto parse_args
)

echo Unknown option: %~1
echo Usage: %~nx0 [--ui^|--headed^|--html^|--debug] [--environment^|--team^|--downgrade^|--webhook^|--retention^|--all]
exit /b 1

:run_tests
REM Run the tests
call npx playwright test tests/verification %RUN_MODE% %TEST_FILTER%

if %errorlevel% equ 0 (
    echo.
    echo ==================================================
    echo [92m✓ All verification tests passed![0m
    echo ==================================================
    echo.
    echo Next steps:
    echo   1. Review the test report ^(if --html was used^)
    echo   2. Document the verification results
    echo   3. Delete verification tests ^(Task T016^)
    echo.
) else (
    echo.
    echo ==================================================
    echo [91m✗ Some verification tests failed[0m
    echo ==================================================
    echo.
    echo Debugging steps:
    echo   1. Check backend logs for errors
    echo   2. Verify database state
    echo   3. Run with --ui flag to debug interactively:
    echo      tests\verification\run-verification.bat --ui
    echo   4. Check the README.md for troubleshooting
    echo.
    exit /b 1
)

endlocal
