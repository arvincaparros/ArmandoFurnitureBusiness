@echo off
echo ============================================
echo   Armando Furniture - RESET DEMO DATA
echo ============================================
echo.
echo WARNING: This will PERMANENTLY DELETE all data in this demo,
echo including any products, resources, transactions, and history
echo you have created or changed since the demo was set up.
echo.
echo This CANNOT be undone.
echo.
set /p CONFIRM="Type YES (capital letters) to continue, or press Enter to cancel: "

if /i not "%CONFIRM%"=="YES" (
    echo.
    echo Reset cancelled. Nothing was changed.
    echo.
    pause
    exit /b 0
)

echo.
echo Deleting all demo data...
cd /d "%~dp0"
docker compose -f docker-compose.client.yml down -v

echo.
echo Done. All demo data has been removed.
echo The next time you double-click start-demo.bat, a fresh copy of
echo the demo data will be created automatically.
echo.
pause
