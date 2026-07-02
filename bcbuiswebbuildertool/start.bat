@echo off
REM ============================================================
REM   Pacific Web Builder - one-click launcher (Windows)
REM   Double-click this file inside the bcbuiswebbuildertool folder.
REM   It creates .env if missing, starts the server, and opens a
REM   public HTTPS tunnel (HTTP/2, the stable protocol).
REM ============================================================
setlocal
cd /d "%~dp0"

REM Port (change here or set PORT before running). Server + tunnel stay in sync.
if "%PORT%"=="" set PORT=5000

echo.
echo ============================================================
echo    PACIFIC WEB BUILDER - Launcher
echo ============================================================

REM 1) Ensure a .env exists so login works (does NOT overwrite yours)
if not exist ".env" (
  echo Creating .env with default password: careful2026
  >.env echo ADMIN_PASSWORD=careful2026
) else (
  echo Found existing .env - using your settings.
)

REM 2) Start the server in its own window
echo Starting server on http://localhost:%PORT% ...
start "Pacific Web Builder - SERVER" cmd /k python src/server.py

REM 3) Wait for the server to come up, then start the tunnel on HTTP/2
timeout /t 6 /nobreak >nul
where cloudflared >nul 2>nul
if %errorlevel%==0 (
  echo Starting public HTTPS tunnel ^(HTTP/2^)...
  start "Pacific Web Builder - TUNNEL" cmd /k cloudflared tunnel --url http://localhost:%PORT% --protocol http2
  echo.
  echo Your public https://...trycloudflare.com link will appear in the TUNNEL window.
) else (
  echo.
  echo cloudflared not installed - running LOCAL ONLY.
  echo Install it from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
)

echo.
echo ------------------------------------------------------------
echo   Local dashboard : http://localhost:%PORT%
echo   Login password  : see the SERVER window banner (default: careful2026)
echo ------------------------------------------------------------
echo   Leave the SERVER and TUNNEL windows open while you work.
echo   Close them to stop the tool.
echo.
pause
