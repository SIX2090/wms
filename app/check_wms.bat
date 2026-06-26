@echo off
setlocal EnableExtensions

echo Checking local WMS...
curl -I --max-time 5 http://127.0.0.1:8080/login >nul 2>nul
if errorlevel 1 (
    echo Local check failed: http://127.0.0.1:8080/login
    echo.
    echo Port 8080:
    netstat -ano | findstr :8080
    exit /b 1
)

echo Local check OK: http://127.0.0.1:8080/login
echo.
echo Port 8080:
netstat -ano | findstr :8080
exit /b 0
