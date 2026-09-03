@echo off
REM Launches Chrome with remote debugging enabled on a dedicated profile,
REM so the AI Coding Practice Agent can attach to it via CDP.
REM Double-click this file (or run it) each time before using the agent.

echo Killing any existing Chrome processes...
taskkill /F /IM chrome.exe /T >nul 2>&1

echo Launching Chrome with remote debugging on port 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug-profile"

echo.
echo Chrome launched. Verify it worked by visiting:
echo   http://127.0.0.1:9222/json/version
echo.
echo Then open your coding problem in a new tab in that window.
pause
