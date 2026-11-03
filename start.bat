@echo off
REM Windows launcher for the containerized app. Runs start.ps1 with the execution policy
REM bypassed for this one script. Usage: start.bat [up|down|logs|rebuild|restart]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
exit /b %ERRORLEVEL%
