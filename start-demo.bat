@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Armando Furniture - Starting Demo
echo ============================================
echo.

where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker Desktop was not found on this computer.
    echo.
    echo Please install Docker Desktop from:
    echo   https://www.docker.com/products/docker-desktop
    echo then try again.
    echo.
    pause
    exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker Desktop does not appear to be running.
    echo.
    echo Please start Docker Desktop and wait until it says
    echo "Docker Desktop is running", then double-click start-demo.bat again.
    echo.
    pause
    exit /b 1
)

echo Docker Desktop found. Starting the application...
echo This may take a few minutes the first time while everything downloads and builds.
echo.

cd /d "%~dp0"
docker compose -f docker-compose.client.yml up -d --build
if errorlevel 1 (
    echo.
    echo [ERROR] Something went wrong while starting the application.
    echo Please check the messages above, or ask for help.
    echo.
    pause
    exit /b 1
)

echo.
echo Waiting for the application to finish starting up...

set /a WAITED=0
set /a MAX_WAIT=180

:waitloop
set "HEALTH="
for /f "usebackq delims=" %%H in (`docker inspect --format="{{.State.Health.Status}}" armando-furniture-client-backend 2^>nul`) do set "HEALTH=%%H"

if "!HEALTH!"=="healthy" goto ready

if !WAITED! GEQ !MAX_WAIT! (
    echo.
    echo [WARNING] The application is taking longer than expected to start.
    echo It may still finish starting in the background - try opening
    echo http://localhost:3000 in your browser in a minute or two.
    echo.
    echo If it still does not work, see CLIENT-SETUP.md for help, or ask
    echo whoever set up this demo for you.
    echo.
    pause
    exit /b 1
)

timeout /t 3 /nobreak >nul
set /a WAITED+=3
goto waitloop

:ready
echo.
echo ============================================
echo   Armando Furniture is ready!
echo ============================================
echo Opening your browser now...
start "" http://localhost:3000
echo.
echo You can close this window. The application will keep running
echo in the background until you double-click stop-demo.bat.
echo.
pause
exit /b 0
