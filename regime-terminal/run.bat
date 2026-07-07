@echo off
rem Double-click this file to launch the Regime Terminal web app.
rem It changes to its own folder, opens your browser, and starts the server.
cd /d "%~dp0"
echo.
echo  Regime Terminal  -  http://localhost:8000
echo  (keep this window open; close it to stop the server)
echo.
start "" http://localhost:8000
python serve.py
echo.
echo  Server stopped. If you saw an error above, make sure Python is installed
echo  and on PATH (try: python --version).
pause
