@echo off
echo ============================================
echo   Armando Furniture - Stopping Demo
echo ============================================
echo.

cd /d "%~dp0"
docker compose -f docker-compose.client.yml down

echo.
echo The application has been stopped.
echo Your data has been kept and will still be there next time you
echo double-click start-demo.bat.
echo.
pause
